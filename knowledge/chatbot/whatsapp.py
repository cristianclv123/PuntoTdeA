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

from communications.adapters.meta_adapter import (
    send_image_message,
    send_uploaded_image_message,
    send_text_message,
    upload_whatsapp_media,
)
from communications.models import Contact
from cases.models import Conversation as CaseConversation
from cases.services.ingestion import InboundPayload, ingest_inbound_message
from ..models import ChatConversation, FAQ
from .case_status import CaseStatusAPIError, get_case_status
from .inactivity import INACTIVITY_TIMEOUT, close_if_inactive
from .workflow import FOLLOW_UP_MESSAGE, ChatbotWorkflow


logger = logging.getLogger(__name__)

INACTIVITY_NOTICE = (
    'Si no recibimos respuesta, el chat se cerrará automáticamente '
    'después de 5 minutos de inactividad.'
)

# Patrón para detectar URLs en un mensaje de texto. Cuando una respuesta
# contiene una URL, se envía como mensaje aparte para que WhatsApp genere
# la preview automática (miniatura + título del sitio).
_URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)


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
                    yield sender, text, (message.get('id') or '').strip()


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


def _forward_inbound_to_case(
    conversation: ChatConversation,
    sender: str,
    text: str,
    external_message_id: str = '',
) -> CaseConversation:
    case_conversation = conversation.case_conversation
    if case_conversation is None:
        raise ValueError('La conversación no tiene un ticket asociado.')

    case_conversation, _, _ = ingest_inbound_message(
        InboundPayload(
            channel_code='whatsapp',
            external_thread_id=case_conversation.external_thread_id,
            body=text,
            external_message_id=external_message_id,
            theme=(conversation.escalation_reason or '')[:120],
            **_case_contact_values(conversation.contact, sender),
        )
    )

    if conversation.case_conversation_id != case_conversation.pk:
        conversation.case_conversation = case_conversation
        conversation.save(update_fields=['case_conversation', 'updated_at'])

    return case_conversation


def _create_case_ticket(
    conversation: ChatConversation,
    sender: str,
    question: str,
    reason: str,
    external_message_id: str = '',
) -> CaseConversation:
    case_thread_id = sender
    previous_case = _manager(CaseConversation).filter(
        channel__code='whatsapp',
        external_thread_id=sender,
    ).order_by('-updated_at').first()
    if previous_case and previous_case.status == CaseConversation.Status.CERRADO:
        case_thread_id = f'{sender}:chat-{conversation.pk}'

    case_conversation, _, _ = ingest_inbound_message(
        InboundPayload(
            channel_code='whatsapp',
            external_thread_id=case_thread_id,
            body=question,
            external_message_id=external_message_id,
            theme=reason[:120],
            **_case_contact_values(conversation.contact, sender),
        )
    )
    conversation.case_conversation = case_conversation
    conversation.escalation_reason = reason
    conversation.escalated_at = timezone.now()
    conversation.status = ChatConversation.STATUS_ACTIVE
    conversation.flow_state = 'help_options'
    conversation.save(update_fields=[
        'case_conversation',
        'escalation_reason',
        'escalated_at',
        'status',
        'flow_state',
        'updated_at',
    ])
    return case_conversation


def _ticket_confirmation(conversation: ChatConversation, ticket: CaseConversation) -> str:
    message = f'He creado el ticket {ticket.ticket_number} para que un asesor atienda tu solicitud.'
    conversation.messages.append({
        'author': 'bot',
        'content': message,
        'created_at': timezone.now().isoformat(),
        'awaiting_advisor': True,
    })
    conversation.save(update_fields=['messages', 'updated_at'])
    return message


