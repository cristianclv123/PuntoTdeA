"""Recepción de casos transferidos automáticamente desde el bot de conocimiento.

Contrato acordado con knowledge/services/bot_service.py::trigger_handoff:
create_ticket_from_bot(user_data, theme, channel_code, history) -> Conversation
"""
from django.db import transaction
from django.utils import timezone

from cases.models import Channel, Contact, Conversation, Message
from cases.services.realtime import broadcast_conversation_update


def _resolve_document_number(user_data: dict) -> str:
    """Mismo criterio que cases/services/ingestion.py::_upsert_contact: si no
    hay documento, genera uno temporal para no romper el unique constraint."""
    document = (user_data.get("document_number") or "").strip()
    if document:
        return document
    phone = (user_data.get("phone") or "").strip()
    email = (user_data.get("email") or "").strip()
    return f"TMP-{phone or email or timezone.now().timestamp()}"


@transaction.atomic
def create_ticket_from_bot(user_data: dict, theme: str, channel_code: str, history: list) -> Conversation:
    """Recibe la información transferida desde el bot y crea las entidades en 'cases'."""

    # 1. Obtener o crear el contacto del estudiante
    document_number = _resolve_document_number(user_data)
    contact, _ = Contact.objects.get_or_create(
        document_number=document_number,
        defaults={
            "full_name": user_data.get("full_name") or "Usuario Anónimo",
            "email": user_data.get("email") or "",
            "phone": user_data.get("phone") or "",
            "academic_program": user_data.get("academic_program") or "No especificado",
            "semester": user_data.get("semester") or 1,
        },
    )

    # 2. Obtener (o crear si aún no existe) el canal de origen
    channel, _ = Channel.objects.get_or_create(
        code=channel_code,
        defaults={"name": channel_code.title(), "is_active": True},
    )

    # 3. Crear la conversación/ticket (status="pendiente")
    conversation = Conversation.objects.create(
        channel=channel,
        contact=contact,
        status=Conversation.Status.PENDIENTE,
        priority=Conversation.Priority.MEDIA,
        theme=(theme or "")[:120],
    )
    # El save() del modelo Conversation asigna ticket_number, ej: TDEA-000007.

    # 4. Guardar el historial del chat previo en la tabla Message
    for msg in history:
        direction = Message.Direction.INBOUND if msg.get("sender") == "user" else Message.Direction.OUTBOUND
        Message.objects.create(
            conversation=conversation,
            direction=direction,
            body=msg.get("text", ""),
        )

    # Mensaje de sistema registrando la transferencia
    Message.objects.create(
        conversation=conversation,
        direction=Message.Direction.SYSTEM,
        body="[SISTEMA] Conversación transferida automáticamente desde el Bot de Conocimiento.",
    )

    broadcast_conversation_update(conversation)
    return conversation
