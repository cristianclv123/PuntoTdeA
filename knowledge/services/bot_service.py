"""Decide si el bot puede responder o si debe transferir el caso a un asesor.

Contrato acordado con cases/services/bot_intake.py::create_ticket_from_bot.
"""
from django.conf import settings

from cases.services import create_ticket_from_bot

from ..models import Intent
from .rag_service import answer_query

ESCALATION_INTENT_NAME = "Solicitar Asesor"

ESCALATION_KEYWORDS = ["asesor", "humano", "persona", "hablar con alguien", "soporte"]


def _confidence_threshold() -> float:
    """Umbral configurado en el Intent 'Solicitar Asesor' (Admin); si aún no
    existe, usa el umbral global de settings.KNOWLEDGE_SETTINGS como respaldo."""
    threshold = (
        Intent.objects.filter(name=ESCALATION_INTENT_NAME, is_active=True)
        .values_list("confidence_threshold", flat=True)
        .first()
    )
    if threshold is not None:
        return threshold
    return settings.KNOWLEDGE_SETTINGS.get("MIN_CONFIDENCE", 0.7)


def process_user_message(user_data: dict, user_message: str, conversation_history: list) -> dict:
    """
    1. Evalúa el mensaje con las FAQs/artículos publicados (vía rag_service).
    2. Si la confianza no supera el umbral del Intent, o el usuario pide un
       asesor directamente, escala a cases.
    """
    normalized = (user_message or "").lower()
    if any(keyword in normalized for keyword in ESCALATION_KEYWORDS):
        return trigger_handoff(user_data, "Solicitud directa de asesor", conversation_history)

    response = answer_query(user_message)
    if response["confidence"] < _confidence_threshold():
        theme = f"Consulta no resuelta: {user_message[:80]}"
        return trigger_handoff(user_data, theme, conversation_history)

    return {"status": "bot_response", "answer": response["answer"], "confidence": response["confidence"]}


def trigger_handoff(user_data: dict, theme: str, conversation_history: list, channel_code: str = "web") -> dict:
    """Llama al servicio del módulo cases que recibe y registra el ticket."""
    ticket = create_ticket_from_bot(
        user_data=user_data,
        theme=theme,
        channel_code=channel_code,
        history=conversation_history,
    )
    return {
        "status": "escalated",
        "message": f"Te hemos transferido con un asesor. Tu número de ticket es {ticket.ticket_number}.",
        "ticket_number": ticket.ticket_number,
    }