def _submit_question(
    conversation: ChatConversation,
    workflow: ChatbotWorkflow,
    question: str,
) -> list[dict[str, Any]]:
    result = workflow.submit_question(question)
    if result.get('valid') and result.get('needs_human_attention'):
        follow_up = (
            'No encontré una respuesta confiable a tu pregunta. '
            '¿Deseas comunicarte con un asesor? Responde sí para crear un ticket '
            'o no para escribir una nueva pregunta.'
        )
        conversation.flow_state = 'waiting_low_confidence_choice'
        conversation.messages[-1]['content'] = follow_up
        conversation.messages[-1].pop('awaiting_advisor', None)
        conversation.messages[-1].pop('image_url', None)
        conversation.messages[-1].pop('image_source_id', None)
        conversation.messages[-1].pop('source_question', None)
        conversation.save(update_fields=['messages', 'flow_state', 'updated_at'])
        return [{'text': follow_up}]
    image_faq_id = (
        result.get('image_faq_id') or result.get('image_source_id')
        if result.get('valid')
        else None
    )
    if result.get('valid') and result.get('follow_up_message') == FOLLOW_UP_MESSAGE:
        replies = []
        if image_faq_id:
            replies.append({'text': result['answer_message'], 'image_faq_id': image_faq_id})
        else:
            replies.append({'text': result['answer_message']})
        replies.append({'text': result['follow_up_message']})
        return replies
    return [{'text': result['message']}]


def _create_low_confidence_ticket(conversation: ChatConversation, sender: str) -> str:
    reason = 'El chatbot no encontró una respuesta con suficiente confianza.'
    ticket = _create_case_ticket(
        conversation,
        sender,
        conversation.last_question,
        reason,
    )
    return _ticket_confirmation(conversation, ticket)


def _case_ticket_status(conversation: ChatConversation) -> str | None:
    if conversation.case_conversation_id is None:
        return None
    try:
        status = get_case_status(conversation.case_conversation_id)
    except CaseStatusAPIError as exc:
        logger.warning(
            'No se pudo consultar el estado remoto del ticket %s; se usará el estado local: %s',
            conversation.case_conversation_id,
            exc,
        )
        return conversation.case_conversation.status
    return status


def handle_message(
    sender: str,
    text: str,
    external_message_id: str = '',
) -> list[str]:
    contact = _find_contact(sender)
    conversations = _manager(ChatConversation).filter(
        channel='whatsapp',
        external_user_id=sender,
    ).select_related('case_conversation')
    conversation = conversations.filter(
        status=ChatConversation.STATUS_ACTIVE,
    ).order_by('-updated_at', '-created_at').first()
    if conversation is None:
        conversation = conversations.order_by('-updated_at', '-created_at').first()
    start_new_conversation = conversation is None
    inactivity_result = None
    ticket_status = _case_ticket_status(conversation) if conversation else None

    if conversation and ticket_status == CaseConversation.Status.CERRADO:
        conversation.status = ChatConversation.STATUS_ENDED
        conversation.flow_state = 'ended'
        conversation.save(update_fields=['status', 'flow_state', 'updated_at'])
        start_new_conversation = True

    if (
        conversation
        and conversation.case_conversation_id is not None
        and ticket_status is not None
        and ticket_status != CaseConversation.Status.CERRADO
    ):
        is_pending = (
            conversation.status == ChatConversation.STATUS_PENDING
            or conversation.flow_state == 'pending'
        )
        if not is_pending and (
            conversation.status == ChatConversation.STATUS_ENDED
            or conversation.flow_state == 'ended'
        ):
            conversation.status = ChatConversation.STATUS_ACTIVE
            conversation.flow_state = 'help_options'
            conversation.save(update_fields=['status', 'flow_state', 'updated_at'])
    elif conversation and (
        conversation.status in {
            ChatConversation.STATUS_ENDED,
            ChatConversation.STATUS_PENDING,
        }
        or conversation.flow_state in {'ended', 'pending'}
    ):
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
    new_conversation = start_new_conversation or not conversation.messages
    greeting = None
    if new_conversation:
        greeting = workflow.start()['message']
        if inactivity_result is not None:
            return [inactivity_result['message'], greeting]
        return [greeting]

    if (
        conversation.case_conversation_id is not None
        and ticket_status != CaseConversation.Status.CERRADO
    ):
        _forward_inbound_to_case(
            conversation,
            sender,
            text,
            external_message_id,
        )
        return []

    state = conversation.flow_state
    if state == 'waiting_question':
        if _requests_advisor(text):
            replies = [workflow.escalate('El usuario solicitó atención humana.')['message']]
        else:
            replies = _submit_question(conversation, workflow, text)
        if new_conversation and greeting:
            replies.insert(0, greeting)
        if inactivity_result is not None:
            replies.insert(0, inactivity_result['message'])
        return replies
    if state == 'waiting_low_confidence_choice':
        if _is_yes(text) or _requests_advisor(text):
            return [_create_low_confidence_ticket(conversation, sender)]
        if _is_no(text):
            message = 'De acuerdo. Escribe tu nueva pregunta y la buscaré en la base de conocimiento.'
            conversation.flow_state = 'waiting_question'
            conversation.messages.append({
                'author': 'bot',
                'content': message,
                'created_at': timezone.now().isoformat(),
            })
            conversation.save(update_fields=['messages', 'flow_state', 'updated_at'])
            return [message]
        return _submit_question(conversation, workflow, text)
    if state == 'waiting_confirmation':
        if _requests_advisor(text):
            return [workflow.escalate('El usuario solicitó atención humana después de recibir una respuesta.')['message']]
        if _is_yes(text):
            return [workflow.confirm_more_help(True)['message']]
        if _is_no(text):
            return [workflow.confirm_more_help(False)['message']]
        return ['Responde sí si necesitas otra pregunta o un asesor, o no si ya quedó resuelta tu duda.']
    if state == 'help_options':
        if _requests_advisor(text):
            return [workflow.escalate('El usuario solicitó atención humana después de recibir una respuesta.')['message']]
        return _submit_question(conversation, workflow, text)
    if state == 'waiting_advisor_question':
        result = workflow.submit_advisor_question(text)
        if result.get('valid'):
            reason = conversation.escalation_reason or 'El usuario solicitó atención humana.'
            ticket = _create_case_ticket(
                conversation, sender, text, reason, external_message_id,
            )
            return [result['message'], _ticket_confirmation(conversation, ticket)]
        return [result['message']]
    if state == 'ended':
        return ['Esta conversación ya está cerrada. Envía un nuevo mensaje para iniciar otra conversación.']
    workflow.start()
    return _submit_question(conversation, workflow, text)


