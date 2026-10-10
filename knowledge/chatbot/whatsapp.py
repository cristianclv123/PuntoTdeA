"""Adaptador de WhatsApp Cloud API para el flujo conversacional."""

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime
from typing import Any

from django.conf import settings
from django.utils import timezone

from communications.adapters.meta_adapter import send_text_message
from communications.models import Contact
from cases.models import Conversation as CaseConversation
from cases.services.ingestion import InboundPayload, ingest_inbound_message
from ..models import ChatConversation
from .inactivity import INACTIVITY_TIMEOUT, close_if_inactive
from .workflow import ChatbotWorkflow


logger = logging.getLogger(__name__)


def _manager(model):
    return getattr(model, '_default_manager')


def verify_webhook(mode: str, token: str, challenge: str) -> str | None:
    if mode == 'subscribe' and token == getattr(settings, 'META_VERIFY_TOKEN', ''):
        return challenge
    return None


def validate_signature(raw_body: bytes, signature_header: str | None) -> bool:
    secret = getattr(settings, 'META_APP_SECRET', '')
    if not secret:
        return False
    if not signature_header or not signature_header.startswith('sha256='):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.split('=', 1)[1])


def _messages(payload: dict[str, Any]):
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value') or {}
            for message in value.get('messages') or []:
                if message.get('type') != 'text':
                    continue
                text = ((message.get('text') or {}).get('body') or '').strip()
                sender = message.get('from', '').strip()
                if text and sender:
                    yield sender, text


def _is_yes(text: str) -> bool:
    return text.lower().strip() in {'si', 'sí', 's', 'yes'}


def _is_no(text: str) -> bool:
    return text.lower().strip() in {'no', 'n'}


def _requests_advisor(text: str) -> bool:
    normalized = text.lower()
    return any(word in normalized for word in ('asesor', 'humano', 'persona'))


def _find_contact(sender: str) -> Contact | None:
    phone_digits = re.sub(r'\D', '', sender)
    if not phone_digits:
        return None

    matches = list(_manager(Contact).filter(phone__endswith=phone_digits).order_by('pk')[:2])
    if len(matches) > 1:
        logger.warning('Más de un contacto de comunicaciones coincide con el número %s.', sender)
        return None
    return matches[0] if matches else None


def _case_contact_values(contact: Contact | None, sender: str) -> dict[str, Any]:
    semester = 1
    if contact and contact.semester.isdigit():
        semester = int(contact.semester)

    return {
        'contact_full_name': contact.full_name if contact else sender,
        'contact_document_number': contact.document_number if contact else '',
        'contact_email': contact.email if contact else '',
        'contact_phone': contact.phone if contact and contact.phone else sender,
        'contact_academic_program': (
            contact.academic_program if contact and contact.academic_program else 'Sin definir'
        ),
        'contact_semester': semester,
    }


def _create_case_ticket(
    conversation: ChatConversation,
    sender: str,
    question: str,
    reason: str,
) -> CaseConversation:
    case_conversation, _, _ = ingest_inbound_message(
        InboundPayload(
            channel_code='whatsapp',
            external_thread_id=sender,
            body=question,
            theme=reason[:120],
            **_case_contact_values(conversation.contact, sender),
        )
    )
    conversation.case_conversation = case_conversation
    conversation.escalation_reason = reason
    conversation.escalated_at = timezone.now()
    conversation.status = ChatConversation.STATUS_PENDING
    conversation.flow_state = 'pending'
    conversation.save(update_fields=[
        'case_conversation', 'escalation_reason', 'escalated_at',
        'status', 'flow_state', 'updated_at',
    ])
    return case_conversation


def _ticket_confirmation(conversation: ChatConversation, ticket: CaseConversation) -> str:
    message = f'He creado el ticket {ticket.ticket_number} para que un asesor atienda tu solicitud.'
    conversation.messages.append({
        'author': 'bot',
        'content': message,
        'created_at': timezone.now().isoformat(),
    })
    conversation.save(update_fields=['messages', 'updated_at'])
    return message


def _submit_question(
    workflow: ChatbotWorkflow,
    question: str,
) -> list[str]:
    result = workflow.submit_question(question)
    return [result['message']]


