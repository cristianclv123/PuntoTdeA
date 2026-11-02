"""Adaptador de WhatsApp Cloud API para el flujo conversacional."""

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from communications.adapters.meta_adapter import (
    send_image_message,
    send_interactive_buttons,
    send_interactive_list,
    send_text_message,
    send_uploaded_image_message,
    upload_whatsapp_media,
)
from communications.models import Contact
from cases.models import Conversation as CaseConversation
from cases.services.ingestion import InboundPayload, ingest_inbound_message
from ..models import ChatConversation, FAQ
from .case_status import CaseStatusAPIError, get_case_status
from .inactivity import (
    INACTIVITY_CLOSE_TIMEOUT,
    INACTIVITY_WARNING_TIMEOUT,
    backfill_last_user_activity,
    close_expired_conversation,
    close_if_inactive,
    warn_if_inactive,
)
from .schedule import get_business_schedule
from .workflow import FOLLOW_UP_MESSAGE, ChatbotWorkflow


logger = logging.getLogger(__name__)

# Identificadores estables de las opciones interactivas. El webhook recibe el
# ``id`` y no depende del texto visible (que puede cambiar sin romper el flujo).
CHAT_MORE = 'chat_more'
CHAT_ADVISOR = 'chat_advisor'
CHAT_FINISH = 'chat_finish'
LOW_CONFIDENCE_ADVISOR = 'lowconf_advisor'
LOW_CONFIDENCE_QUESTION = 'lowconf_question'
HELP_QUESTION = 'help_question'
HELP_ADVISOR = 'help_advisor'

CONFIRMATION_BUTTONS = [
    {'id': CHAT_MORE, 'title': 'Otra consulta'},
    {'id': CHAT_ADVISOR, 'title': 'Hablar con asesor'},
    {'id': CHAT_FINISH, 'title': 'Finalizar'},
]

LOW_CONFIDENCE_BUTTONS = [
    {'id': LOW_CONFIDENCE_ADVISOR, 'title': 'Sí, asesor'},
    {'id': LOW_CONFIDENCE_QUESTION, 'title': 'No, otra pregunta'},
]

HELP_BUTTONS = [
    {'id': HELP_QUESTION, 'title': 'Escribir pregunta'},
    {'id': HELP_ADVISOR, 'title': 'Hablar con asesor'},
]

# Motivo que se guarda cuando la baja confianza deriva en un asesor. Permite
# adjuntar la pregunta original al ticket sin perder el contexto.
LOW_CONFIDENCE_REASON = 'El chatbot no encontró una respuesta con suficiente confianza.'

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
    """Itera mensajes entrantes textuales e interactivos.

    Devuelve ``(sender, text, external_message_id, interactive_id)``. En los
    mensajes interactivos ``text`` es el título visible (para compatibilidad
    con las respuestas de texto) e ``interactive_id`` es el identificador
    estable del botón o de la fila de la lista.
    """
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value') or {}
            for message in value.get('messages') or []:
                message_type = message.get('type')
                sender = (message.get('from') or '').strip()
                external_message_id = (message.get('id') or '').strip()
                if not sender:
                    continue

                if message_type == 'text':
                    text = ((message.get('text') or {}).get('body') or '').strip()
                    if text:
                        yield sender, text, external_message_id, ''
                    continue

                if message_type != 'interactive':
                    continue

                interactive = message.get('interactive') or {}
                kind = interactive.get('type')
                if kind not in {'button_reply', 'list_reply'}:
                    continue
                data = interactive.get(kind) or {}
                choice_id = (data.get('id') or '').strip()
                title = (data.get('title') or '').strip()
                if choice_id or title:
                    yield sender, title, external_message_id, choice_id


def _is_yes(text: str) -> bool:
    return text.lower().strip() in {'si', 'sí', 's', 'yes'}


def _is_no(text: str) -> bool:
    return text.lower().strip() in {'no', 'n'}


def _is_finish(text: str) -> bool:
    return text.lower().strip() in {
        'no',
        'n',
        'finalizar',
        'terminar',
        'finalizar conversación',
        'finalizar conversacion',
    }


