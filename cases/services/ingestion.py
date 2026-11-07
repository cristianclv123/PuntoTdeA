import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from cases.models import Channel, Contact, Conversation, Message
from cases.services.message_links import first_http_url
from cases.services.realtime import broadcast_new_message
from communications.adapters.meta_adapter import (
    MetaAdapter,
    send_media_message,
    send_text_message,
    upload_whatsapp_media,
)


@dataclass
class InboundPayload:
    channel_code: str
    external_thread_id: str
    body: str
    external_message_id: str = ""
    sent_at: Optional[object] = None
    contact_full_name: str = ""
    contact_document_number: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    contact_academic_program: str = "Sin definir"
    contact_semester: int = 1
    theme: str = ""


def _resolve_sent_at(value):
    if value is None:
        return timezone.now()
    if timezone.is_aware(value):
        return value
    if isinstance(value, str):
        parsed = parse_datetime(value)
        if parsed is None:
            return timezone.now()
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _upsert_contact(payload: InboundPayload) -> Contact:
    document = (payload.contact_document_number or "").strip()
    phone = (payload.contact_phone or "").strip()
    email = (payload.contact_email or "").strip().lower()

    contact = None
    if document:
        contact = Contact.objects.filter(document_number=document).first()
    if contact is None and phone:
        contact = Contact.objects.filter(phone=phone).first()
    if contact is None and email:
        contact = Contact.objects.filter(email=email).first()

    defaults = {
        "full_name": payload.contact_full_name or phone or email or "Contacto web",
        "email": email or f"{phone or 'web'}@placeholder.local",
        "phone": phone or "0000000000",
        "academic_program": payload.contact_academic_program or "Sin definir",
        "semester": payload.contact_semester or 1,
    }

    if contact is None:
        if not document:
            document = f"TMP-{phone or email or timezone.now().timestamp()}"
        contact = Contact.objects.create(document_number=document, **defaults)
        return contact

    for field, value in defaults.items():
        if value:
            setattr(contact, field, value)
    contact.save()
    return contact


@transaction.atomic
def ingest_inbound_message(payload: InboundPayload) -> tuple[Conversation, Message, bool]:
    """
    Persist inbound message. Returns (conversation, message, created).
    Idempotent when external_message_id is provided.
    """
    channel, _ = Channel.objects.get_or_create(
        code=payload.channel_code,
        defaults={"name": payload.channel_code.title(), "is_active": True},
    )
    contact = _upsert_contact(payload)
    sent_at = _resolve_sent_at(payload.sent_at)

    conversation = (
        Conversation.objects.select_for_update()
        .filter(channel=channel, external_thread_id=payload.external_thread_id)
        .first()
    )
    if conversation is None:
        conversation = Conversation.objects.create(
            channel=channel,
            contact=contact,
            external_thread_id=payload.external_thread_id,
            theme=payload.theme or "",
            status=Conversation.Status.PENDIENTE,
            last_message_at=sent_at,
        )
    else:
        conversation.contact = contact
        if payload.theme:
            conversation.theme = payload.theme
        conversation.last_message_at = sent_at
        conversation.save(update_fields=["contact", "theme", "last_message_at", "updated_at"])

    external_id = (payload.external_message_id or "").strip()
    if external_id:
        existing = Message.objects.filter(
            conversation=conversation,
            external_id=external_id,
        ).first()
        if existing:
            return conversation, existing, False

    message = Message.objects.create(
        conversation=conversation,
        direction=Message.Direction.INBOUND,
        body=payload.body,
        external_id=external_id,
        sent_at=sent_at,
    )
    broadcast_new_message(message)
    from notifications.events import notify_customer_reply, notify_new_chat

    if conversation.messages.filter(direction=Message.Direction.INBOUND).count() <= 1:
        notify_new_chat(conversation)
    else:
        notify_customer_reply(conversation, payload.body)
    return conversation, message, True


def _channel_code(conversation: Conversation) -> str:
    channel = getattr(conversation, "channel", None)
    if channel is None and conversation.channel_id:
        channel = Channel.objects.filter(pk=conversation.channel_id).first()
    return getattr(channel, "code", "") or ""


def _contact_phone(conversation: Conversation) -> str:
    contact = getattr(conversation, "contact", None)
    if contact is None and conversation.contact_id:
        contact = Contact.objects.filter(pk=conversation.contact_id).first()
    return (getattr(contact, "phone", "") or "").strip()


def _render_template_body(template, params: dict | None) -> str:
    text = template.body_text or ""
    for key, value in (params or {}).items():
        text = text.replace(f"{{{{{key}}}}}", str(value))
    return text.strip()