def _case_ticket_is_closed(conversation: ChatConversation) -> bool:
    return (
        conversation.case_conversation_id is not None
        and conversation.case_conversation.status == CaseConversation.Status.CERRADO
    )


def handle_message(sender: str, text: str) -> list[str]:
    contact = _find_contact(sender)
    conversation = _manager(ChatConversation).filter(
        channel='whatsapp',
        external_user_id=sender,
    ).select_related('case_conversation').first()
    start_new_conversation = conversation is None
    inactivity_result = None

    if conversation and _case_ticket_is_closed(conversation):
        conversation.status = ChatConversation.STATUS_ENDED
        conversation.flow_state = 'ended'
        conversation.save(update_fields=['status', 'flow_state', 'updated_at'])
        start_new_conversation = True

    if conversation and conversation.status == ChatConversation.STATUS_ACTIVE:
        inactivity_result = close_if_inactive(conversation)
        if inactivity_result is not None:
            start_new_conversation = True

    if conversation and conversation.status == ChatConversation.STATUS_ENDED:
        start_new_conversation = True

    if start_new_conversation:
        conversation = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id=sender,
            status=ChatConversation.STATUS_ACTIVE,
            contact=contact,
        )

    if contact and not conversation.contact_id:
        conversation.contact = contact
        conversation.save(update_fields=['contact', 'updated_at'])

    workflow = ChatbotWorkflow(conversation)
    if start_new_conversation or not conversation.messages:
        greeting = workflow.start()['message']
        if inactivity_result is not None:
            return [inactivity_result['message'], greeting]
        return [greeting]

    state = conversation.flow_state
    if state == 'waiting_question':
        if _requests_advisor(text):
            return [workflow.escalate('El usuario solicitó atención humana.')['message']]
        return _submit_question(workflow, text)
    if state == 'waiting_confirmation':
        if _requests_advisor(text):
            return [workflow.escalate('El usuario solicitó atención humana después de recibir una respuesta.')['message']]
        if _is_yes(text):
            return [workflow.confirm_more_help(True)['message']]
        if _is_no(text):
            return [workflow.confirm_more_help(False)['message']]
        return ['Respóndeme sí o no: ¿te puedo ayudar en algo más?']
    if state == 'help_options':
        if _requests_advisor(text):
            return [workflow.escalate('El usuario solicitó atención humana después de recibir una respuesta.')['message']]
        return _submit_question(workflow, text)
    if state == 'waiting_advisor_question':
        result = workflow.submit_advisor_question(text)
        if result.get('valid'):
            reason = conversation.escalation_reason or 'El usuario solicitó atención humana.'
            ticket = _create_case_ticket(conversation, sender, text, reason)
            return [result['message'], _ticket_confirmation(conversation, ticket)]
        return [result['message']]
    if state in {'ended', 'pending'}:
        return ['Esta conversación ya está cerrada. Envía un nuevo mensaje para iniciar otra conversación.']
    workflow.start()
    return _submit_question(workflow, text)


def send_text(recipient: str, text: str) -> bool:
    result = send_text_message(recipient, text)
    if not result.success:
        logger.warning(
            'No fue posible enviar la respuesta de WhatsApp a %s: %s',
            recipient,
            result.error,
        )
    return result.success


def process_webhook(payload: dict[str, Any]) -> int:
    processed = 0
    for sender, text in _messages(payload):
        for reply in handle_message(sender, text):
            send_text(sender, reply)
        processed += 1
    return processed


def close_inactive_whatsapp_conversations(current_time: datetime | None = None) -> int:
    current_time = current_time or timezone.now()
    cutoff = current_time - INACTIVITY_TIMEOUT
    conversations = _manager(ChatConversation).filter(
        channel='whatsapp',
        status=ChatConversation.STATUS_ACTIVE,
        updated_at__lte=cutoff,
    )
    closed_count = 0
    for conversation in conversations.iterator():
        result = close_if_inactive(conversation, current_time)
        if result is None:
            continue
        send_text(conversation.external_user_id, result['message'])
        closed_count += 1
    return closed_count


def parse_json(raw_body: bytes) -> dict[str, Any]:
    return json.loads(raw_body.decode('utf-8') or '{}')
