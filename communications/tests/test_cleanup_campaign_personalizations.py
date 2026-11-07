from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from communications.models import (
    AudienceSegment,
    Campaign,
    CampaignPersonalization,
)


class CleanupCampaignPersonalizationsTests(TestCase):
    def setUp(self):
        self.segment = AudienceSegment.objects.create(name="Audiencia")
        self.expired = CampaignPersonalization.objects.create(
            segment=self.segment,
            template_fingerprint="a" * 64,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.current = CampaignPersonalization.objects.create(
            segment=self.segment,
            template_fingerprint="b" * 64,
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        campaign = Campaign.objects.create(
            name="Campaña validada",
            segment=self.segment,
        )
        self.consumed = CampaignPersonalization.objects.create(
            campaign=campaign,
            segment=self.segment,
            template_fingerprint="c" * 64,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

    def run_command(self, *args, **kwargs):
        output = StringIO()
        call_command(
            "cleanup_campaign_personalizations",
            *args,
            stdout=output,
            stderr=StringIO(),
            **kwargs,
        )
        return output.getvalue()

    def test_dry_run_keeps_expired_validations(self):
        output = self.run_command()

        self.assertIn("Modo ensayo", output)
        self.assertTrue(
            CampaignPersonalization.objects.filter(pk=self.expired.pk).exists()
        )

    def test_execute_deletes_only_expired_unconsumed_validations(self):
        output = self.run_command("--ejecutar")

        self.assertIn("Borradas 1 validaciones", output)
        self.assertFalse(
            CampaignPersonalization.objects.filter(pk=self.expired.pk).exists()
        )
        self.assertTrue(
            CampaignPersonalization.objects.filter(pk=self.current.pk).exists()
        )
        self.assertTrue(
            CampaignPersonalization.objects.filter(pk=self.consumed.pk).exists()
        )
