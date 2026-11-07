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


# Límites oficiales de WhatsApp Cloud API para mensajes interactivos.
MAX_INTERACTIVE_BUTTONS = 3
MAX_BUTTON_TITLE_LENGTH = 20
MAX_LIST_ROWS = 10
MAX_ROW_TITLE_LENGTH = 24
MAX_ROW_DESCRIPTION_LENGTH = 72
MAX_SECTION_TITLE_LENGTH = 24
MAX_LIST_BUTTON_LENGTH = 20
MAX_INTERACTIVE_BODY_LENGTH = 1024
MAX_INTERACTIVE_HEADER_LENGTH = 60
MAX_INTERACTIVE_FOOTER_LENGTH = 60


def _interactive_envelope(
    normalized_phone: str,
    body_text: str,
    *,
    header_text: str = "",
    footer_text: str = "",
) -> tuple[dict[str, Any], str]:
    """Arma el sobre común de los mensajes interactivos y valida longitudes."""
    body = (body_text or "").strip()
    if not body:
        return {}, "El cuerpo del mensaje interactivo está vacío."
    if len(body) > MAX_INTERACTIVE_BODY_LENGTH:
        return {}, "El cuerpo del mensaje interactivo supera los 1024 caracteres."

    interactive: dict[str, Any] = {"body": {"text": body}}
    header = (header_text or "").strip()
    if header:
        if len(header) > MAX_INTERACTIVE_HEADER_LENGTH:
            return {}, "El encabezado supera los 60 caracteres."
        interactive["header"] = {"type": "text", "text": header}
    footer = (footer_text or "").strip()
    if footer:
        if len(footer) > MAX_INTERACTIVE_FOOTER_LENGTH:
            return {}, "El pie supera los 60 caracteres."
        interactive["footer"] = {"text": footer}

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": normalized_phone,
        "type": "interactive",
        "interactive": interactive,
    }, ""


def send_interactive_buttons(
    to: str,
    body_text: str,
    buttons: list[dict[str, str]],
    *,
    header_text: str = "",
    footer_text: str = "",
) -> SendResult:
    """Envía hasta 3 botones de respuesta rápida (``reply buttons``).

    Cada botón es ``{"id": "...", "title": "..."}``. El ``id`` es el valor
    estable que llega al webhook; el ``title`` es solo lo que ve el usuario.
    """
    normalized_phone = _normalize_phone(to)
    if not normalized_phone:
        return SendResult(success=False, error="Número de teléfono vacío.")
    if not 1 <= len(buttons) <= MAX_INTERACTIVE_BUTTONS:
        return SendResult(
            success=False,
            error="WhatsApp admite entre 1 y 3 botones de respuesta.",
        )

    payload, error = _interactive_envelope(
        normalized_phone,
        body_text,
        header_text=header_text,
        footer_text=footer_text,
    )
    if error:
        return SendResult(success=False, error=error)

    action_buttons = []
    seen_ids = set()
    for button in buttons:
        button_id = (button.get("id") or "").strip()
        title = (button.get("title") or "").strip()
        if not button_id or not title:
            return SendResult(success=False, error="Cada botón necesita id y título.")
        if button_id in seen_ids:
            return SendResult(success=False, error="Los identificadores de botón deben ser únicos.")
        if len(title) > MAX_BUTTON_TITLE_LENGTH:
            return SendResult(
                success=False,
                error="El título de un botón supera los 20 caracteres.",
            )
        seen_ids.add(button_id)
        action_buttons.append(
            {"type": "reply", "reply": {"id": button_id, "title": title}}
        )

    payload["interactive"]["type"] = "button"
    payload["interactive"]["action"] = {"buttons": action_buttons}
    return _post_message(payload)