_WHATSAPP_IMAGES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_WHATSAPP_VIDEOS = {
    ".mp4": "video/mp4",
    ".3gp": "video/3gpp",
    ".3gpp": "video/3gpp",
}


def _whatsapp_media_type(filename: str, content_type: str) -> tuple[str, str]:
    extension = Path(filename or "").suffix.lower()
    if extension in _WHATSAPP_IMAGES:
        return "image", _WHATSAPP_IMAGES[extension]
    if extension in _WHATSAPP_VIDEOS:
        return "video", _WHATSAPP_VIDEOS[extension]
    guessed, _encoding = mimetypes.guess_type(filename or "")
    mime = (content_type or "").split(";", 1)[0].strip() or guessed or "application/octet-stream"
    return "document", mime


def _read_upload(uploaded) -> bytes:
    payload = uploaded.read()
    if hasattr(uploaded, "seek"):
        uploaded.seek(0)
    return payload


def _file_label(files) -> str:
    names = [Path(getattr(uploaded, "name", "") or "archivo").name for uploaded in files]
    return ", ".join(name for name in names if name)


def _send_whatsapp_files(phone: str, files) -> str:
    first_id = ""
    for uploaded in files:
        filename = Path(getattr(uploaded, "name", "") or "archivo").name
        kind, mime = _whatsapp_media_type(
            filename,
            getattr(uploaded, "content_type", "") or "",
        )
        uploaded_media = upload_whatsapp_media(
            _read_upload(uploaded),
            filename=filename,
            content_type=mime,
        )
        if not uploaded_media.success:
            raise ValidationError(
                uploaded_media.error or "No se pudo subir el archivo a WhatsApp."
            )
        sent = send_media_message(
            phone,
            media_type=kind,
            media_id=uploaded_media.provider_message_id,
            filename=filename,
        )
        if not sent.success:
            raise ValidationError(sent.error or "No se pudo enviar el archivo por WhatsApp.")
        if not first_id:
            first_id = sent.provider_message_id or ""
    return first_id


def _dispatch_whatsapp(
    *,
    conversation: Conversation,
    body: str,
    template=None,
    template_params=None,
    files=None,
) -> str:
    phone = _contact_phone(conversation)
    if template is not None:
        result = MetaAdapter().send_template_message(phone, template, template_params or {})
        if not result.success:
            raise ValidationError(result.error or "No se pudo enviar la plantilla por WhatsApp.")
        return result.provider_message_id or ""

    if _channel_code(conversation) != "whatsapp":
        return ""

    file_list = [item for item in (files or []) if item]
    provider_id = _send_whatsapp_files(phone, file_list) if file_list else ""
    text = (body or "").strip()
    if not text:
        return provider_id
    if first_http_url(text):
        result = send_text_message(phone, text, preview_url=True)
    else:
        result = send_text_message(phone, text)
    if not result.success:
        raise ValidationError(result.error or "No se pudo enviar el mensaje por WhatsApp.")
    return provider_id or result.provider_message_id or ""


@transaction.atomic
def create_outbound_message(
    conversation: Conversation,
    body: str,
    *,
    external_id: str = "",
    user=None,
    uploaded_files=None,
    template=None,
    template_params=None,
    emit_notification: bool = True,
) -> Message:
    from cases.models import MessageAttachment
    from cases.services.attachments import validate_uploaded_file

    sent_at = timezone.now()
    files = list(uploaded_files or [])
    text = (body or "").strip()
    if template is not None and not text:
        text = _render_template_body(template, template_params)
    if not text and not files:
        raise ValidationError("Debes escribir un mensaje o adjuntar un archivo.")

    kinds = [validate_uploaded_file(uploaded) for uploaded in files]

    provider_id = external_id or _dispatch_whatsapp(
        conversation=conversation,
        body=text,
        template=template,
        template_params=template_params,
        files=files,
    )

    message = Message.objects.create(
        conversation=conversation,
        direction=Message.Direction.OUTBOUND,
        body=text or _file_label(files),
        external_id=provider_id,
        sent_at=sent_at,
    )

    for uploaded, kind in zip(files, kinds):
        MessageAttachment.objects.create(
            message=message,
            file=uploaded,
            original_name=uploaded.name,
            content_type=getattr(uploaded, "content_type", "") or "",
            kind=kind,
            size_bytes=uploaded.size,
        )

    conversation.last_message_at = sent_at
    conversation.save(update_fields=["last_message_at", "updated_at"])
    broadcast_new_message(message)
    if emit_notification:
        from notifications.events import notify_advisor_reply

        notify_advisor_reply(conversation, user)
    return message
