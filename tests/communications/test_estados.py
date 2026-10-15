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
            body_text="Hola",
        )
        segment = AudienceSegment.objects.create(name="Seg estado")
        segment.contacts.add(contact)
        self.campaign = Campaign.objects.create(
            name="Campaña estados",
            segment=segment,
            template_meta_id="",
            template_name=template.name,
            template_language="es_CO",
            template_snapshot={
                "body_text": template.body_text,
                "header_type": template.header_type,
                "header_media_url": template.header_media_url,
            },
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
