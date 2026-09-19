"""Adaptador de respuestas; puede reemplazarse por un proveedor LLM."""

from typing import Any, Callable

from ..services.rag_service import answer_query


Responder = Callable[[str], dict[str, Any]]


def generate_response(question: str, responder: Responder = answer_query) -> dict[str, Any]:
    """Generate an answer without owning question validation or conversation state."""
    return responder(question)