def _is_more_question(text: str) -> bool:
    return text.lower().strip() in {
        'si',
        'sí',
        's',
        'yes',
        'otra consulta',
        'otra pregunta',
        'no, otra pregunta',
        'continuar',
        'escribir pregunta',
    }


def _requests_advisor(text: str) -> bool:
    normalized = text.lower()
    return any(word in normalized for word in ('asesor', 'humano', 'persona'))


def _choice_alias(state: str, text: str) -> str:
    """Traduce el número de la opción cuando el envío interactivo falla.

    El respaldo de botones/lista envía las opciones numeradas. Si el usuario
    responde con ese número, se reutiliza la misma acción del botón.
    """
    aliases = {
        'waiting_confirmation': {
            '1': CHAT_MORE,
            '2': CHAT_ADVISOR,
            '3': CHAT_FINISH,
        },
        'waiting_low_confidence_choice': {
            '1': LOW_CONFIDENCE_ADVISOR,
            '2': LOW_CONFIDENCE_QUESTION,
        },
        'help_options': {
            '1': HELP_QUESTION,
            '2': HELP_ADVISOR,
        },
    }
    return aliases.get(state, {}).get((text or '').strip(), '')


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
    if not get_business_schedule().is_open():
        message += (
            ' Nuestro horario de atención es de lunes a viernes, '
            'de 8:00 a. m. a 5:00 p. m. Tu solicitud será atendida dentro de ese horario.'
        )
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
            '¿Deseas comunicarte con un asesor?'
        )
        conversation.flow_state = 'waiting_low_confidence_choice'
        conversation.messages[-1]['content'] = follow_up
        conversation.messages[-1].pop('awaiting_advisor', None)
        conversation.messages[-1].pop('image_url', None)
        conversation.messages[-1].pop('image_source_id', None)
        conversation.messages[-1].pop('source_question', None)
        conversation.save(update_fields=['messages', 'flow_state', 'updated_at'])
        return [{'text': follow_up, 'buttons': LOW_CONFIDENCE_BUTTONS}]
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
        replies.append({
            'text': result['follow_up_message'],
            'buttons': CONFIRMATION_BUTTONS,
        })
        return replies
    return [{'text': result['message']}]


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


def _append_bot_prompt(
    conversation: ChatConversation,
    message: str,
    state: str | None = None,
) -> None:
    conversation.messages.append({
        'author': 'bot',
        'content': message,
        'created_at': timezone.now().isoformat(),
    })
    update_fields = ['messages', 'updated_at']
    if state is not None:
        conversation.flow_state = state
        update_fields.append('flow_state')
    conversation.save(update_fields=update_fields)


def _handle_interactive_choice(
    conversation: ChatConversation,
    workflow: ChatbotWorkflow,
    sender: str,
    choice_id: str,
) -> list[str | dict[str, Any]] | None:
    """Ejecuta la acción del botón o fila de lista seleccionada.

    Devuelve ``None`` cuando el ``id`` no pertenece al estado actual; en ese
    caso el llamador responde con un recordatorio en vez de interpretar el
    título como una pregunta nueva.
    """
    state = conversation.flow_state

    if state == 'waiting_confirmation':
        if choice_id == CHAT_FINISH:
            return [workflow.confirm_more_help(False)['message']]
        if choice_id == CHAT_ADVISOR:
            return [workflow.escalate(
                'El usuario solicitó atención humana después de recibir una respuesta.'
            )['message']]
        if choice_id == CHAT_MORE:
            message = workflow.confirm_more_help(True)['message']
            return [{'text': message, 'buttons': HELP_BUTTONS}]

    elif state == 'waiting_low_confidence_choice':
        if choice_id == LOW_CONFIDENCE_ADVISOR:
            return [workflow.escalate(LOW_CONFIDENCE_REASON)['message']]
        if choice_id == LOW_CONFIDENCE_QUESTION:
            message = (
                'De acuerdo. Escribe tu nueva pregunta y la buscaré en la base '
                'de conocimiento.'
            )
            _append_bot_prompt(conversation, message, 'waiting_question')
            return [message]

    elif state == 'help_options':
        if choice_id == HELP_ADVISOR:
            return [workflow.escalate(
                'El usuario solicitó atención humana después de recibir una respuesta.'
            )['message']]
        if choice_id == HELP_QUESTION:
            message = 'Escribe tu pregunta y la buscaré en la base de conocimiento.'
            _append_bot_prompt(conversation, message)
            return [message]

    return None


