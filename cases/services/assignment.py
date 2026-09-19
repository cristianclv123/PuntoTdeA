"""Asignación atómica de conversaciones a asesores."""

from django.db import transaction

from cases.models import Conversation
from cases.services.case_events import mark_claimed
from cases.services.realtime import broadcast_conversation_update


class ClaimError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@transaction.atomic
def claim_conversation(conversation_id: int, user) -> Conversation:
    if user is None or not getattr(user, "is_authenticated", False):
        raise ClaimError("unauthenticated", "Debes iniciar sesión para tomar el chat.")

    # of=("self",): Postgres rejects FOR UPDATE on nullable OUTER JOIN sides
    # created by select_related on nullable FKs (assigned_to, department).
    conversation = (
        Conversation.objects.select_for_update(of=("self",))
        .select_related("assigned_to", "channel", "contact", "department")
        .filter(pk=conversation_id)
        .first()
    )
    if conversation is None:
        raise ClaimError("not_found", "Conversación no encontrada.")

    if conversation.assigned_to_id and conversation.assigned_to_id != user.id:
        raise ClaimError(
            "already_assigned",
            f"Este chat ya está asignado a {conversation.assigned_to.get_full_name() or conversation.assigned_to.username}.",
        )

    if conversation.status == Conversation.Status.CERRADO:
        raise ClaimError("closed", "Este caso ya está cerrado y no puede tomarse.")

    if conversation.assigned_to_id is None:
        mark_claimed(conversation, user)
        broadcast_conversation_update(conversation)

    return conversation


def advisor_can_reply(conversation: Conversation, user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and conversation.assigned_to_id == user.id
        and conversation.status != Conversation.Status.CERRADO
    )
