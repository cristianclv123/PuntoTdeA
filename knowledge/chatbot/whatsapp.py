"""Adaptador de WhatsApp Cloud API para el flujo conversacional."""

import hashlib
import hmac
import json
import logging
import re
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

from communications.models import Contact
from cases.models import Conversation as CaseConversation
from cases.services.ingestion import InboundPayload, ingest_inbound_message
from ..models import ChatConversation
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
        return True
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
    conversation: ChatConversation,
    workflow: ChatbotWorkflow,
    sender: str,
    question: str,
) -> list[str]:
    result = workflow.submit_question(question)
    if result.get('valid') and result.get('needs_human_attention'):
        reason = 'El chatbot no encontró una respuesta con suficiente confianza.'
        ticket = _create_case_ticket(conversation, sender, question, reason)
        return [result['message'], _ticket_confirmation(conversation, ticket)]
    return [result['message']]


def handle_message(sender: str, text: str) -> list[str]:
    contact = _find_contact(sender)
    conversation, created = _manager(ChatConversation).get_or_create(
        channel='whatsapp',
        external_user_id=sender,
        defaults={'status': ChatConversation.STATUS_ACTIVE, 'contact': contact},
    )
    if contact and not conversation.contact_id:
        conversation.contact = contact
        conversation.save(update_fields=['contact', 'updated_at'])

    workflow = ChatbotWorkflow(conversation)
    if created or not conversation.messages:
        return [workflow.start()['message']]

    state = conversation.flow_state
    if state == 'waiting_question':
        if _requests_advisor(text):
            return [workflow.escalate('El usuario solicitó atención humana.')['message']]
        return _submit_question(conversation, workflow, sender, text)
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
        return _submit_question(conversation, workflow, sender, text)
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
    return _submit_question(conversation, workflow, sender, text)


def send_text(recipient: str, text: str) -> bool:
    token = getattr(settings, 'META_ACCESS_TOKEN', '')
    phone_number_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
    api_version = getattr(settings, 'WHATSAPP_API_VERSION', 'v21.0')
    if not token or not phone_number_id:
        logger.warning('WhatsApp no está configurado; se omite el envío a %s.', recipient)
        return False
    try:
        response = requests.post(
            f'https://graph.facebook.com/{api_version}/{phone_number_id}/messages',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            json={
                'messaging_product': 'whatsapp',
                'to': recipient,
                'type': 'text',
                'text': {'body': text},
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception('No fue posible enviar la respuesta de WhatsApp a %s.', recipient)
        return False
    return True


def process_webhook(payload: dict[str, Any]) -> int:
    processed = 0
    for sender, text in _messages(payload):
        for reply in handle_message(sender, text):
            send_text(sender, reply)
        processed += 1
    return processed


def parse_json(raw_body: bytes) -> dict[str, Any]:
    return json.loads(raw_body.decode('utf-8') or '{}')