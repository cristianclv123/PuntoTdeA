"""Métricas reales de campañas para el dashboard (reemplaza mock_data.py)."""
from django.utils import timezone

from communications.models import BroadcastRecipient, Campaign, ContactEvent


def _format_count(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def campaign_kpis():
    """Tarjetas de métricas agregadas sobre todos los envíos registrados."""
    sent = BroadcastRecipient.objects.exclude(
        status__in=[BroadcastRecipient.Status.PENDING, BroadcastRecipient.Status.OPTED_OUT]
    ).count()
    delivered = BroadcastRecipient.objects.filter(
        status__in=[BroadcastRecipient.Status.DELIVERED, BroadcastRecipient.Status.READ]
    ).count()
    read = BroadcastRecipient.objects.filter(status=BroadcastRecipient.Status.READ).count()
    replies = ContactEvent.objects.filter(event_type=ContactEvent.EventType.MESSAGE_REPLIED).count()
    read_rate = f"{round(read / delivered * 100)}%" if delivered else "0%"

    return [
        {"label": "Mensajes enviados", "value": _format_count(sent), "sub": "campañas WhatsApp"},
        {"label": "Entregados", "value": _format_count(delivered), "sub": "confirmados por canal"},
        {"label": "Tasa de lectura", "value": read_rate, "sub": "sobre entregados"},
        {"label": "Respuestas", "value": _format_count(replies), "sub": "interacciones entrantes"},
    ]


def recent_campaigns(limit=4):
    """Últimas campañas creadas, con sus métricas de entrega/lectura."""
    campaigns = Campaign.objects.select_related("segment").order_by("-created_at")[:limit]
    rows = []
    for campaign in campaigns:
        delivered = campaign.delivered_count
        read = campaign.read_count
        read_pct = f"{round(read / delivered * 100)}%" if delivered else "0%"
        moment = campaign.scheduled_at or campaign.created_at
        rows.append(
            {
                "id": campaign.id,
                "name": campaign.name,
                "channel": campaign.channel,
                "meta": f"{campaign.segment.name} · {timezone.localtime(moment).strftime('%d %b, %I:%M %p')}",
                "segments": [campaign.segment.name],
                "status": campaign.get_status_display().lower(),
                "sent": campaign.sent_count,
                "delivered": delivered,
                "read": read,
                "clicks": 0,
                "replies": ContactEvent.objects.filter(
                    campaign=campaign, event_type=ContactEvent.EventType.MESSAGE_REPLIED
                ).count(),
                "audience": campaign.segment.name,
                "read_pct": read_pct,
            }
        )
    return rows


def recent_activity(limit=4):
    """Últimos eventos de contactos (respuestas, entregas, bajas, etc.)."""
    events = ContactEvent.objects.select_related("contact", "campaign").order_by("-created_at")[:limit]
    rows = []
    for event in events:
        detail = (event.payload or {}).get("detail") or event.get_event_type_display()
        rows.append(
            {
                "at": timezone.localtime(event.created_at).strftime("%Y-%m-%d %H:%M"),
                "person": event.contact.full_name,
                "channel": event.channel,
                "campaign": event.campaign.name if event.campaign else "General",
                "event": event.get_event_type_display().lower(),
                "detail": detail,
            }
        )
    return rows