def send_text(recipient: str, text: str, *, preview_url: bool = False) -> bool:
    """Envía un mensaje de texto por WhatsApp Cloud API.

    Si ``preview_url=True``, se incluye en el payload para que WhatsApp genere
    automáticamente la preview (miniatura) de la primera URL del cuerpo.
    """
    result = send_text_message(recipient, text, preview_url=preview_url)
    if not result.success:
        logger.warning(
            'No fue posible enviar la respuesta de WhatsApp a %s: %s',
            recipient,
            result.error,
        )
    return result.success


def _send_text_with_link_preview(recipient: str, text: str) -> None:
    """Envía texto y, si contiene URLs, activa ``preview_url`` para la miniatura.

    WhatsApp Cloud API soporta el parámetro ``preview_url: true`` en el body del
    mensaje de texto. Cuando está presente, WhatsApp intenta generar la preview
    (miniatura + título) de la primera URL que encuentre en el cuerpo, incluso
    si hay más texto alrededor.

    Si el texto contiene una URL, se envía con ``preview_url=True`` en el
    mismo mensaje de texto (con el aviso de inactividad anexado, que no
    interfiere con la preview).

    Si no contiene URL, se envía como texto normal.
    """
    text = (text or '').strip()
    urls = _URL_PATTERN.findall(text)
    if urls:
        # La URL va en el cuerpo con preview_url para que se genere la miniatura.
        send_text(recipient, f'{text}\n\n{INACTIVITY_NOTICE}', preview_url=True)
        return
    # Sin URLs: texto normal.
    send_text(recipient, f'{text}\n\n{INACTIVITY_NOTICE}')


