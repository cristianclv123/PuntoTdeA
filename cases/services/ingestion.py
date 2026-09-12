from dataclasses import dataclass
from typing import Optional

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from cases.models import Channel, Contact, Conversation, Message
from cases.services.realtime import broadcast_new_message


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
    return conversation, message, True


def create_outbound_message(
    conversation: Conversation,
    body: str,
    *,
    external_id: str = "",
    user=None,
    uploaded_files=None,
) -> Message:
    from django.core.exceptions import ValidationError

    from cases.models import MessageAttachment
    from cases.services.attachments import validate_uploaded_file

    sent_at = timezone.now()
    files = list(uploaded_files or [])
    if not (body or "").strip() and not files:
        raise ValidationError("Debes escribir un mensaje o adjuntar un archivo.")

    message = Message.objects.create(
        conversation=conversation,
        direction=Message.Direction.OUTBOUND,
        body=(body or "").strip() or ("📎 Archivo adjunto" if files else ""),
        external_id=external_id,
        sent_at=sent_at,
    )

    for uploaded in files:
        kind = validate_uploaded_file(uploaded)
        MessageAttachment.objects.create(
            message=message,
            file=uploaded,
            original_name=uploaded.name,
            content_type=getattr(uploaded, "content_type", "") or "",
            kind=kind,
            size_bytes=uploaded.size,
        )

    updates = ["last_message_at", "updated_at"]
    conversation.last_message_at = sent_at
    if user and conversation.assigned_to_id is None:
        conversation.assigned_to = user
        updates.append("assigned_to")
    conversation.save(update_fields=updates)
    broadcast_new_message(message)
    return message