def send_interactive_list(
    to: str,
    body_text: str,
    button_label: str,
    sections: list[dict[str, Any]],
    *,
    header_text: str = "",
    footer_text: str = "",
) -> SendResult:
    """Envía un mensaje de lista (``list message``) con hasta 10 opciones.

    ``sections`` es ``[{"title": "...", "rows": [{"id", "title",
    "description"}]}]``. El ``id`` de cada fila es el valor estable que recibe
    el webhook.
    """
    normalized_phone = _normalize_phone(to)
    if not normalized_phone:
        return SendResult(success=False, error="Número de teléfono vacío.")
    label = (button_label or "").strip()
    if not label or len(label) > MAX_LIST_BUTTON_LENGTH:
        return SendResult(
            success=False,
            error="La etiqueta del botón de la lista debe tener entre 1 y 20 caracteres.",
        )

    payload, error = _interactive_envelope(
        normalized_phone,
        body_text,
        header_text=header_text,
        footer_text=footer_text,
    )
    if error:
        return SendResult(success=False, error=error)

    total_rows = 0
    seen_ids = set()
    action_sections = []
    for section in sections:
        rows = []
        section_title = (section.get("title") or "").strip()
        if len(section_title) > MAX_SECTION_TITLE_LENGTH:
            return SendResult(
                success=False,
                error="El título de una sección supera los 24 caracteres.",
            )
        for row in section.get("rows") or []:
            row_id = (row.get("id") or "").strip()
            title = (row.get("title") or "").strip()
            description = (row.get("description") or "").strip()
            if not row_id or not title:
                return SendResult(
                    success=False,
                    error="Cada fila de la lista necesita id y título.",
                )
            if row_id in seen_ids:
                return SendResult(
                    success=False,
                    error="Los identificadores de fila deben ser únicos.",
                )
            if len(title) > MAX_ROW_TITLE_LENGTH:
                return SendResult(
                    success=False,
                    error="El título de una fila supera los 24 caracteres.",
                )
            if len(description) > MAX_ROW_DESCRIPTION_LENGTH:
                return SendResult(
                    success=False,
                    error="La descripción de una fila supera los 72 caracteres.",
                )
            seen_ids.add(row_id)
            total_rows += 1
            row_payload = {"id": row_id, "title": title}
            if description:
                row_payload["description"] = description
            rows.append(row_payload)
        if not rows:
            return SendResult(
                success=False,
                error="Cada sección de la lista debe tener al menos una fila.",
            )
        section_payload: dict[str, Any] = {"rows": rows}
        if section_title:
            section_payload["title"] = section_title
        action_sections.append(section_payload)

    if not 1 <= total_rows <= MAX_LIST_ROWS:
        return SendResult(
            success=False,
            error="WhatsApp admite entre 1 y 10 opciones en una lista.",
        )

    payload["interactive"]["type"] = "list"
    payload["interactive"]["action"] = {
        "button": label,
        "sections": action_sections,
    }
    return _post_message(payload)


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
        return SendResult(success=False, error="El archivo está vacío.")

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
    """Envía una imagen previamente subida a Meta (por ``media_id``)."""
    return send_media_message(
        to,
        media_type="image",
        media_id=media_id,
        caption=caption,
    )


def send_media_message(
    to: str,
    *,
    media_type: str,
    media_id: str,
    caption: str = "",
    filename: str = "",
) -> SendResult:
    """Envía imagen, video o documento ya subido a Meta.

    El documento puede llevar ``filename`` para que WhatsApp muestre el nombre.
    """
    normalized_phone = _normalize_phone(to)
    if not normalized_phone:
        return SendResult(success=False, error="Número de teléfono vacío.")
    if media_type not in {"image", "video", "document"}:
        return SendResult(success=False, error="Tipo de medio no soportado.")
    if not (media_id or "").strip():
        return SendResult(success=False, error="Falta el id del medio.")
    media: dict[str, Any] = {"id": media_id}
    caption_text = (caption or "").strip()
    if caption_text:
        media["caption"] = caption_text
    if media_type == "document" and filename:
        media["filename"] = filename
    return _post_message(
        {
            "messaging_product": "whatsapp",
            "to": normalized_phone,
            "type": media_type,
            media_type: media,
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
