# Lógica de creación/orquestación de campañas
"""Lógica de creación, resolución de destinatarios y envío de campañas.

Por ahora el envío es síncrono usando MockAdapter (sin Redis/Celery todavía).
Cuando se conecte Celery, solo hay que envolver `send_campaign` en una tarea
`@shared_task` y trocear `recipients` en lotes — la lógica de negocio de acá
no cambia.
"""

import random
from django.db import transaction
from django.utils import timezone

from ..adapters.base import TemplateRef
from ..adapters.meta_adapter import MetaAdapter
from ..models import BroadcastRecipient, Campaign, Contact, ContactEvent
from .campaign_personalization_service import (
    PersonalizationAuthorizationError,
    assert_authorized_recipients,
    template_variables,
)
from .logging_service import log_event

# Único lugar donde se decide qué adaptador se usa hoy.
# La integración de este proyecto usa exclusivamente Meta WhatsApp Cloud API.
DEFAULT_ADAPTER = MetaAdapter()


class CampaignSendError(Exception):
    """La campaña no supera la validación previa al envío."""


def resolve_recipients(campaign: Campaign) -> list[BroadcastRecipient]:
    """Crea (si no existen) los BroadcastRecipient para cada contacto del
    segmento de la campaña. Es idempotente: correrlo varias veces no duplica."""
    if hasattr(campaign, "personalization"):
        recipients = list(campaign.recipients.select_related("contact").all())
        try:
            assert_authorized_recipients(campaign, recipients)
        except PersonalizationAuthorizationError as exc:
            raise CampaignSendError(str(exc)) from exc
        return recipients

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


def _template_ref(campaign: Campaign) -> TemplateRef:
    """Arma el envío a partir del snapshot guardado en la campaña.

    La plantilla ya no vive en la base local: solo se conserva una copia de sus
    datos en ``campaign.template_snapshot``.
    """
    snapshot = campaign.template_snapshot or {}
    return TemplateRef(
        name=campaign.template_name,
        language=campaign.template_language or "es_CO",
        body_text=snapshot.get("body_text", ""),
        header_type=snapshot.get("header_type", "none"),
        header_text=snapshot.get("header_text", ""),
        header_media_url=snapshot.get("header_media_url", ""),
    )


def send_campaign(campaign: Campaign, adapter=None) -> Campaign:
    """Envía (o simula el envío de) una campaña a todos sus destinatarios
    pendientes. Actualiza estados y deja rastro en ContactEvent."""
    adapter = adapter or DEFAULT_ADAPTER

    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
        if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED):
            raise CampaignSendError(
                f"No se puede enviar una campaña en estado '{campaign.status}'."
            )

        recipients = resolve_recipients(campaign)
        pending_recipients = [
            recipient
            for recipient in recipients
            if recipient.status == BroadcastRecipient.Status.PENDING
        ]
        body_text = (campaign.template_snapshot or {}).get("body_text", "")
        required_variables = template_variables(body_text)
        for recipient in pending_recipients:
            if recipient.contact.whatsapp_opt_in == Contact.OptInStatus.BAJA:
                continue
            if not recipient.phone_snapshot.strip():
                raise CampaignSendError(
                    f"El destinatario {recipient.contact_id} no tiene un teléfono válido."
                )
            params = recipient.params if isinstance(recipient.params, dict) else {}
            for variable in required_variables:
                value = params.get(variable)
                if value is None or not str(value).strip():
                    raise CampaignSendError(
                        f"Falta el valor de {{{{{variable}}}}} para el destinatario "
                        f"{recipient.contact_id}; no se inició ningún envío."
                    )

        campaign.status = Campaign.Status.SENDING
        campaign.save(update_fields=["status"])

    for recipient in pending_recipients:
        if recipient.contact.whatsapp_opt_in == Contact.OptInStatus.BAJA:
            recipient.status = BroadcastRecipient.Status.OPTED_OUT
            recipient.save(update_fields=["status"])
            continue

        result = adapter.send_template_message(
            to=recipient.phone_snapshot,
            template=_template_ref(campaign),
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
    from notifications.events import notify_campaign
    from notifications.models import Notification

    sent = campaign.recipients.filter(status=BroadcastRecipient.Status.SENT).count()
    failed = campaign.recipients.filter(status=BroadcastRecipient.Status.FAILED).count()
    notify_campaign(
        "Campaña enviada",
        f"{campaign.name}: {sent} enviados, {failed} fallidos.",
        event="campaign.sent",
        level=Notification.Level.WARNING if failed else Notification.Level.SUCCESS,
        campaign_id=campaign.id,
    )
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
        from notifications.events import notify_campaign
        from notifications.models import Notification

        notify_campaign(
            "Campaña pausada",
            campaign.name,
            event="campaign.paused",
            level=Notification.Level.WARNING,
            campaign_id=campaign.id,
        )
    return campaign


def resume_campaign(campaign: Campaign) -> Campaign:
    if campaign.status == Campaign.Status.PAUSED:
        campaign.status = (
            Campaign.Status.SCHEDULED if campaign.scheduled_at else Campaign.Status.DRAFT
        )
        campaign.save(update_fields=["status"])
        from notifications.events import notify_campaign
        from notifications.models import Notification

        notify_campaign(
            "Campaña reanudada",
            campaign.name,
            event="campaign.resumed",
            level=Notification.Level.INFO,
            campaign_id=campaign.id,
        )
    return campaign


def cancel_campaign(campaign: Campaign) -> Campaign:
    """HU-07: cancelar antes de la salida."""
    if campaign.status in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED, Campaign.Status.PAUSED):
        campaign.status = Campaign.Status.CANCELLED
        campaign.save(update_fields=["status"])
        from notifications.events import notify_campaign
        from notifications.models import Notification

        notify_campaign(
            "Campaña cancelada",
            campaign.name,
            event="campaign.cancelled",
            level=Notification.Level.WARNING,
            campaign_id=campaign.id,
        )
    return campaign