def _stale_interactive_reply(conversation: ChatConversation) -> list[str | dict[str, Any]]:
    """Respuesta para una selección que ya no corresponde al estado actual."""
    state = conversation.flow_state
    if state == 'waiting_confirmation':
        return [{'text': FOLLOW_UP_MESSAGE, 'buttons': CONFIRMATION_BUTTONS}]
    if state == 'waiting_low_confidence_choice':
        return [{
            'text': '¿Deseas comunicarte con un asesor?',
            'buttons': LOW_CONFIDENCE_BUTTONS,
        }]
    if state == 'help_options':
        return [{
            'text': 'Puedes escribir tu pregunta o elegir una opción.',
            'buttons': HELP_BUTTONS,
        }]
    if state == 'waiting_question':
        return ['Escribe tu pregunta y la buscaré en la base de conocimiento.']
    return ['Tu selección ya no está disponible. Escribe tu mensaje para continuar.']


def handle_message(
    sender: str,
    text: str,
    external_message_id: str = '',
    interactive_id: str = '',
) -> list[str | dict[str, Any]]:
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
    expired_result = None
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
        expired_result = close_expired_conversation(conversation)
        if expired_result is not None:
            start_new_conversation = True
        else:
            # Cada mensaje entrante reinicia el ciclo y cancela un cierre que
            # estuviera pendiente después del aviso de inactividad.
            now = timezone.now()
            conversation.last_user_activity_at = now
            conversation.inactivity_warned_at = None
            conversation.save(update_fields=[
                'last_user_activity_at',
                'inactivity_warned_at',
                'updated_at',
            ])

    if conversation and conversation.status == ChatConversation.STATUS_ENDED:
        start_new_conversation = True

    if start_new_conversation:
        conversation = _manager(ChatConversation).create(
            channel='whatsapp',
            external_user_id=sender,
            status=ChatConversation.STATUS_ACTIVE,
            contact=contact,
            last_user_activity_at=timezone.now(),
        )

    if contact and not conversation.contact_id:
        conversation.contact = contact
        conversation.save(update_fields=['contact', 'updated_at'])

    workflow = ChatbotWorkflow(conversation)
    new_conversation = start_new_conversation or not conversation.messages
    greeting = None
    if new_conversation:
        greeting = workflow.start()['message']
        if expired_result is not None:
            return [expired_result['message'], greeting]
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

    if interactive_id:
        handled = _handle_interactive_choice(
            conversation,
            workflow,
            sender,
            interactive_id,
        )
        if handled is not None:
            return handled
        return _stale_interactive_reply(conversation)

    alias = _choice_alias(conversation.flow_state, text)
    if alias:
        handled = _handle_interactive_choice(
            conversation,
            workflow,
            sender,
            alias,
        )
        if handled is not None:
            return handled

    state = conversation.flow_state
    if state == 'waiting_question':
        if _requests_advisor(text):
            replies = [workflow.escalate('El usuario solicitó atención humana.')['message']]
        else:
            replies = _submit_question(conversation, workflow, text)
        return replies
    if state == 'waiting_low_confidence_choice':
        if _is_yes(text) or _requests_advisor(text):
            return [workflow.escalate(LOW_CONFIDENCE_REASON)['message']]
        if _is_no(text) or _is_more_question(text):
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
        if _is_more_question(text):
            message = workflow.confirm_more_help(True)['message']
            return [{'text': message, 'buttons': HELP_BUTTONS}]
        if _is_finish(text):
            return [workflow.confirm_more_help(False)['message']]
        return [{
            'text': FOLLOW_UP_MESSAGE,
            'buttons': CONFIRMATION_BUTTONS,
        }]
    if state == 'help_options':
        if _requests_advisor(text):
            return [workflow.escalate('El usuario solicitó atención humana después de recibir una respuesta.')['message']]
        if _is_more_question(text):
            return [{
                'text': 'Escribe tu pregunta y la buscaré en la base de conocimiento.',
                'buttons': HELP_BUTTONS,
            }]
        return _submit_question(conversation, workflow, text)
    if state == 'waiting_advisor_question':
        result = workflow.submit_advisor_question(text)
        if result.get('valid'):
            reason = conversation.escalation_reason or 'El usuario solicitó atención humana.'
            body = text
            if (
                conversation.last_question
                and conversation.escalation_reason == LOW_CONFIDENCE_REASON
            ):
                # La ruta de baja confianza no pudo responder la pregunta
                # original; la adjuntamos para que el asesor tenga el contexto.
                body = f'{text}\n\nPregunta original: {conversation.last_question}'
            ticket = _create_case_ticket(
                conversation, sender, body, reason, external_message_id,
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
    """
    text = (text or '').strip()
    if _URL_PATTERN.search(text):
        send_text(recipient, text, preview_url=True)
        return
    send_text(recipient, text)


def _buttons_as_text(text: str, buttons: list[dict[str, str]]) -> str:
    """Respaldo legible si WhatsApp rechaza el mensaje interactivo."""
    options = '\n'.join(
        f'{index}. {button.get("title", "")}'
        for index, button in enumerate(buttons, start=1)
    )
    return f'{text}\n\n{options}'


def _list_as_text(
    text: str,
    button_label: str,
    sections: list[dict[str, Any]],
) -> str:
    lines = [text, f'\n{button_label}:']
    for section in sections:
        title = (section.get('title') or '').strip()
        if title:
            lines.append(f'\n{title}')
        for row in section.get('rows') or []:
            lines.append(f'- {row.get("title", "")}')
    return '\n'.join(lines)


def _send_options(recipient: str, reply: dict[str, Any]) -> bool:
    """Envía botones o lista y devuelve ``True`` si el mensaje era interactivo.

    Si Meta rechaza el interactivo, cae a un texto con las mismas opciones para
    no dejar al usuario sin respuesta.
    """
    text = reply.get('text', '')
    buttons = reply.get('buttons') or []
    list_payload = reply.get('list') or {}

    if buttons:
        result = send_interactive_buttons(recipient, text, buttons)
        if not result.success:
            logger.warning(
                'No fue posible enviar botones a %s: %s. Se envía texto de respaldo.',
                recipient,
                result.error,
            )
            send_text(recipient, _buttons_as_text(text, buttons))
        return True

    if list_payload:
        button_label = list_payload.get('button') or 'Ver opciones'
        sections = list_payload.get('sections') or []
        result = send_interactive_list(
            recipient,
            text,
            button_label,
            sections,
            header_text=list_payload.get('header_text', ''),
            footer_text=list_payload.get('footer_text', ''),
        )
        if not result.success:
            logger.warning(
                'No fue posible enviar la lista a %s: %s. Se envía texto de respaldo.',
                recipient,
                result.error,
            )
            send_text(recipient, _list_as_text(text, button_label, sections))
        return True

    return False


def _send_reply(recipient: str, reply: dict[str, Any]) -> None:
    """Envía un mensaje estructurado que puede incluir imagen de una FAQ.

    Si ``reply`` contiene ``image_faq_id``, sube la imagen a Meta para obtener
    un ``media_id`` y la envía como mensaje de imagen antes que el texto.
    """
    image_faq_id = reply.get('image_faq_id')
    text = reply.get('text', '')
    is_interactive = bool(reply.get('buttons') or reply.get('list'))
    if image_faq_id:
        faq = _manager(FAQ).filter(pk=image_faq_id).first()
        if faq is None:
            logger.warning('FAQ %s no encontrada para enviar imagen.', image_faq_id)
        else:
            image_bytes = faq.get_image_bytes()
            if not image_bytes:
                logger.warning('FAQ %s no tiene imagen en BD a pesar del flag.', image_faq_id)
            else:
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
                else:
                    # Con opciones interactivas, el texto va en el interactivo
                    # para no duplicarlo en el pie de la imagen.
                    caption = '' if is_interactive else (text or '').strip()
                    image_result = send_uploaded_image_message(
                        recipient,
                        upload_result.provider_message_id,
                        caption=caption,
                    )
                    if image_result.success:
                        if is_interactive:
                            _send_options(recipient, reply)
                        return
                    logger.warning(
                        'No fue posible enviar imagen de FAQ %s a %s: %s',
                        image_faq_id,
                        recipient,
                        image_result.error,
                    )
    if _send_options(recipient, reply):
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
) -> None:
    """Envía las respuestas del flujo sin cambiar su orden y adjunta la FAQ coincidente."""
    faq = _question_image(sender, question)
    image_sent = False
    for index, reply in enumerate(replies):
        if isinstance(reply, dict):
            _send_reply(sender, reply)
            continue
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
            send_text(sender, reply)


def process_webhook(payload: dict[str, Any]) -> int:
    processed = 0
    for sender, text, external_message_id, interactive_id in _messages(payload):
        replies = handle_message(
            sender,
            text,
            external_message_id=external_message_id,
            interactive_id=interactive_id,
        )
        for reply in replies:
            if isinstance(reply, dict):
                _send_reply(sender, reply)
            else:
                _send_text_with_link_preview(sender, reply)
        processed += 1
    return processed


def process_inactivity(current_time: datetime | None = None) -> dict[str, int]:
    """Procesa el ciclo 5 + 2 minutos para las conversaciones de WhatsApp.

    Pensado para ejecutarse periódicamente (cada minuto). El primer paso envía
    el aviso; el segundo cierra las conversaciones que no respondieron. Los
    ``UPDATE`` condicionales de ``warn_if_inactive`` y ``close_if_inactive``
    evitan avisos y cierres duplicados entre procesos.
    """
    current_time = current_time or timezone.now()
    backfill_last_user_activity()
    summary = {'warned': 0, 'closed': 0}

    warning_cutoff = current_time - INACTIVITY_WARNING_TIMEOUT
    service_window_start = current_time - timedelta(hours=24)
    pending_warning = _manager(ChatConversation).filter(
        channel='whatsapp',
        status=ChatConversation.STATUS_ACTIVE,
        inactivity_warned_at__isnull=True,
        last_user_activity_at__lte=warning_cutoff,
        # Fuera de la ventana de 24 h de Meta no se puede enviar texto libre.
        last_user_activity_at__gte=service_window_start,
    ).order_by('pk')
    for conversation in pending_warning.iterator():
        result = warn_if_inactive(conversation, current_time)
        if result is None:
            continue
        if send_text(conversation.external_user_id, result['message']):
            summary['warned'] += 1
        else:
            # Si Meta rechazó el aviso, liberar el reclamo para reintentarlo en
            # la siguiente pasada en vez de cerrar sin haber avisado.
            _manager(ChatConversation).filter(
                pk=conversation.pk,
                inactivity_warned_at=current_time,
            ).update(inactivity_warned_at=None)

    closing_cutoff = current_time - INACTIVITY_CLOSE_TIMEOUT
    pending_close = _manager(ChatConversation).filter(
        channel='whatsapp',
        status=ChatConversation.STATUS_ACTIVE,
        inactivity_warned_at__isnull=False,
        inactivity_warned_at__lte=closing_cutoff,
        last_user_activity_at__lte=F('inactivity_warned_at'),
    ).order_by('pk')
    for conversation in pending_close.iterator():
        result = close_if_inactive(conversation, current_time)
        if result is None:
            continue
        if (
            conversation.last_user_activity_at
            and conversation.last_user_activity_at >= service_window_start
        ):
            send_text(conversation.external_user_id, result['message'])
        summary['closed'] += 1

    return summary


def close_inactive_whatsapp_conversations(current_time: datetime | None = None) -> int:
    """Compatibilidad: devuelve solo cuántas conversaciones se cerraron."""
    return process_inactivity(current_time)['closed']


def parse_json(raw_body: bytes) -> dict[str, Any]:
    return json.loads(raw_body.decode('utf-8') or '{}')
