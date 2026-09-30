"""Webhook único de Meta WhatsApp Cloud API.

Recibe mensajes para el chatbot y confirmaciones de campañas. Meta puede
reenviar sus eventos, por lo que cada evento se registra de forma idempotente.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone as datetime_timezone
from typing import Any

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from communications.models import BroadcastRecipient, ContactEvent, WhatsAppWebhookEvent
from communications.services.logging_service import log_event
from knowledge.chatbot import whatsapp as chatbot_whatsapp


logger = logging.getLogger(__name__)


def _verify_subscription(request: HttpRequest) -> HttpResponse:
    token = (settings.META_VERIFY_TOKEN or "").strip()
    supplied = request.GET.get("hub.verify_token", "")
    if (
        request.GET.get("hub.mode") != "subscribe"
        or not token
        or not hmac.compare_digest(token, supplied)
    ):
        return HttpResponseForbidden("Verification failed")
    return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")


def _signature_is_valid(raw_body: bytes, signature_header: str | None) -> bool:
    secret = (settings.META_APP_SECRET or "").strip()
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header.split("=", 1)[1])


def _event(
    event_key: str,
    message_id: str,
    event_type: str,
    status: str = "",
    payload: dict[str, Any] | None = None,
):
    """Obtiene o registra el evento. ``False`` indica que ya fue procesado."""
    defaults = {
        "provider_message_id": message_id,
        "event_type": event_type,
        "status": status,
    }
    if payload:
        defaults["payload"] = payload
    try:
        event, created = WhatsAppWebhookEvent.objects.get_or_create(
            event_key=event_key,
            defaults=defaults,
        )
    except IntegrityError:
        event = WhatsAppWebhookEvent.objects.get(event_key=event_key)
        created = False
    return event, created or event.processed_at is None


def _finish_event(event: WhatsAppWebhookEvent) -> None:
    event.processed_at = timezone.now()
    # `payload` se actualiza junto: en varios caminos de ignorados se anota el
    # motivo y no hay otra llamada a save() que lo persista.
    event.save(update_fields=["processed_at", "payload"])


def _compact_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Guarda el `statuses[]` de Meta sin arrastrar campos que no usamos.

    Lo que importa es `errors[]`: sin él, un `failed` que no corresponde a
    ningún destinatario de campaña queda registrado como fallido, pero sin
    explicación de por qué.
    """
    compact: dict[str, Any] = {
        "timestamp": payload.get("timestamp"),
        "recipient_id": payload.get("recipient_id"),
    }
    pricing = payload.get("pricing") or {}
    if pricing:
        compact["pricing"] = {
            key: pricing[key]
            for key in ("billable", "pricing_model", "type", "category")
            if key in pricing
        }
    errors = [error for error in (payload.get("errors") or []) if isinstance(error, dict)]
    if errors:
        compact["errors"] = [
            {key: error[key] for key in ("code", "title", "message") if key in error}
            for error in errors
        ]
    conversation = payload.get("conversation") or {}
    if conversation.get("id"):
        compact["conversation_id"] = conversation["id"]
    return compact


def _compact_inbound(message: dict[str, Any]) -> dict[str, Any]:
    """Guarda lo esencial del mensaje entrante para poder mostrarlo después."""
    return {
        "from": message.get("from"),
        "type": message.get("type"),
        "text": ((message.get("text") or {}).get("body") or "")[:500],
        "timestamp": message.get("timestamp"),
    }


