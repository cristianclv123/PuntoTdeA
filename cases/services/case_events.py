"""Eventos de sistema del caso (toma / cierre) visibles en el chat."""

from django.utils import timezone

from cases.models import Message
from cases.services.realtime import broadcast_new_message


def advisor_label(user) -> str:
    if user is None:
        return "Un asesor"
    return (user.get_full_name() or "").strip() or user.username


def add_system_message(conversation, body: str, *, at=None) -> Message:
    message = Message.objects.create(
        conversation=conversation,
        direction=Message.Direction.SYSTEM,
        body=body,
        sent_at=at or timezone.now(),
    )
    broadcast_new_message(message)
    return message


def mark_claimed(conversation, user, *, assign: bool = True):
    """Registra la toma del caso (timestamps + evento en chat)."""
    if conversation.claimed_at and conversation.claimed_by_id:
        if assign and conversation.assigned_to_id is None:
            conversation.assigned_to = user
            conversation.save(update_fields=["assigned_to", "updated_at"])
        return

    when = timezone.now()
    conversation.claimed_at = when
    conversation.claimed_by = user
    update_fields = ["claimed_at", "claimed_by", "updated_at"]
    if assign:
        conversation.assigned_to = user
        update_fields.insert(2, "assigned_to")
    conversation.save(update_fields=update_fields)
    add_system_message(conversation, f"{advisor_label(user)} tomó el caso", at=when)


def mark_closed(conversation, user):
    """Registra el cierre del caso (timestamps + evento en chat)."""
    when = timezone.now()
    conversation.closed_at = when
    conversation.closed_by = user
    conversation.save(update_fields=["closed_at", "closed_by", "updated_at"])
    add_system_message(conversation, f"{advisor_label(user)} cerró el caso", at=when)
