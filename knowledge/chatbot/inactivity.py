"""Control de inactividad de las conversaciones del chatbot.

Ciclo implementado:

1. Cinco minutos sin mensajes del usuario: se envía **un** aviso.
2. Dos minutos después del aviso: si el usuario no respondió, se cierra la
   conversación y se le informa.

El estado del ciclo vive en la propia conversación (``last_user_activity_at`` e
``inactivity_warned_at``) y cada transición se reclama con un ``UPDATE``
condicional. Así dos procesos o dos instancias no pueden enviar el aviso dos
veces ni cerrar la misma conversación por duplicado.
"""

from datetime import datetime, timedelta
from typing import Any

from django.db.models import F
from django.utils import timezone

from ..models import ChatConversation


INACTIVITY_WARNING_TIMEOUT = timedelta(minutes=5)
INACTIVITY_CLOSE_TIMEOUT = timedelta(minutes=2)
INACTIVITY_TOTAL_TIMEOUT = INACTIVITY_WARNING_TIMEOUT + INACTIVITY_CLOSE_TIMEOUT

INACTIVITY_WARNING_MESSAGE = (
    'Estamos notando que no has tenido actividad en la conversación. '
    'En 2 minutos cerraremos esta sesión por inactividad. '
    'Si deseas continuar, simplemente responde a este mensaje.'
)

INACTIVITY_CLOSED_MESSAGE = (
    'Tu conversación ha sido cerrada por inactividad. '
    'Cuando necesites ayuda nuevamente, puedes escribirnos y estaremos '
    'encantados de atenderte.'
)


def _manager(model):
    return getattr(model, '_default_manager')


def last_user_activity(conversation: ChatConversation) -> datetime:
    """Momento de la última interacción del usuario.

    ``last_user_activity_at`` se escribe al procesar cada mensaje entrante. El
    ``updated_at`` queda como respaldo para conversaciones históricas o creadas
    antes de esta migración.
    """
    return conversation.last_user_activity_at or conversation.updated_at


def has_pending_advisor_response(conversation: ChatConversation) -> bool:
    """True si el último paso del bot está esperando a un asesor humano."""
    messages = conversation.messages if isinstance(conversation.messages, list) else []
    return any(
        isinstance(message, dict) and message.get('awaiting_advisor') is True
        for message in messages
    )


def conversation_expired(
    conversation: ChatConversation,
    current_time: datetime | None = None,
) -> bool:
    """True si la conversación ya cumplió el ciclo completo de inactividad."""
    current_time = current_time or timezone.now()
    if conversation.status != ChatConversation.STATUS_ACTIVE:
        return False
    if conversation.case_conversation_id is not None:
        # Un ticket abierto sigue vivo aunque el bot deje de responder; el
        # asesor puede tardar más de 7 minutos y no queremos cortar el caso.
        return False

    warned_at = conversation.inactivity_warned_at
    if warned_at is not None:
        # Una vez enviado el aviso, el usuario tiene los 2 minutos completos
        # aunque el aviso se haya enviado con retraso.
        return warned_at + INACTIVITY_CLOSE_TIMEOUT <= current_time

    return last_user_activity(conversation) + INACTIVITY_TOTAL_TIMEOUT <= current_time


def _append_bot_message(
    conversation: ChatConversation,
    content: str,
    *,
    inactivity_warning: bool = False,
    inactivity_closed: bool = False,
) -> None:
    message = {
        'author': 'bot',
        'content': content,
        'created_at': timezone.now().isoformat(),
    }
    if inactivity_warning:
        message['inactivity_warning'] = True
    if inactivity_closed:
        message['inactivity_closed'] = True
    # Releer el historial antes de escribir: si otro proceso agregó un mensaje
    # entre el reclamo y este punto, no se debe sobrescribir.
    conversation.refresh_from_db(fields=['messages'])
    messages = conversation.messages if isinstance(conversation.messages, list) else []
    messages.append(message)
    conversation.messages = messages
    conversation.save(update_fields=['messages', 'updated_at'])


