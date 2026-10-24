from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from communications.models import AudienceSegment, Campaign
from communications.services import campaign_service


class RunScheduledCampaignsTests(TestCase):
    def setUp(self):
        self.segment = AudienceSegment.objects.create(name="Audiencia de prueba")

    def make_campaign(self, name, status=Campaign.Status.SCHEDULED, scheduled_at=None):
        return Campaign.objects.create(
            name=name,
            segment=self.segment,
            status=status,
            scheduled_at=scheduled_at or timezone.now() - timedelta(minutes=1),
        )

    def run_command(self):
        call_command(
            "run_scheduled_campaigns",
            "--once",
            stdout=StringIO(),
            stderr=StringIO(),
        )

    def test_future_campaign_is_not_sent(self):
        campaign = self.make_campaign(
            "Futura", scheduled_at=timezone.now() + timedelta(minutes=1)
        )

        with patch.object(campaign_service, "send_campaign") as send_campaign:
            self.run_command()

        send_campaign.assert_not_called()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.SCHEDULED)

    def test_due_campaign_is_processed(self):
        campaign = self.make_campaign("Vencida")

        with patch.object(
            campaign_service,
            "send_campaign",
            side_effect=lambda item: Campaign.objects.filter(pk=item.pk).update(
                status=Campaign.Status.SENT
            ),
        ) as send_campaign:
            self.run_command()

        send_campaign.assert_called_once()
        self.assertEqual(send_campaign.call_args.args[0].pk, campaign.pk)
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.SENT)

    def test_paused_and_cancelled_campaigns_are_not_sent(self):
        paused = self.make_campaign("Pausada", status=Campaign.Status.PAUSED)
        cancelled = self.make_campaign("Cancelada", status=Campaign.Status.CANCELLED)

        with patch.object(campaign_service, "send_campaign") as send_campaign:
            self.run_command()

        send_campaign.assert_not_called()
        paused.refresh_from_db()
        cancelled.refresh_from_db()
        self.assertEqual(paused.status, Campaign.Status.PAUSED)
        self.assertEqual(cancelled.status, Campaign.Status.CANCELLED)

    def test_failure_isolated_and_failed_campaign_is_not_retried(self):
        failed = self.make_campaign("Inválida")
        sent = self.make_campaign("Válida")

        def send(campaign):
            if campaign.pk == failed.pk:
                raise campaign_service.CampaignSendError("Falta una variable.")
            Campaign.objects.filter(pk=campaign.pk).update(status=Campaign.Status.SENT)

        with self.assertLogs(
            "communications.management.commands.run_scheduled_campaigns", level="ERROR"
        ) as logs:
            with patch.object(campaign_service, "send_campaign", side_effect=send) as sender:
                self.run_command()

        self.assertEqual(sender.call_count, 2)
        self.assertEqual(len(logs.records), 1)
        self.assertIn(str(failed.pk), logs.records[0].getMessage())
        failed.refresh_from_db()
        sent.refresh_from_db()
        self.assertEqual(failed.status, Campaign.Status.FAILED)
        self.assertEqual(sent.status, Campaign.Status.SENT)

        with patch.object(campaign_service, "send_campaign") as sender:
            self.run_command()

        sender.assert_not_called()

    def test_error_does_not_overwrite_campaign_already_being_sent(self):
        campaign = self.make_campaign("Envío concurrente")

        def send(item):
            Campaign.objects.filter(pk=item.pk).update(status=Campaign.Status.SENDING)
            raise RuntimeError("Fallo posterior al inicio del envío.")

        with self.assertLogs(
            "communications.management.commands.run_scheduled_campaigns", level="ERROR"
        ):
            with patch.object(campaign_service, "send_campaign", side_effect=send):
                self.run_command()

        campaign.refresh_from_db()
        self.assertEqual(campaign.status, Campaign.Status.SENDING)
