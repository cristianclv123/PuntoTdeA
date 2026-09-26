# Lógica de creación/orquestación de campañas
"""Lógica de creación, resolución de destinatarios y envío de campañas.

Por ahora el envío es síncrono usando MockAdapter (sin Redis/Celery todavía).
Cuando se conecte Celery, solo hay que envolver `send_campaign` en una tarea
`@shared_task` y trocear `recipients` en lotes — la lógica de negocio de acá
no cambia.
"""

import random
from django.utils import timezone

from ..adapters.mock_adapter import MockAdapter
from ..models import BroadcastRecipient, Campaign, Contact, ContactEvent
from .logging_service import log_event

# Único lugar donde se decide qué adaptador se usa hoy.
# El día que se conecte Twilio o Meta, se cambia esta línea (o se hace
# configurable por Campaign) y el resto del servicio sigue igual.
DEFAULT_ADAPTER = MockAdapter()


def resolve_recipients(campaign: Campaign) -> list[BroadcastRecipient]:
    """Crea (si no existen) los BroadcastRecipient para cada contacto del
    segmento de la campaña. Es idempotente: correrlo varias veces no duplica."""
    existing_contact_ids = set(
        campaign.recipients.values_list("contact_id", flat=True)
    )
    to_create = []
    for contact in campaign.segment.contacts.all():
        if contact.id in existing_contact_ids:
            continue
        to_create.append(
            BroadcastRecipient(
                campaign=campaign,
                contact=contact,
                phone_snapshot=contact.phone,
                params=_render_params(campaign, contact),
            )
        )
    if to_create:
        BroadcastRecipient.objects.bulk_create(to_create)
    return list(campaign.recipients.all())


def _render_params(campaign: Campaign, contact: Contact) -> dict:
    """Combina los parámetros por defecto de la campaña con datos del
    contacto. Un valor tipo "contact.full_name" se resuelve dinámicamente
    contra el contacto (soporta personalización tipo {{1}} = nombre)."""
    resolved = {}
    for key, value in campaign.default_params.items():
        if isinstance(value, str) and value.startswith("contact."):
            attr = value.split(".", 1)[1]
            resolved[key] = getattr(contact, attr, "") or contact.attributes.get(attr, "")
        else:
            resolved[key] = value
    return resolved


def send_campaign(campaign: Campaign, adapter=None) -> Campaign:
    """Envía (o simula el envío de) una campaña a todos sus destinatarios
    pendientes. Actualiza estados y deja rastro en ContactEvent."""
    adapter = adapter or DEFAULT_ADAPTER

    resolve_recipients(campaign)
    campaign.status = Campaign.Status.SENDING
    campaign.save(update_fields=["status"])

    for recipient in campaign.recipients.filter(status=BroadcastRecipient.Status.PENDING):
        if recipient.contact.whatsapp_opt_in == Contact.OptInStatus.BAJA:
            recipient.status = BroadcastRecipient.Status.OPTED_OUT
            recipient.save(update_fields=["status"])
            continue

        result = adapter.send_template_message(
            to=recipient.phone_snapshot,
            template=campaign.template,
            params=recipient.params,
        )

        if result.success:
            recipient.status = BroadcastRecipient.Status.SENT
            recipient.provider = adapter.provider_name
            recipient.provider_message_id = result.provider_message_id
            recipient.sent_at = timezone.now()
            recipient.save()
            log_event(
                recipient.contact,
                ContactEvent.EventType.MESSAGE_SENT,
                campaign=campaign,
                broadcast_recipient=recipient,
            )
            if adapter.provider_name == "mock":
                _simulate_delivery(recipient, campaign)
        else:
            recipient.status = BroadcastRecipient.Status.FAILED
            recipient.error_message = result.error
            recipient.save()
            log_event(
                recipient.contact,
                ContactEvent.EventType.MESSAGE_FAILED,
                campaign=campaign,
                broadcast_recipient=recipient,
                payload={"error": result.error},
            )

    campaign.status = Campaign.Status.SENT
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=["status", "sent_at"])
    return campaign


def _simulate_delivery(recipient: BroadcastRecipient, campaign: Campaign) -> None:
    """Solo para el MockAdapter: simula entrega/lectura para que las
    métricas de la campaña (sent/delivered/read) se vean realistas en el
    demo mientras no hay webhooks reales de Twilio/Meta conectados."""
    now = timezone.now()

    if random.random() < 0.95:  # ~95% de entrega, similar a datos reales
        recipient.status = BroadcastRecipient.Status.DELIVERED
        recipient.delivered_at = now
        log_event(
            recipient.contact,
            ContactEvent.EventType.MESSAGE_DELIVERED,
            campaign=campaign,
            broadcast_recipient=recipient,
        )

        if random.random() < 0.80:  # de lo entregado, ~80% se lee
            recipient.status = BroadcastRecipient.Status.READ
            recipient.read_at = now
            log_event(
                recipient.contact,
                ContactEvent.EventType.MESSAGE_READ,
                campaign=campaign,
                broadcast_recipient=recipient,
            )
        recipient.save()


def pause_campaign(campaign: Campaign) -> Campaign:
    """HU-07: pausar una campaña programada antes de que salga."""
    if campaign.status in (Campaign.Status.SCHEDULED, Campaign.Status.SENDING):
        campaign.status = Campaign.Status.PAUSED
        campaign.save(update_fields=["status"])
    return campaign


def resume_campaign(campaign: Campaign) -> Campaign:
    if campaign.status == Campaign.Status.PAUSED:
        campaign.status = (
            Campaign.Status.SCHEDULED if campaign.scheduled_at else Campaign.Status.DRAFT
        )
        campaign.save(update_fields=["status"])
    return campaign


def cancel_campaign(campaign: Campaign) -> Campaign:
    """HU-07: cancelar antes de la salida."""
    if campaign.status in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED, Campaign.Status.PAUSED):
        campaign.status = Campaign.Status.CANCELLED
        campaign.save(update_fields=["status"])
    return campaign