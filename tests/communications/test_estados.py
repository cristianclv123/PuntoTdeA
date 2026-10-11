from django.test import TestCase

from communications.adapters.mock_adapter import MockAdapter
from communications.models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    MessageTemplate,
)
from communications.services.campaign_service import send_campaign


class CampaignEstadoTests(TestCase):
    def setUp(self):
        contact = Contact.objects.create(
            full_name="Estado Campaña",
            document_number="CC-ST-1",
            phone="573009990001",
            whatsapp_opt_in=Contact.OptInStatus.SUSCRITO,
        )
        template = MessageTemplate.objects.create(
            name="Estado tpl",
            meta_template_name="estado_tpl",
            body_text="Hola",
            status=MessageTemplate.Status.APPROVED,
        )
        segment = AudienceSegment.objects.create(name="Seg estado")
        segment.contacts.add(contact)
        self.campaign = Campaign.objects.create(
            name="Campaña estados",
            template=template,
            segment=segment,
        )

    def test_draft_a_sending_a_sent(self):
        self.assertEqual(self.campaign.status, Campaign.Status.DRAFT)
        send_campaign(self.campaign, adapter=MockAdapter(failure_rate=0.0))
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, Campaign.Status.SENT)
        recipient = self.campaign.recipients.get()
        self.assertEqual(recipient.status, BroadcastRecipient.Status.SENT)
        self.assertTrue(recipient.provider_message_id.startswith("mock-"))

    def test_recipient_empieza_pending(self):
        from communications.services.campaign_service import resolve_recipients

        resolve_recipients(self.campaign)
        self.assertEqual(self.campaign.recipients.get().status, BroadcastRecipient.Status.PENDING)
