# Registro de interacciones (RF-12)
"""Registro de interacciones en la línea de tiempo del contacto (RF-12)."""

from ..models import ContactEvent


def log_event(
    contact,
    event_type: str,
    *,
    channel: str = "whatsapp",
    campaign=None,
    broadcast_recipient=None,
    payload: dict | None = None,
) -> ContactEvent:
    """Crea un ContactEvent. Punto único de escritura para la línea de
    tiempo, así el CDP queda consistente sin importar quién dispara el evento
    (campaign_service, un webhook, o una acción manual de un asesor)."""
    return ContactEvent.objects.create(
        contact=contact,
        event_type=event_type,
        channel=channel,
        campaign=campaign,
        broadcast_recipient=broadcast_recipient,
        payload=payload or {},
    )