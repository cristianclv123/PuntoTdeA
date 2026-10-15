"""Cierre de conversaciones inactivas del chatbot."""

from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from ..models import ChatConversation
from .workflow import ChatbotWorkflow


INACTIVITY_TIMEOUT = timedelta(minutes=5)


def close_if_inactive(
    conversation: ChatConversation,
    current_time: datetime | None = None,
) -> dict[str, Any] | None:
    current_time = current_time or timezone.now()
    messages = conversation.messages if isinstance(conversation.messages, list) else []
    last_message = messages[-1] if messages else None
    has_pending_advisor_response = any(
        isinstance(message, dict) and message.get('awaiting_advisor') is True
        for message in messages
    )
    if (
        conversation.status != ChatConversation.STATUS_ACTIVE
        or conversation.updated_at > current_time - INACTIVITY_TIMEOUT
        or not isinstance(last_message, dict)
        or last_message.get('author') != 'bot'
        or has_pending_advisor_response
    ):
        return None

    return ChatbotWorkflow(conversation).close_for_inactivity()
