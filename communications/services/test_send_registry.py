"""Registro de envíos de prueba para correlacionar los webhooks de Meta."""

from django.utils import timezone

from ..models import WhatsAppWebhookEvent

TEST_SEND_KEY_PREFIX = "test-send:"


def record_test_send(phone: str, wamid: str, kind: str, detail: str):
    """Guarda el wamid devuelto por Meta para correlacionarlo con webhooks."""
    if not wamid:
        return None
    event, _ = WhatsAppWebhookEvent.objects.get_or_create(
        event_key=f"{TEST_SEND_KEY_PREFIX}{wamid}",
        defaults={
            "provider_message_id": wamid,
            "event_type": WhatsAppWebhookEvent.Type.STATUS,
            "status": kind,
            "payload": {"to": phone, "detail": detail},
            "processed_at": timezone.now(),
        },
    )
    return event
