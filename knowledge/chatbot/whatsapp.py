"""Adaptador de WhatsApp Cloud API para el flujo conversacional."""

import hashlib
import hmac
import json
import logging
from typing import Any

import requests
from django.conf import settings

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


def handle_message(sender: str, text: str) -> list[str]:
    conversation, created = _manager(ChatConversation).get_or_create(
        channel='whatsapp',
        external_user_id=sender,
        defaults={'status': ChatConversation.STATUS_ACTIVE},
    )
    workflow = ChatbotWorkflow(conversation)
    if created or not conversation.messages:
        return [workflow.start()['message']]

    state = conversation.flow_state
    if state == 'waiting_question':
        return [workflow.submit_question(text)['message']]
    if state == 'waiting_confirmation':
        if _is_yes(text):
            return [workflow.confirm_more_help(True)['message']]
        if _is_no(text):
            return [workflow.confirm_more_help(False)['message']]
        return ['Respóndeme sí o no: ¿te puedo ayudar en algo más?']
    if state == 'help_options':
        if _requests_advisor(text):
            return [workflow.escalate('El usuario solicitó atención humana después de recibir una respuesta.')['message']]
        return [workflow.submit_question(text)['message']]
    if state == 'waiting_advisor_question':
        return [workflow.submit_advisor_question(text)['message']]
    if state in {'ended', 'pending'}:
        return ['Esta conversación ya está cerrada. Envía un nuevo mensaje para iniciar otra conversación.']
    workflow.start()
    return [workflow.submit_question(text)['message']]


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