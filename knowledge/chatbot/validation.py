"""Validaciones independientes de la generación de respuestas."""


MINIMUM_QUESTION_LENGTH = 3


def validate_question(question: str) -> tuple[bool, str]:
    """Return whether a user question can be sent to the responder."""
    normalized = (question or '').strip()
    if not normalized:
        return False, 'Por favor, ingresa una pregunta.'
    if len(normalized) < MINIMUM_QUESTION_LENGTH:
        return False, 'La pregunta es demasiado corta. Intenta explicar un poco más.'
    return True, ''