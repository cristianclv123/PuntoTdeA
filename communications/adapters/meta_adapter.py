"""Cliente directo para Meta WhatsApp Cloud API."""

from __future__ import annotations

import mimetypes
import re
from typing import Any

import requests
from django.conf import settings
from django.core.files import File

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


def send_image_message(to: str, image_file: File, caption: str = "") -> SendResult:
    """Sube una imagen guardada en el servidor y la envía con un pie de foto."""
    normalized_phone = _normalize_phone(to)
    if not normalized_phone:
        return SendResult(success=False, error="Número de teléfono vacío.")
    if not image_file:
        return SendResult(success=False, error="El archivo de imagen está vacío.")

    filename = image_file.name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    content_type = mimetypes.guess_type(filename)[0] or ""
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
        image_file.open("rb")
        upload_response = requests.post(
            _media_url(),
            headers={"Authorization": f"Bearer {settings.META_ACCESS_TOKEN}"},
            data={"messaging_product": "whatsapp"},
            files={"file": (filename, image_file, content_type)},
            timeout=settings.META_REQUEST_TIMEOUT,
        )
        upload_response.raise_for_status()
        media_id = upload_response.json().get("id")
    except (OSError, requests.RequestException, ValueError) as exc:
        return SendResult(
            success=False,
            error=_request_error(upload_response, exc),
        )
    finally:
        image_file.close()

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

        if fields["header_type"] != "none":
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
