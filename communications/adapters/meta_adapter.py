"""Cliente directo para Meta WhatsApp Cloud API."""

from __future__ import annotations

import re
from typing import Any

import requests
from django.conf import settings

from .base import ChannelAdapter, SendResult
from ..services.meta_errors import explain


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


def _media_url() -> str:
    return (
        f"{settings.META_GRAPH_API_URL.rstrip('/')}/"
        f"{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}/media"
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
            return explain(detail)

    return explain(str(error))


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


def send_text_message(to: str, text: str, *, preview_url: bool = False) -> SendResult:
    """Envía una respuesta de texto del chatbot por el número configurado.

    Si ``preview_url`` es ``true``, WhatsApp intenta generar una preview de la
    primera URL que encuentre en el cuerpo del mensaje (miniatura + título).
    """
    normalized_phone = _normalize_phone(to)
    if not normalized_phone:
        return SendResult(success=False, error="Número de teléfono vacío.")
    if not (text or "").strip():
        return SendResult(success=False, error="El texto del mensaje está vacío.")
    text_payload: dict[str, Any] = {"body": text.strip()}
    if preview_url:
        text_payload["preview_url"] = True
    return _post_message(
        {
            "messaging_product": "whatsapp",
            "to": normalized_phone,
            "type": "text",
            "text": text_payload,
        }
    )


def send_image_message(
    to: str,
    image_data: bytes,
    filename: str,
    content_type: str,
    caption: str = "",
) -> SendResult:
    """Sube bytes de imagen almacenados en la base de datos y los envía con texto."""
    normalized_phone = _normalize_phone(to)
    if not normalized_phone:
        return SendResult(success=False, error="Número de teléfono vacío.")
    if not image_data:
        return SendResult(success=False, error="El archivo de imagen está vacío.")

    if content_type not in {"image/jpeg", "image/png"}:
        return SendResult(
            success=False,
            error="WhatsApp solo admite imágenes JPG o PNG para este envío.",
        )

    error = _configuration_error()
    if error:
        return SendResult(success=False, error=error)

    upload_response = None
    try:
        upload_response = requests.post(
            _media_url(),
            headers={"Authorization": f"Bearer {settings.META_ACCESS_TOKEN}"},
            data={"messaging_product": "whatsapp"},
            files={"file": (filename, image_data, content_type)},
            timeout=settings.META_REQUEST_TIMEOUT,
        )
        upload_response.raise_for_status()
        media_id = upload_response.json().get("id")
    except (OSError, requests.RequestException, ValueError) as exc:
        return SendResult(
            success=False,
            error=_request_error(upload_response, exc),
        )

    if not media_id:
        return SendResult(success=False, error="Meta no devolvió el identificador de la imagen.")

    image_payload: dict[str, Any] = {"id": media_id}
    if caption.strip():
        if len(caption.strip()) > 1024:
            return SendResult(
                success=False,
                error="La respuesta supera el límite de 1024 caracteres del pie de imagen.",
            )
        image_payload["caption"] = caption.strip()
    return _post_message(
        {
            "messaging_product": "whatsapp",
            "to": normalized_phone,
            "type": "image",
            "image": image_payload,
        }
    )


def upload_whatsapp_media(
    file_bytes: bytes,
    filename: str = "imagen.jpg",
    content_type: str = "image/jpeg",
) -> SendResult:
    """Sube un archivo binario al almacén de medios de WhatsApp Cloud API."""
    error = _configuration_error()
    if error:
        return SendResult(success=False, error=error)
    if not file_bytes:
        return SendResult(success=False, error="El archivo de imagen está vacío.")
    if content_type not in {"image/jpeg", "image/png"}:
        return SendResult(
            success=False,
            error="WhatsApp solo admite imágenes JPG o PNG para este envío.",
        )

    response = None
    try:
        response = requests.post(
            _media_url(),
            headers={"Authorization": f"Bearer {settings.META_ACCESS_TOKEN}"},
            data={"messaging_product": "whatsapp"},
            files={"file": (filename, file_bytes, content_type)},
            timeout=settings.META_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        return SendResult(success=False, error=_request_error(response, exc))

    media_id = body.get("id", "")
    if not media_id:
        return SendResult(
            success=False,
            error="Meta no devolvió el ID del medio subido.",
        )
    return SendResult(success=True, provider_message_id=str(media_id))


def send_uploaded_image_message(to: str, media_id: str, caption: str = "") -> SendResult:
    """Envía una imagen previamente subida a Meta (por ``media_id``).

    Si se proporciona ``caption``, se muestra como texto bajo la imagen.
    """
    normalized_phone = _normalize_phone(to)
    if not normalized_phone:
        return SendResult(success=False, error="Número de teléfono vacío.")
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": normalized_phone,
        "type": "image",
        "image": {"id": media_id},
    }
    caption_text = (caption or "").strip()
    if caption_text:
        payload["image"]["caption"] = caption_text
    return _post_message(payload)

class MetaAdapter(ChannelAdapter):
    """Envío de plantillas aprobadas mediante Meta WhatsApp Cloud API."""

    provider_name = "meta"

    @staticmethod
    def _template_fields(template) -> dict[str, str]:
        """Lee los datos del envío desde un borrador, snapshot o ``TemplateRef``."""
        return {
            "name": getattr(template, "meta_template_name", "")
            or getattr(template, "name", "")
            or "",
            "language": getattr(template, "language", "") or "es_CO",
            "body_text": getattr(template, "body_text", "") or "",
            "header_type": getattr(template, "header_type", "") or "none",
            "header_text": getattr(template, "header_text", "") or "",
            "header_media_url": getattr(template, "header_media_url", "") or "",
        }

    @staticmethod
    def _parameter_values(body_text: str, params: dict) -> tuple[list[dict[str, str]], str]:
        indexes = sorted(
            {int(index) for index in re.findall(r"\{\{(\d+)\}\}", body_text or "")}
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

        fields = self._template_fields(template)
        if not fields["name"]:
            return None, "La plantilla no tiene un nombre válido en Meta."

        components: list[dict[str, Any]] = []
        parameters, error = self._parameter_values(fields["body_text"], params or {})
        if error:
            return None, error
        if parameters:
            components.append({"type": "body", "parameters": parameters})

        if fields["header_type"] == "text":
            header_text = fields["header_text"].strip()
            if not header_text:
                return None, "La plantilla tiene encabezado de texto, pero no contiene el texto requerido."
            if "{{" in header_text or "}}" in header_text:
                return None, "El encabezado de texto no admite variables dinámicas."
            components.append(
                {
                    "type": "header",
                    "parameters": [{"type": "text", "text": header_text}],
                }
            )
        elif fields["header_type"] in {"image", "video", "document"}:
            if not fields["header_media_url"]:
                return None, "La plantilla tiene encabezado multimedia pero no una URL configurada."
            media_type = fields["header_type"]
            components.append(
                {
                    "type": "header",
                    "parameters": [
                        {"type": media_type, media_type: {"link": fields["header_media_url"]}}
                    ],
                }
            )
        elif fields["header_type"] != "none":
            return None, f"Tipo de encabezado no soportado: {fields['header_type']}."

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": normalized_phone,
            "type": "template",
            "template": {
                "name": fields["name"],
                "language": {"code": fields["language"]},
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
