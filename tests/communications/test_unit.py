from django.test import TestCase

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
            meta_template_name="aviso_ok",
            body_text="Hola {{1}}",
            status=MessageTemplate.Status.APPROVED,
        )
        self.segment = AudienceSegment.objects.create(name="Segmento prueba")
        self.segment.contacts.add(self.contact, self.opted_out)
        self.campaign = Campaign.objects.create(
            name="Campaña unit",
            template=self.template,
            segment=self.segment,
            default_params={"1": "contact.full_name"},
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

    def test_send_text_without_config_fails_cleanly(self):
        result = send_text_message("573001112233", "Hola")
        self.assertIsInstance(result, SendResult)
        self.assertFalse(result.success)
        self.assertTrue(result.error)