def warn_if_inactive(
    conversation: ChatConversation,
    current_time: datetime | None = None,
) -> dict[str, Any] | None:
    """Envía el aviso de inactividad una sola vez por conversación.

    Devuelve ``None`` si la conversación no corresponde, ya fue avisada o si
    otro proceso ganó la carrera por el aviso.
    """
    current_time = current_time or timezone.now()
    if conversation.status != ChatConversation.STATUS_ACTIVE:
        return None
    if conversation.case_conversation_id is not None:
        return None
    if has_pending_advisor_response(conversation):
        return None
    if last_user_activity(conversation) < current_time - timedelta(hours=24):
        # Fuera de la ventana de 24 h de Meta no se puede enviar texto libre;
        # se evita reintentar un aviso que Meta rechazará siempre.
        return None

    cutoff = current_time - INACTIVITY_WARNING_TIMEOUT
    claimed = _manager(ChatConversation).filter(
        pk=conversation.pk,
        status=ChatConversation.STATUS_ACTIVE,
        inactivity_warned_at__isnull=True,
        last_user_activity_at__lte=cutoff,
    ).update(inactivity_warned_at=current_time)
    if not claimed:
        return None

    conversation.refresh_from_db(fields=['inactivity_warned_at', 'status'])
    if conversation.status != ChatConversation.STATUS_ACTIVE:
        return None

    _append_bot_message(
        conversation,
        INACTIVITY_WARNING_MESSAGE,
        inactivity_warning=True,
    )
    return {
        'conversation_id': str(conversation.pk),
        'message': INACTIVITY_WARNING_MESSAGE,
        'inactivity': 'warning',
    }


def close_if_inactive(
    conversation: ChatConversation,
    current_time: datetime | None = None,
) -> dict[str, Any] | None:
    """Cierra la conversación cuando se cumplen los 2 minutos del aviso.

    Solo cierra si el usuario no volvió a escribir después del aviso. El
    ``UPDATE`` condicional garantiza un único cierre aunque haya varios
    procesos revisando la misma conversación.
    """
    current_time = current_time or timezone.now()
    if conversation.status != ChatConversation.STATUS_ACTIVE:
        return None
    if conversation.case_conversation_id is not None:
        return None

    cutoff = current_time - INACTIVITY_CLOSE_TIMEOUT
    claimed = _manager(ChatConversation).filter(
        pk=conversation.pk,
        status=ChatConversation.STATUS_ACTIVE,
        inactivity_warned_at__isnull=False,
        inactivity_warned_at__lte=cutoff,
        last_user_activity_at__lte=F('inactivity_warned_at'),
    ).update(
        status=ChatConversation.STATUS_ENDED,
        flow_state='ended',
    )
    if not claimed:
        return None

    conversation.refresh_from_db(fields=['status', 'flow_state'])
    _append_bot_message(
        conversation,
        INACTIVITY_CLOSED_MESSAGE,
        inactivity_closed=True,
    )
    return {
        'conversation_id': str(conversation.pk),
        'message': INACTIVITY_CLOSED_MESSAGE,
        'inactivity': 'closed',
    }


def close_expired_conversation(
    conversation: ChatConversation,
    current_time: datetime | None = None,
) -> dict[str, Any] | None:
    """Cierra una conversación vencida cuando llega un mensaje nuevo.

    Cubre el caso en que el proceso programado aún no pasó: si el usuario
    escribe después de los 7 minutos, la conversación anterior se cierra (con
    su aviso de cierre) y el llamador inicia una nueva sesión.
    """
    current_time = current_time or timezone.now()
    if not conversation_expired(conversation, current_time):
        return None

    claim_filters: dict[str, Any] = {
        'pk': conversation.pk,
        'status': ChatConversation.STATUS_ACTIVE,
    }
    if conversation.inactivity_warned_at is not None:
        claim_filters['inactivity_warned_at__lte'] = (
            current_time - INACTIVITY_CLOSE_TIMEOUT
        )
    else:
        claim_filters['inactivity_warned_at__isnull'] = True
        claim_filters['last_user_activity_at__lte'] = (
            current_time - INACTIVITY_TOTAL_TIMEOUT
        )
    claimed = _manager(ChatConversation).filter(**claim_filters).update(
        status=ChatConversation.STATUS_ENDED,
        flow_state='ended',
    )
    if not claimed:
        # La conversación ya fue cerrada por otro proceso (o el usuario volvió
        # a escribir justo antes del UPDATE). No hay que hacer nada.
        return None

    conversation.refresh_from_db(fields=['status', 'flow_state'])
    _append_bot_message(
        conversation,
        INACTIVITY_CLOSED_MESSAGE,
        inactivity_closed=True,
    )
    return {
        'conversation_id': str(conversation.pk),
        'message': INACTIVITY_CLOSED_MESSAGE,
        'inactivity': 'closed',
    }


def backfill_last_user_activity() -> int:
    """Completa conversaciones históricas creadas antes de la migración."""
    return _manager(ChatConversation).filter(
        last_user_activity_at__isnull=True,
    ).update(last_user_activity_at=F('updated_at'))
