"""Pruebas unitarias de los modelos de la integración Meta en communications.

Cubren invariantes de persistencia (unicidad, cascadas, valores por defecto),
las propiedades calculadas que consume la UI y el webhook, y la progresión de
estados de los destinatarios. No se llama a la API real de Meta.
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from communications.models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    ContactEvent,
    MessageTemplate,
    SegmentMembership,
    WhatsAppWebhookEvent,
)


def make_contact(index: int, **kwargs) -> Contact:
    """Crea un contacto con documento y teléfono únicos."""
    defaults = {
        "full_name": f"Contacto {index}",
        "document_number": f"CC-{index}",
        "phone": f"5730000000{index:02d}",
        "whatsapp_opt_in": Contact.OptInStatus.SUSCRITO,
    }
    defaults.update(kwargs)
    return Contact.objects.create(**defaults)


def make_campaign(name: str = "Campaña Meta", segment=None) -> Campaign:
    """Crea una campaña con el snapshot de plantilla que usa el envío."""
    segment = segment or AudienceSegment.objects.create(name=f"Segmento {name}")
    return Campaign.objects.create(
        name=name,
        segment=segment,
        template_meta_id="999",
        template_name="recordatorio_web",
        template_language="es_CO",
        template_snapshot={
            "body_text": "Hola {{1}}, recuerda tu fecha {{2}}.",
            "header_type": "none",
            "header_media_url": "",
        },
    )


class WhatsAppWebhookEventTests(TestCase):
    def test_event_key_es_unico(self):
        WhatsAppWebhookEvent.objects.create(
            event_key="status:wamid.1:sent",
            provider_message_id="wamid.1",
            event_type=WhatsAppWebhookEvent.Type.STATUS,
            status="sent",
        )

        # El savepoint evita que el IntegrityError deje rota la transacción
        # del TestCase (Django exige rollback y no permite seguir consultando).
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WhatsAppWebhookEvent.objects.create(
                    event_key="status:wamid.1:sent",
                    provider_message_id="wamid.1",
                    event_type=WhatsAppWebhookEvent.Type.STATUS,
                    status="sent",
                )

        self.assertEqual(WhatsAppWebhookEvent.objects.count(), 1)

    def test_processed_at_nace_nulo_y_se_puede_marcar(self):
        event = WhatsAppWebhookEvent.objects.create(
            event_key="inbound:wamid.2",
            provider_message_id="wamid.2",
            event_type=WhatsAppWebhookEvent.Type.INBOUND,
        )
        self.assertIsNone(event.processed_at)

        event.processed_at = timezone.now()
        event.save(update_fields=["processed_at"])
        event.refresh_from_db()

        self.assertIsNotNone(event.processed_at)

    def test_registra_inbound_y_status(self):
        inbound = WhatsAppWebhookEvent.objects.create(
            event_key="inbound:wamid.3",
            provider_message_id="wamid.3",
            event_type=WhatsAppWebhookEvent.Type.INBOUND,
        )
        status = WhatsAppWebhookEvent.objects.create(
            event_key="status:wamid.4:read",
            provider_message_id="wamid.4",
            event_type=WhatsAppWebhookEvent.Type.STATUS,
            status="read",
        )

        self.assertEqual(inbound.event_type, WhatsAppWebhookEvent.Type.INBOUND)
        self.assertEqual(status.event_type, WhatsAppWebhookEvent.Type.STATUS)
        self.assertEqual(WhatsAppWebhookEvent.Type.values, ["inbound", "status"])

    def test_actualizacion_de_plantilla_se_guarda_como_status(self):
        # El webhook no crea un tipo nuevo: las plantillas viven en Meta y el
        # evento queda como `status` con el nombre del cambio en `status`.
        event = WhatsAppWebhookEvent.objects.create(
            event_key="template:message_template_status_update:aviso:es_CO:APPROVED",
            provider_message_id="aviso",
            event_type=WhatsAppWebhookEvent.Type.STATUS,
            status="approved",
            payload={"message_template_name": "aviso", "event": "APPROVED"},
        )

        self.assertEqual(event.event_type, WhatsAppWebhookEvent.Type.STATUS)
        self.assertEqual(event.status, "approved")
        self.assertEqual(event.payload["message_template_name"], "aviso")

    def test_payload_por_defecto_y_motivo_de_failed(self):
        event = WhatsAppWebhookEvent.objects.create(
            event_key="inbound:wamid.5",
            provider_message_id="wamid.5",
            event_type=WhatsAppWebhookEvent.Type.INBOUND,
        )
        self.assertEqual(event.payload, {})

        failed = WhatsAppWebhookEvent.objects.create(
            event_key="status:wamid.6:failed",
            provider_message_id="wamid.6",
            event_type=WhatsAppWebhookEvent.Type.STATUS,
            status="failed",
            payload={
                "recipient_id": "573001112233",
                "errors": [{"code": 131047, "title": "Destinatario sin WhatsApp"}],
            },
        )
        failed.refresh_from_db()

        self.assertEqual(failed.payload["errors"][0]["code"], 131047)

    def test_str_y_orden_descendente_por_created_at(self):
        first = WhatsAppWebhookEvent.objects.create(
            event_key="inbound:wamid.7",
            provider_message_id="wamid.7",
            event_type=WhatsAppWebhookEvent.Type.INBOUND,
        )
        second = WhatsAppWebhookEvent.objects.create(
            event_key="inbound:wamid.8",
            provider_message_id="wamid.8",
            event_type=WhatsAppWebhookEvent.Type.INBOUND,
        )
        WhatsAppWebhookEvent.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        WhatsAppWebhookEvent.objects.filter(pk=second.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        self.assertEqual(
            list(WhatsAppWebhookEvent.objects.values_list("event_key", flat=True)),
            [second.event_key, first.event_key],
        )
        self.assertEqual(str(first), "inbound: wamid.7")


class BroadcastRecipientTests(TestCase):
    def setUp(self):
        self.contact = make_contact(1)
        self.segment = AudienceSegment.objects.create(name="Aspirantes")
        self.segment.contacts.add(self.contact)
        self.campaign = make_campaign("Recordatorio", segment=self.segment)
        self.recipient = BroadcastRecipient.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            phone_snapshot=self.contact.phone,
        )

    def test_estado_inicial_y_valores_por_defecto(self):
        self.assertEqual(self.recipient.status, BroadcastRecipient.Status.PENDING)
        self.assertEqual(self.recipient.provider_message_id, "")
        self.assertEqual(self.recipient.provider, "")
        self.assertEqual(self.recipient.params, {})
        self.assertIsNone(self.recipient.queued_at)
        self.assertIsNone(self.recipient.sent_at)
        self.assertIsNone(self.recipient.delivered_at)
        self.assertIsNone(self.recipient.read_at)

    def test_progresion_pending_a_read(self):
        recipient = self.recipient

        recipient.status = BroadcastRecipient.Status.QUEUED
        recipient.queued_at = timezone.now()
        recipient.save(update_fields=["status", "queued_at"])
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, BroadcastRecipient.Status.QUEUED)
        self.assertIsNotNone(recipient.queued_at)

        recipient.status = BroadcastRecipient.Status.SENT
        recipient.provider_message_id = "wamid.outbound.1"
        recipient.sent_at = timezone.now()
        recipient.save(update_fields=["status", "provider_message_id", "sent_at"])
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, BroadcastRecipient.Status.SENT)
        self.assertEqual(recipient.provider_message_id, "wamid.outbound.1")
        self.assertIsNotNone(recipient.sent_at)

        recipient.status = BroadcastRecipient.Status.DELIVERED
        recipient.delivered_at = timezone.now()
        recipient.save(update_fields=["status", "delivered_at"])
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, BroadcastRecipient.Status.DELIVERED)
        self.assertIsNotNone(recipient.delivered_at)

        recipient.status = BroadcastRecipient.Status.READ
        recipient.read_at = timezone.now()
        recipient.save(update_fields=["status", "read_at"])
        recipient.refresh_from_db()
        self.assertEqual(recipient.status, BroadcastRecipient.Status.READ)
        self.assertIsNotNone(recipient.read_at)

    def test_estado_opted_out_y_failed(self):
        opted_out = BroadcastRecipient.objects.create(
            campaign=self.campaign,
            contact=make_contact(2),
            phone_snapshot="573000000002",
            status=BroadcastRecipient.Status.OPTED_OUT,
        )
        self.assertEqual(opted_out.status, "opted_out")

        failed = BroadcastRecipient.objects.create(
            campaign=self.campaign,
            contact=make_contact(3),
            phone_snapshot="573000000003",
            status=BroadcastRecipient.Status.FAILED,
            provider_message_id="wamid.failed.1",
            error_message="Destinatario sin WhatsApp",
        )
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error_message, "Destinatario sin WhatsApp")
        self.assertIsNone(failed.sent_at)

    def test_provider_message_id_identifica_el_mensaje_de_meta(self):
        self.recipient.provider_message_id = "wamid.outbound.9"
        self.recipient.save(update_fields=["provider_message_id"])

        self.assertEqual(
            BroadcastRecipient.objects.get(pk=self.recipient.pk).provider_message_id,
            "wamid.outbound.9",
        )

    def test_unicidad_campaña_contacto(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BroadcastRecipient.objects.create(
                    campaign=self.campaign,
                    contact=self.contact,
                    phone_snapshot=self.contact.phone,
                )

    def test_phone_snapshot_no_cambia_con_el_contacto(self):
        self.contact.phone = "573009998877"
        self.contact.save(update_fields=["phone"])

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.phone_snapshot, "573000000001")

    def test_str_y_orden_por_id(self):
        second = BroadcastRecipient.objects.create(
            campaign=self.campaign,
            contact=make_contact(4),
            phone_snapshot="573000000004",
        )

        self.assertEqual(str(second), f"{second.campaign_id} → 573000000004 (pending)")
        self.assertEqual(
            list(BroadcastRecipient.objects.values_list("id", flat=True)),
            [self.recipient.id, second.id],
        )


class ContactEventTests(TestCase):
    def setUp(self):
        self.contact = make_contact(1)
        self.segment = AudienceSegment.objects.create(name="Aspirantes")
        self.campaign = make_campaign("Recordatorio", segment=self.segment)
        self.recipient = BroadcastRecipient.objects.create(
            campaign=self.campaign,
            contact=self.contact,
            phone_snapshot=self.contact.phone,
            status=BroadcastRecipient.Status.DELIVERED,
            provider_message_id="wamid.1",
            delivered_at=timezone.now(),
        )

    def test_creacion_y_relacion_con_contacto(self):
        event = ContactEvent.objects.create(
            contact=self.contact,
            event_type=ContactEvent.EventType.MESSAGE_DELIVERED,
            payload={"provider_message_id": "wamid.1", "status": "delivered"},
        )

        self.assertEqual(self.contact.events.count(), 1)
        self.assertEqual(event.contact, self.contact)
        self.assertEqual(event.channel, "whatsapp")
        self.assertEqual(event.event_type, "message_delivered")
        self.assertIsNone(event.campaign)
        self.assertIsNone(event.broadcast_recipient)

    def test_se_puede_vincular_a_campaña_y_destinatario(self):
        event = ContactEvent.objects.create(
            contact=self.contact,
            event_type=ContactEvent.EventType.MESSAGE_SENT,
            campaign=self.campaign,
            broadcast_recipient=self.recipient,
        )

        self.assertEqual(event.campaign, self.campaign)
        self.assertEqual(event.broadcast_recipient, self.recipient)
        self.assertEqual(self.campaign.events.count(), 1)
        self.assertEqual(self.recipient.events.count(), 1)

    def test_tipos_de_evento(self):
        self.assertEqual(
            ContactEvent.EventType.values,
            [
                "message_sent",
                "message_delivered",
                "message_read",
                "message_failed",
                "message_replied",
                "opted_out",
                "segment_added",
                "note",
            ],
        )

    def test_payload_por_defecto_y_str(self):
        event = ContactEvent.objects.create(
            contact=self.contact,
            event_type=ContactEvent.EventType.NOTE,
        )

        self.assertEqual(event.payload, {})
        self.assertEqual(
            str(event), f"{self.contact.pk} · {event.get_event_type_display()}"
        )
        self.assertEqual(event.get_event_type_display(), "Nota interna")

    def test_orden_descendente_por_created_at(self):
        first = ContactEvent.objects.create(
            contact=self.contact, event_type=ContactEvent.EventType.MESSAGE_SENT
        )
        second = ContactEvent.objects.create(
            contact=self.contact, event_type=ContactEvent.EventType.MESSAGE_READ
        )
        ContactEvent.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        ContactEvent.objects.filter(pk=second.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        self.assertEqual(
            list(ContactEvent.objects.values_list("id", flat=True)),
            [second.id, first.id],
        )

    def test_eliminar_contacto_borra_sus_eventos(self):
        ContactEvent.objects.create(
            contact=self.contact, event_type=ContactEvent.EventType.MESSAGE_SENT
        )

        self.contact.delete()

        self.assertEqual(ContactEvent.objects.count(), 0)

    def test_al_borrar_la_campaña_las_referencias_quedan_en_null(self):
        event = ContactEvent.objects.create(
            contact=self.contact,
            event_type=ContactEvent.EventType.MESSAGE_SENT,
            campaign=self.campaign,
            broadcast_recipient=self.recipient,
        )

        self.campaign.delete()

        event.refresh_from_db()
        self.assertIsNone(event.campaign)
        self.assertIsNone(event.broadcast_recipient)

    def test_al_borrar_el_destinatario_la_referencia_queda_en_null(self):
        event = ContactEvent.objects.create(
            contact=self.contact,
            event_type=ContactEvent.EventType.MESSAGE_DELIVERED,
            broadcast_recipient=self.recipient,
        )

        self.recipient.delete()

        event.refresh_from_db()
        self.assertIsNone(event.broadcast_recipient)
        self.assertEqual(event.contact, self.contact)


class MessageTemplateTests(TestCase):
    def test_categorias_y_valor_por_defecto(self):
        default = MessageTemplate.objects.create(name="Aviso", body_text="Hola")
        self.assertEqual(default.category, MessageTemplate.Category.UTILITY)
        self.assertEqual(default.category, "utility")

        for value in ("marketing", "authentication"):
            template = MessageTemplate.objects.create(
                name=f"Plantilla {value}", body_text="Hola", category=value
            )
            self.assertEqual(template.category, value)

        self.assertEqual(
            MessageTemplate.Category.values, ["marketing", "utility", "authentication"]
        )

    def test_tipos_de_header_y_valores_por_defecto(self):
        template = MessageTemplate.objects.create(name="Sin header", body_text="Hola")
        self.assertEqual(template.header_type, MessageTemplate.HeaderType.NONE)
        self.assertEqual(template.header_type, "none")
        self.assertEqual(template.header_text, "")
        self.assertEqual(template.header_media_url, "")

        for value in ("text", "image", "video", "document"):
            template = MessageTemplate.objects.create(
                name=f"Header {value}", body_text="Hola", header_type=value
            )
            self.assertEqual(template.header_type, value)

        self.assertEqual(
            MessageTemplate.HeaderType.values,
            ["none", "text", "image", "video", "document"],
        )

    def test_param_count_cuenta_variables_distintas(self):
        template = MessageTemplate(
            name="Recordatorio",
            body_text="Hola {{1}}, tu cita es el {{2}}. Repite {{1}}.",
        )
        self.assertEqual(template.param_count, 2)

        self.assertEqual(
            MessageTemplate(name="Sin vars", body_text="Hola").param_count, 0
        )
        self.assertEqual(
            MessageTemplate(name="Una", body_text="Hola {{10}}").param_count, 1
        )

    def test_param_count_ignora_llaves_sin_numero(self):
        template = MessageTemplate(name="Rara", body_text="Hola {{nombre}} y {{}}")

        self.assertEqual(template.param_count, 0)

    def test_el_borrador_no_replica_el_estado_de_meta(self):
        # Desde la migración 0006 MessageTemplate es solo un borrador local:
        # `meta_template_name` y `status` se eliminaron y viven en Meta.
        template = MessageTemplate.objects.create(name="Borrador", body_text="Hola")

        self.assertFalse(hasattr(template, "meta_template_name"))
        self.assertFalse(hasattr(template, "status"))

    def test_valores_por_defecto_de_campos_json(self):
        template = MessageTemplate.objects.create(name="JSON", body_text="Hola {{1}}")

        self.assertEqual(template.variable_types, {})
        self.assertEqual(template.buttons, [])

    def test_orden_por_nombre_y_str(self):
        MessageTemplate.objects.create(name="Beta", body_text="Hola")
        MessageTemplate.objects.create(name="Alfa", body_text="Hola")

        self.assertEqual(
            list(MessageTemplate.objects.values_list("name", flat=True)),
            ["Alfa", "Beta"],
        )
        self.assertEqual(str(MessageTemplate.objects.get(name="Beta")), "Beta")


class CampaignMetaTests(TestCase):
    def setUp(self):
        self.segment = AudienceSegment.objects.create(name="Aspirantes")
        self.campaign = make_campaign("Recordatorio", segment=self.segment)

    def test_estado_inicial_y_canal_fijo(self):
        self.assertEqual(self.campaign.status, Campaign.Status.DRAFT)
        self.assertEqual(self.campaign.status, "draft")
        self.assertEqual(self.campaign.channel, "whatsapp")
        self.assertFalse(Campaign._meta.get_field("channel").editable)

    def test_valores_por_defecto(self):
        campaign = Campaign.objects.create(name="Sin snapshot", segment=self.segment)

        self.assertEqual(campaign.template_meta_id, "")
        self.assertEqual(campaign.template_name, "")
        self.assertEqual(campaign.template_language, "es_CO")
        self.assertEqual(campaign.template_snapshot, {})
        self.assertEqual(campaign.default_params, {})
        self.assertEqual(campaign.rate_limit_per_minute, 60)
        self.assertIsNone(campaign.scheduled_at)
        self.assertIsNone(campaign.sent_at)

    def test_snapshot_guarda_la_plantilla_para_enviarla(self):
        self.assertEqual(self.campaign.template_meta_id, "999")
        self.assertEqual(self.campaign.template_name, "recordatorio_web")
        self.assertEqual(
            self.campaign.template_snapshot["body_text"],
            "Hola {{1}}, recuerda tu fecha {{2}}.",
        )

    def test_estados_disponibles(self):
        self.assertEqual(
            Campaign.Status.values,
            [
                "draft",
                "scheduled",
                "sending",
                "sent",
                "paused",
                "cancelled",
                "failed",
            ],
        )

    def test_metricas_de_destinatarios(self):
        statuses = [
            (BroadcastRecipient.Status.PENDING, {}),
            (BroadcastRecipient.Status.OPTED_OUT, {}),
            (BroadcastRecipient.Status.QUEUED, {}),
            (BroadcastRecipient.Status.SENT, {"provider_message_id": "wamid.1"}),
            (BroadcastRecipient.Status.DELIVERED, {"provider_message_id": "wamid.2"}),
            (BroadcastRecipient.Status.READ, {"provider_message_id": "wamid.3"}),
            (BroadcastRecipient.Status.FAILED, {"error_message": "falló"}),
        ]
        for index, (status, extra) in enumerate(statuses, start=1):
            BroadcastRecipient.objects.create(
                campaign=self.campaign,
                contact=make_contact(index),
                phone_snapshot=f"5730000000{index:02d}",
                status=status,
                **extra,
            )

        self.assertEqual(self.campaign.total_recipients, 7)
        # Solo cuentan como enviados los que no están pending ni excluidos.
        self.assertEqual(self.campaign.sent_count, 5)
        self.assertEqual(self.campaign.delivered_count, 2)
        self.assertEqual(self.campaign.read_count, 1)
        self.assertEqual(self.campaign.failed_count, 1)

    def test_el_segmento_esta_protegido(self):
        with self.assertRaises(ProtectedError):
            self.segment.delete()

        self.assertTrue(Campaign.objects.filter(pk=self.campaign.pk).exists())

    def test_str(self):
        self.assertEqual(str(self.campaign), "Recordatorio")


class AudienceSegmentTests(TestCase):
    def setUp(self):
        self.segment = AudienceSegment.objects.create(name="Aspirantes")
        self.contact = make_contact(1)

    def test_origen_por_defecto_y_valores(self):
        self.assertEqual(
            self.segment.source_type, AudienceSegment.SourceType.EXCEL_IMPORT
        )
        self.assertEqual(self.segment.source_type, "excel_import")
        self.assertEqual(self.segment.filter_rules, {})
        self.assertEqual(
            AudienceSegment.SourceType.values,
            ["excel_import", "manual", "dynamic"],
        )

    def test_contact_count_y_miembros(self):
        self.assertEqual(self.segment.contact_count, 0)

        SegmentMembership.objects.create(segment=self.segment, contact=self.contact)

        self.assertEqual(self.segment.contact_count, 1)
        self.assertEqual(self.contact.segments.count(), 1)

    def test_miembros_unicos_por_segmento(self):
        SegmentMembership.objects.create(segment=self.segment, contact=self.contact)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SegmentMembership.objects.create(
                    segment=self.segment, contact=self.contact
                )

    def test_eliminar_segmento_borra_miembros_pero_no_contactos(self):
        SegmentMembership.objects.create(segment=self.segment, contact=self.contact)

        self.segment.delete()

        self.assertEqual(SegmentMembership.objects.count(), 0)
        self.assertTrue(Contact.objects.filter(pk=self.contact.pk).exists())

    def test_str_y_orden_descendente(self):
        older = AudienceSegment.objects.create(name="Viejo")
        AudienceSegment.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        AudienceSegment.objects.filter(pk=self.segment.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

        self.assertEqual(
            list(AudienceSegment.objects.values_list("name", flat=True)),
            [self.segment.name, older.name],
        )
        self.assertEqual(str(self.segment), "Aspirantes")
