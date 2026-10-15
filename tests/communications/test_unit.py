from django.test import TestCase, override_settings

from communications.adapters.base import SendResult
from communications.adapters.mock_adapter import MockAdapter
from communications.adapters.meta_adapter import send_text_message
from communications.models import AudienceSegment, Campaign, Contact, MessageTemplate
from communications.services.campaign_service import resolve_recipients, send_campaign


class CommunicationsUnitTests(TestCase):
    def setUp(self):
        self.contact = Contact.objects.create(
            full_name="Camila Test",
            document_number="CC-COM-1",
            phone="573001112233",
            whatsapp_opt_in=Contact.OptInStatus.SUSCRITO,
        )
        self.opted_out = Contact.objects.create(
            full_name="Baja Test",
            document_number="CC-COM-2",
            phone="573001112244",
            whatsapp_opt_in=Contact.OptInStatus.BAJA,
        )
        self.template = MessageTemplate.objects.create(
            name="Aviso",
            body_text="Hola {{1}}",
        )
        self.segment = AudienceSegment.objects.create(name="Segmento prueba")
        self.segment.contacts.add(self.contact, self.opted_out)
        self.campaign = Campaign.objects.create(
            name="Campaña unit",
            segment=self.segment,
            default_params={"1": "contact.full_name"},
            template_meta_id="",
            template_name=self.template.name,
            template_language="es_CO",
            template_snapshot={
                "body_text": self.template.body_text,
                "header_type": self.template.header_type,
                "header_media_url": self.template.header_media_url,
            },
        )

    def test_resolve_recipients_is_idempotent(self):
        first = resolve_recipients(self.campaign)
        second = resolve_recipients(self.campaign)
        self.assertEqual(len(first), 2)
        self.assertEqual(len(second), 2)

    def test_send_campaign_marks_opted_out_and_sent(self):
        send_campaign(self.campaign, adapter=MockAdapter(failure_rate=0.0))
        self.campaign.refresh_from_db()
        by_phone = {
            r.phone_snapshot: r.status for r in self.campaign.recipients.all()
        }
        self.assertEqual(by_phone["573001112244"], "opted_out")
        self.assertIn(by_phone["573001112233"], {"sent", "delivered", "read"})

    @override_settings(META_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID="")
    def test_send_text_without_config_fails_cleanly(self):
        result = send_text_message("573001112233", "Hola")
        self.assertIsInstance(result, SendResult)
        self.assertFalse(result.success)
        self.assertTrue(result.error)