def _timestamp(value: Any):
    try:
        return datetime.fromtimestamp(int(value), tz=datetime_timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return timezone.now()


def _error_message(status_payload: dict[str, Any]) -> str:
    errors = status_payload.get("errors") or []
    parts = []
    for error in errors:
        if not isinstance(error, dict):
            continue
        parts.append(str(error.get("title") or error.get("message") or error.get("code") or ""))
    return "; ".join(part for part in parts if part) or "Meta reportó un fallo de entrega."


def _process_status(status_payload: dict[str, Any]) -> str:
    message_id = (status_payload.get("id") or "").strip()
    status = (status_payload.get("status") or "").strip().lower()
    if not message_id or status not in {"sent", "delivered", "read", "failed"}:
        return "ignored"

    event, should_process = _event(
        f"status:{message_id}:{status}",
        message_id,
        WhatsAppWebhookEvent.Type.STATUS,
        status,
        _compact_status(status_payload),
    )
    if not should_process:
        return "duplicate"

    recipient = (
        BroadcastRecipient.objects.select_related("contact", "campaign")
        .filter(provider_message_id=message_id)
        .first()
    )
    if recipient is None:
        # Sin destinatario el estado no se puede aplicar, pero se conserva el
        # motivo: es la única forma de saber por qué falló un envío suelto
        # hecho desde la página de prueba.
        event.payload = {**event.payload, "unmatched": True}
        logger.info(
            "Estado de Meta sin destinatario de campaña: %s (%s)", message_id, status
        )
        _finish_event(event)
        return "unmatched"

    occurred_at = _timestamp(status_payload.get("timestamp"))
    event_type = None
    update_fields: list[str] = []
    progression = {
        BroadcastRecipient.Status.PENDING: 0,
        BroadcastRecipient.Status.QUEUED: 1,
        BroadcastRecipient.Status.SENT: 2,
        BroadcastRecipient.Status.DELIVERED: 3,
        BroadcastRecipient.Status.READ: 4,
    }

    if status == "failed":
        if recipient.status != BroadcastRecipient.Status.READ:
            recipient.status = BroadcastRecipient.Status.FAILED
            recipient.error_message = _error_message(status_payload)
            update_fields = ["status", "error_message"]
            event_type = ContactEvent.EventType.MESSAGE_FAILED
    else:
        target = {
            "sent": BroadcastRecipient.Status.SENT,
            "delivered": BroadcastRecipient.Status.DELIVERED,
            "read": BroadcastRecipient.Status.READ,
        }[status]
        if progression.get(target, 0) >= progression.get(recipient.status, 0):
            if recipient.status != target:
                recipient.status = target
                update_fields.append("status")
                event_type = {
                    "sent": ContactEvent.EventType.MESSAGE_SENT,
                    "delivered": ContactEvent.EventType.MESSAGE_DELIVERED,
                    "read": ContactEvent.EventType.MESSAGE_READ,
                }[status]
            if status == "sent" and not recipient.sent_at:
                recipient.sent_at = occurred_at
                update_fields.append("sent_at")
            elif status == "delivered" and not recipient.delivered_at:
                recipient.delivered_at = occurred_at
                update_fields.append("delivered_at")
            elif status == "read" and not recipient.read_at:
                recipient.read_at = occurred_at
                update_fields.append("read_at")

    if update_fields:
        recipient.save(update_fields=update_fields)
    if event_type:
        payload = {"provider_message_id": message_id, "status": status}
        if status == "failed":
            payload["error"] = recipient.error_message
        log_event(
            recipient.contact,
            event_type,
            campaign=recipient.campaign,
            broadcast_recipient=recipient,
            payload=payload,
        )
    _finish_event(event)
    return "processed"


def _process_inbound(message: dict[str, Any], phone_number_id: str) -> str:
    message_id = (message.get("id") or "").strip()
    sender = (message.get("from") or "").strip()
    if not message_id or not sender:
        return "ignored"

    event, should_process = _event(
        f"inbound:{message_id}",
        message_id,
        WhatsAppWebhookEvent.Type.INBOUND,
        payload=_compact_inbound(message),
    )
    if not should_process:
        return "duplicate"

    configured_phone_id = (settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
    if configured_phone_id and phone_number_id and phone_number_id != configured_phone_id:
        logger.warning("Mensaje de un número de WhatsApp no configurado: %s", phone_number_id)
        _finish_event(event)
        return "ignored"

    if message.get("type") != "text":
        logger.info("Mensaje no textual ignorado: %s", message_id)
        _finish_event(event)
        return "ignored"

    text = ((message.get("text") or {}).get("body") or "").strip()
    if not text:
        _finish_event(event)
        return "ignored"

    try:
        replies = chatbot_whatsapp.handle_message(sender, text)
        for reply in replies:
            result = chatbot_whatsapp.send_text(sender, reply)
            if not result:
                logger.error("Meta no aceptó la respuesta del chatbot para el mensaje %s", message_id)
    except Exception:
        logger.exception("No fue posible procesar el mensaje de Meta %s", message_id)
        raise

    _finish_event(event)
    return "processed"


def _process_payload(payload: dict[str, Any]) -> dict[str, int]:
    summary = {"processed": 0, "duplicates": 0, "ignored": 0, "unmatched": 0}
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}
            phone_number_id = (metadata.get("phone_number_id") or "").strip()
            for message in value.get("messages") or []:
                result = _process_inbound(message, phone_number_id)
                if result == "duplicate":
                    summary["duplicates"] += 1
                else:
                    summary[result] = summary.get(result, 0) + 1
            for status_payload in value.get("statuses") or []:
                result = _process_status(status_payload)
                if result == "duplicate":
                    summary["duplicates"] += 1
                else:
                    summary[result] = summary.get(result, 0) + 1
    return summary


@csrf_exempt
def whatsapp_webhook(request: HttpRequest):
    """Endpoint público configurado en Meta Developers."""
    if request.method == "GET":
        return _verify_subscription(request)
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido."}, status=405)
    if not _signature_is_valid(request.body, request.headers.get("X-Hub-Signature-256")):
        return HttpResponseForbidden("Invalid signature")
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        return JsonResponse({"error": "El cuerpo debe ser JSON válido."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "El cuerpo debe ser un objeto JSON."}, status=400)

    try:
        summary = _process_payload(payload)
    except Exception:
        return JsonResponse({"error": "No fue posible procesar el evento."}, status=500)
    return JsonResponse({"ok": True, **summary})
