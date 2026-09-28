"""Pruebas del comando `cleanup_whatsapp_events` (retención de eventos)."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from communications.models import WhatsAppWebhookEvent


def make_event(
    event_type,
    status="",
    age_days=1,
    processed_at_days_ago=1,
    seq=None,
):
    """Crea un evento y luego le fija created_at en el pasado.

    `created_at` es auto_now_add, así que Django lo sobreescribe al insertar;
    por eso se corrige con un update posterior.
    """
    seq = seq or [0]
    seq[0] += 1
    event = WhatsAppWebhookEvent.objects.create(
        event_key=f"key-{seq[0]}-{age_days}-{event_type}-{status or 'none'}",
        provider_message_id=f"wamid.SEED-{seq[0]}",
        event_type=event_type,
        status=status,
        processed_at=timezone.now() - timedelta(days=processed_at_days_ago),
    )
    WhatsAppWebhookEvent.objects.filter(pk=event.pk).update(
        created_at=timezone.now() - timedelta(days=age_days)
    )
    return event


class CleanupWhatsappEventsTests(TestCase):
    def setUp(self):
        # Eventos de estado antiguos (borrables): sent, delivered, read
        self.old_sent = make_event(WhatsAppWebhookEvent.Type.STATUS, "sent", age_days=40)
        self.old_delivered = make_event(
            WhatsAppWebhookEvent.Type.STATUS, "delivered", age_days=35
        )
        self.old_read = make_event(WhatsAppWebhookEvent.Type.STATUS, "read", age_days=40)
        # Antiguos pero con valor diagnóstico (se conservan)
        self.old_failed = make_event(WhatsAppWebhookEvent.Type.STATUS, "failed", age_days=45)
        self.old_inbound = make_event(WhatsAppWebhookEvent.Type.INBOUND, age_days=50)
        # Recientes (se conservan por edad)
        self.recent_sent = make_event(WhatsAppWebhookEvent.Type.STATUS, "sent", age_days=5)

    def run_command(self, *args, **kwargs):
        out = StringIO()
        call_command(
            "cleanup_whatsapp_events", *args, stdout=out, stderr=StringIO(), **kwargs
        )
        return out.getvalue()

    def test_dry_run_deletes_nothing(self):
        out = self.run_command("--days", "30")
        self.assertIn("Modo ensayo", out)
        self.assertEqual(WhatsAppWebhookEvent.objects.count(), 6)

    def test_ejecutar_deletes_only_old_status_events(self):
        out = self.run_command("--days", "30", "--ejecutar")
        self.assertIn("Borrados 3", out)
        self.assertEqual(WhatsAppWebhookEvent.objects.count(), 3)
        remaining = set(
            WhatsAppWebhookEvent.objects.values_list("event_type", "status")
        )
        self.assertEqual(
            remaining,
            {
                (WhatsAppWebhookEvent.Type.STATUS, "failed"),
                (WhatsAppWebhookEvent.Type.INBOUND, ""),
                (WhatsAppWebhookEvent.Type.STATUS, "sent"),  # el reciente
            },
        )

    def test_keeps_failed_and_inbound(self):
        # Umbral agresivo (1 día): aun así los 'failed' y los 'inbound' se conservan.
        self.run_command("--days", "1", "--ejecutar")
        count = WhatsAppWebhookEvent.objects.count()
        self.assertTrue(WhatsAppWebhookEvent.objects.filter(pk=self.old_failed.pk).exists())
        self.assertTrue(WhatsAppWebhookEvent.objects.filter(pk=self.old_inbound.pk).exists())
        # Los 4 estados de envío (3 antiguos + el reciente de 5 días) se borran.
        self.assertFalse(WhatsAppWebhookEvent.objects.filter(pk=self.recent_sent.pk).exists())
        self.assertEqual(count, 2)

    def test_default_threshold_is_30_days(self):
        # El reciente (5 días) y los de menos de 30 se conservan con el default.
        self.run_command("--ejecutar")
        self.assertTrue(WhatsAppWebhookEvent.objects.filter(pk=self.recent_sent.pk).exists())
        self.assertFalse(WhatsAppWebhookEvent.objects.filter(pk=self.old_sent.pk).exists())

    def test_invalid_days_rejected(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self.run_command("--days", "0", "--ejecutar")