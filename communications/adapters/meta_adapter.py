"""Cliente directo para Meta WhatsApp Cloud API."""

from __future__ import annotations

import re
from typing import Any

import requests
from django.conf import settings

from .base import ChannelAdapter, SendResult


def _configuration_error() -> str:
    missing = [
        name
        for name, value in {
            "META_ACCESS_TOKEN": settings.META_ACCESS_TOKEN,
            "WHATSAPP_PHONE_NUMBER_ID": settings.WHATSAPP_PHONE_NUMBER_ID,
        }.items()
        if not value
    ]
    if missing:
        return f"Falta configurar: {', '.join(missing)}."
    return ""


def _messages_url() -> str:
    return (
        f"{settings.META_GRAPH_API_URL.rstrip('/')}/"
        f"{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )


def _normalize_phone(phone: str) -> str:
    """Meta espera el número E.164 sin el prefijo '+'."""
    return re.sub(r"\D", "", phone or "")


def _request_error(response: requests.Response | None, error: Exception) -> str:
    if response is not None:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except (TypeError, ValueError):
            detail = response.text[:300]
        if detail:
            return f"Meta API: {detail}"
    return f"Meta API: {error}"


def _post_message(payload: dict[str, Any]) -> SendResult:
    error = _configuration_error()
    if error:
        return SendResult(success=False, error=error)

    response = None
    try:
        response = requests.post(
            _messages_url(),
            headers={
                "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=settings.META_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        return SendResult(success=False, error=_request_error(response, exc))

    messages = body.get("messages") or []
    message_id = (messages[0].get("id") if messages else "") or ""
    if not message_id:
        return SendResult(
            success=False,
            error="Meta API no devolvió el identificador del mensaje.",
        )
    return SendResult(success=True, provider_message_id=message_id)


def send_text_message(to: str, text: str) -> SendResult:
    """Envía una respuesta de texto del chatbot por el número configurado."""
    normalized_phone = _normalize_phone(to)
    if not normalized_phone:
        return SendResult(success=False, error="Número de teléfono vacío.")
    if not (text or "").strip():
        return SendResult(success=False, error="El texto del mensaje está vacío.")
    return _post_message(
        {
            "messaging_product": "whatsapp",
            "to": normalized_phone,
            "type": "text",
            "text": {"body": text.strip()},
        }
    )


class MetaAdapter(ChannelAdapter):
    """Envío de plantillas aprobadas mediante Meta WhatsApp Cloud API."""

    provider_name = "meta"

    @staticmethod
    def _parameter_values(template, params: dict) -> tuple[list[dict[str, str]], str]:
        indexes = sorted(
            {int(index) for index in re.findall(r"\{\{(\d+)\}\}", template.body_text or "")}
        )
        values = []
        for index in indexes:
            value = params.get(str(index), params.get(index, params.get(f"{{{{{index}}}}}")))
            if value is None:
                return [], f"Falta el parámetro {{{{{index}}}}} para la plantilla."
            values.append({"type": "text", "text": str(value)})
        return values, ""

    def _payload(self, to: str, template, params: dict) -> tuple[dict[str, Any] | None, str]:
        normalized_phone = _normalize_phone(to)
        if not normalized_phone:
            return None, "Número de teléfono vacío."
        if template.status != template.Status.APPROVED:
            return None, "La plantilla debe estar aprobada por Meta antes de enviarse."

        components: list[dict[str, Any]] = []
        parameters, error = self._parameter_values(template, params or {})
        if error:
            return None, error
        if parameters:
            components.append({"type": "body", "parameters": parameters})

        if template.header_type != template.HeaderType.NONE:
            if not template.header_media_url:
                return None, "La plantilla tiene encabezado multimedia pero no una URL configurada."
            media_type = template.header_type
            components.append(
                {
                    "type": "header",
                    "parameters": [
                        {"type": media_type, media_type: {"link": template.header_media_url}}
                    ],
                }
            )

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": normalized_phone,
            "type": "template",
            "template": {
                "name": template.meta_template_name,
                "language": {"code": template.language},
            },
        }
        if components:
            payload["template"]["components"] = components
        return payload, ""

    def send_template_message(self, to: str, template, params: dict) -> SendResult:
        payload, error = self._payload(to, template, params)
        if error:
            return SendResult(success=False, error=error)
        return _post_message(payload)
