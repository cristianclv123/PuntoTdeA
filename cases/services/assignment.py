"""Asignación atómica de conversaciones a asesores."""

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from cases.models import Conversation, Department
from cases.services.case_events import advisor_label, mark_claimed, mark_closed
from cases.services.realtime import broadcast_conversation_update

User = get_user_model()
logger = logging.getLogger(__name__)


class ClaimError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class CloseError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def user_can_act_on_conversation(conversation: Conversation, user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_staff", False)
            or conversation.assigned_to_id == user.id
        )
    )


def advisor_can_reply(conversation: Conversation, user) -> bool:
    return user_can_act_on_conversation(conversation, user) and (
        conversation.status != Conversation.Status.CERRADO
    )


def claim_greeting_body(user) -> str:
    name = advisor_label(user)
    return (
        f"Hola, soy {name}, asesora de soporte al cliente de Punto TdeA. "
        "¿En qué te podemos ayudar?"
    )


def _send_claim_greeting(conversation: Conversation, user) -> None:
    from cases.services.ingestion import create_outbound_message

    try:
        create_outbound_message(
            conversation,
            claim_greeting_body(user),
            user=user,
        )
    except ValidationError as exc:
        logger.warning(
            "No se pudo enviar el saludo al tomar el caso %s: %s",
            conversation.pk,
            "; ".join(exc.messages) if hasattr(exc, "messages") else exc,
        )


def _locked_conversation(conversation_id: int) -> Conversation | None:
    return (
        Conversation.objects.select_for_update(of=("self",))
        .select_related("assigned_to", "channel", "contact", "department")
        .filter(pk=conversation_id)
        .first()
    )


@transaction.atomic
def _assign_claim(conversation_id: int, user) -> tuple[Conversation, bool]:
    if user is None or not getattr(user, "is_authenticated", False):
        raise ClaimError("unauthenticated", "Debes iniciar sesión para tomar el chat.")

    # of=("self",): Postgres rejects FOR UPDATE on nullable OUTER JOIN sides
    # created by select_related on nullable FKs (assigned_to, department).
    conversation = _locked_conversation(conversation_id)
    if conversation is None:
        raise ClaimError("not_found", "Conversación no encontrada.")

    if conversation.status == Conversation.Status.CERRADO:
        raise ClaimError("closed", "Este caso ya está cerrado y no puede tomarse.")

    if conversation.assigned_to_id and conversation.assigned_to_id != user.id:
        if not getattr(user, "is_staff", False):
            raise ClaimError(
                "already_assigned",
                f"Este chat ya está asignado a {conversation.assigned_to.get_full_name() or conversation.assigned_to.username}.",
            )
        mark_claimed(conversation, user, assign=True, force=True)
        broadcast_conversation_update(conversation)
        return conversation, True

    if conversation.assigned_to_id is None:
        mark_claimed(conversation, user)
        broadcast_conversation_update(conversation)
        return conversation, True

    return conversation, False


def claim_conversation(conversation_id: int, user) -> Conversation:
    conversation, send_greeting = _assign_claim(conversation_id, user)
    if send_greeting:
        _send_claim_greeting(conversation, user)
    return conversation


@transaction.atomic
def close_conversation(
    conversation_id: int,
    user,
    *,
    assigned_to_id=None,
    department_id=None,
    priority=None,
) -> Conversation:
    if user is None or not getattr(user, "is_authenticated", False):
        raise CloseError("unauthenticated", "Debes iniciar sesión para cerrar el caso.")

    conversation = _locked_conversation(conversation_id)
    if conversation is None:
        raise CloseError("not_found", "Conversación no encontrada.")

    if conversation.status == Conversation.Status.CERRADO:
        raise CloseError("already_closed", "El caso ya estaba cerrado.")

    if not user_can_act_on_conversation(conversation, user):
        raise CloseError(
            "forbidden",
            "Solo el asesor asignado o un administrador puede cerrar este caso.",
        )

    effective_assigned = assigned_to_id or conversation.assigned_to_id
    if not effective_assigned and getattr(user, "is_staff", False):
        effective_assigned = user.id
    if not effective_assigned:
        raise CloseError(
            "missing_advisor",
            "Debes asignar un asesor antes de cerrar el caso.",
        )
    if assigned_to_id and not User.objects.filter(pk=assigned_to_id, is_active=True).exists():
        raise CloseError("invalid_advisor", "Asesor no encontrado o inactivo.")
    if (
        assigned_to_id
        and assigned_to_id != conversation.assigned_to_id
        and not getattr(user, "is_staff", False)
        and conversation.assigned_to_id not in (None, user.id)
    ):
        effective_assigned = conversation.assigned_to_id

    effective_department = department_id or conversation.department_id
    if not effective_department:
        raise CloseError(
            "missing_department",
            "Debes indicar la dependencia (clasificación) antes de cerrar el caso.",
        )
    if department_id and not Department.objects.filter(pk=department_id).exists():
        raise CloseError("invalid_department", "Dependencia no encontrada.")

    if priority:
        valid_priorities = {choice.value for choice in Conversation.Priority}
        if priority not in valid_priorities:
            raise CloseError("invalid_priority", "Prioridad inválida.")
        conversation.priority = priority

    conversation.assigned_to_id = effective_assigned
    conversation.department_id = effective_department
    conversation.escalated_to = None
    if not conversation.claimed_at:
        mark_claimed(conversation, conversation.assigned_to or user, assign=False)
    conversation.status = Conversation.Status.CERRADO
    conversation.save()
    mark_closed(conversation, user)
    broadcast_conversation_update(conversation)
    conversation.refresh_from_db()
    return conversation