def _send_reply(recipient: str, reply: dict[str, Any]) -> None:
    """Envía un mensaje estructurado que puede incluir imagen de una FAQ.

    Si ``reply`` contiene ``image_faq_id``, sube la imagen a Meta para obtener
    un ``media_id`` y la envía como mensaje de imagen antes que el texto.
    """
    image_faq_id = reply.get('image_faq_id')
    text = reply.get('text', '')
    if image_faq_id:
        faq = _manager(FAQ).filter(pk=image_faq_id).first()
        if faq is None:
            logger.warning('FAQ %s no encontrada para enviar imagen.', image_faq_id)
            send_text(recipient, f'{text}\n\n{INACTIVITY_NOTICE}')
            return
        image_bytes = faq.get_image_bytes()
        if not image_bytes:
            logger.warning('FAQ %s no tiene imagen en BD a pesar del flag.', image_faq_id)
            send_text(recipient, f'{text}\n\n{INACTIVITY_NOTICE}')
            return
        upload_result = upload_whatsapp_media(
            image_bytes,
            filename=faq.image_name or 'imagen.jpg',
            content_type=faq.image_content_type or 'image/jpeg',
        )
        if not upload_result.success:
            logger.warning(
                'No fue posible subir imagen de FAQ %s a Meta: %s',
                image_faq_id,
                upload_result.error,
            )
            send_text(recipient, f'{text}\n\n{INACTIVITY_NOTICE}')
            return
        caption = (text or '').strip()
        image_result = send_uploaded_image_message(
            recipient,
            upload_result.provider_message_id,
            caption=caption,
        )
        if not image_result.success:
            logger.warning(
                'No fue posible enviar imagen de FAQ %s a %s: %s',
                image_faq_id,
                recipient,
                image_result.error,
            )
            send_text(recipient, f'{text}\n\n{INACTIVITY_NOTICE}')
            return
        # La imagen ya incluye el caption; el aviso de inactividad va aparte.
        if INACTIVITY_NOTICE:
            send_text(recipient, INACTIVITY_NOTICE)
        return
    _send_text_with_link_preview(recipient, text)


def send_image(
    recipient: str,
    image_data: bytes,
    filename: str,
    content_type: str,
    caption: str = '',
) -> bool:
    result = send_image_message(
        recipient,
        image_data,
        filename,
        content_type,
        caption,
    )
    if not result.success:
        logger.warning(
            'No fue posible enviar la imagen de WhatsApp a %s: %s',
            recipient,
            result.error,
        )
    return result.success


def _question_image(sender: str, question: str) -> FAQ | None:
    conversation = _manager(ChatConversation).filter(
        channel='whatsapp',
        external_user_id=sender,
    ).order_by('-updated_at', '-created_at').first()
    if conversation is None or conversation.last_question != question:
        return None
    for message in reversed(conversation.messages):
        image_source_id = message.get('image_source_id')
        if message.get('source_question') == question and image_source_id:
            faq = _manager(FAQ).filter(pk=image_source_id, is_active=True).first()
            if faq and faq.has_image:
                return faq
    return None


def send_replies(
    sender: str,
    question: str,
    replies: list[str | dict[str, Any]],
    add_inactivity_notice: bool = False,
) -> None:
    """Envía las respuestas del flujo sin cambiar su orden y adjunta la FAQ coincidente."""
    faq = _question_image(sender, question)
    image_sent = False
    for index, reply in enumerate(replies):
        if isinstance(reply, dict):
            _send_reply(sender, reply)
            continue
        text_message = (
            f'{reply}\n\n{INACTIVITY_NOTICE}' if add_inactivity_notice else reply
        )
        if index == 0 and faq:
            image_sent = send_image(
                sender,
                faq.get_image_bytes() or b'',
                faq.image_name,
                faq.image_content_type,
                reply[:1024],
            )
            if image_sent and len(reply) > 1024:
                send_text(sender, reply[1024:])
        if index > 0 or not image_sent:
                send_text(sender, text_message)


def process_webhook(payload: dict[str, Any]) -> int:
    processed = 0
    for sender, text, external_message_id in _messages(payload):
        replies = handle_message(
            sender,
            text,
            external_message_id=external_message_id,
        )
        for reply in replies:
            if isinstance(reply, dict):
                _send_reply(sender, reply)
            else:
                _send_text_with_link_preview(sender, reply)
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
