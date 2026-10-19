import hashlib
import hmac
import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from communications.adapters.base import TemplateRef
from communications.adapters.meta_adapter import MetaAdapter
from communications.models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    ContactEvent,
    MessageTemplate,
    WhatsAppWebhookEvent,
)


@override_settings(
    META_ACCESS_TOKEN="meta-access-token",
    META_APP_SECRET="meta-app-secret",
    META_VERIFY_TOKEN="meta-verify-token",
    WHATSAPP_PHONE_NUMBER_ID="123456789",
    WHATSAPP_API_VERSION="v21.0",
)
class MetaWhatsAppIntegrationTests(TestCase):
    def _signature(self, body: bytes) -> str:
        digest = hmac.new(b"meta-app-secret", body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def _post_webhook(self, payload: dict):
        body = json.dumps(payload).encode()
        return self.client.post(
            reverse("meta-whatsapp-webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=self._signature(body),
        )

    def setUp(self):
        self.contact = Contact.objects.create(
            full_name="Ana Pérez",
            document_number="123456",
            phone="+573001112233",
            whatsapp_opt_in=Contact.OptInStatus.SUSCRITO,
        )
        self.template = MessageTemplate.objects.create(
            name="matricula_2026",
            body_text="Hola {{1}}, recuerda tu fecha {{2}}.",
        )

    @patch("communications.adapters.meta_adapter.requests.post")
    def test_meta_adapter_sends_approved_template_with_ordered_parameters(self, post):
        response = Mock()
        response.json.return_value = {"messages": [{"id": "wamid.outbound.1"}]}
        response.raise_for_status.return_value = None
        post.return_value = response

        result = MetaAdapter().send_template_message(
            "+57 300 111 2233",
            self.template,
            {"2": "10 de octubre", "1": "Ana"},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "wamid.outbound.1")
        post.assert_called_once()
        self.assertEqual(
            post.call_args.kwargs["json"],
            {
                "messaging_product": "whatsapp",
                "to": "573001112233",
                "type": "template",
                "template": {
                    "name": "matricula_2026",
                    "language": {"code": "es_CO"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": "Ana"},
                                {"type": "text", "text": "10 de octubre"},
                            ],
                        }
                    ],
                },
            },
        )

    @patch("communications.adapters.meta_adapter.requests.post")
    def test_meta_adapter_rejects_missing_template_parameter(self, post):
        result = MetaAdapter().send_template_message(
            "+573001112233", self.template, {"1": "Ana"}
        )

        self.assertFalse(result.success)
        self.assertIn("{{2}}", result.error)
        post.assert_not_called()

    @patch("communications.adapters.meta_adapter.requests.post")
    def test_meta_adapter_sends_static_text_header_and_body_parameters(self, post):
        response = Mock()
        response.json.return_value = {"messages": [{"id": "wamid.outbound.header"}]}
        response.raise_for_status.return_value = None
        post.return_value = response
        template = TemplateRef(
            name="matricula_2026",
            language="es_CO",
            body_text="Hola {{1}}, recuerda {{2}}.",
            header_type="text",
            header_text="Aviso importante",
        )

        result = MetaAdapter().send_template_message(
            "+573001112233",
            template,
            {"1": "Ana", "2": "tu matrícula"},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider_message_id, "wamid.outbound.header")
        self.assertEqual(
            post.call_args.kwargs["json"],
            {
                "messaging_product": "whatsapp",
                "to": "573001112233",
                "type": "template",
                "template": {
                    "name": "matricula_2026",
                    "language": {"code": "es_CO"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": "Ana"},
                                {"type": "text", "text": "tu matrícula"},
                            ],
                        },
                        {
                            "type": "header",
                            "parameters": [
                                {"type": "text", "text": "Aviso importante"}
                            ],
                        },
                    ],
                },
            },
        )

    @patch("communications.adapters.meta_adapter.requests.post")
    def test_meta_adapter_rejects_text_header_without_text(self, post):
        template = TemplateRef(
            name="matricula_2026",
            body_text="Hola",
            header_type="text",
        )

        result = MetaAdapter().send_template_message(
            "+573001112233", template, {}
        )

        self.assertFalse(result.success)
        self.assertIn("encabezado de texto", result.error)
        post.assert_not_called()

    @patch("communications.adapters.meta_adapter.requests.post")
    def test_meta_adapter_rejects_dynamic_text_header(self, post):
        template = TemplateRef(
            name="matricula_2026",
            body_text="Hola",
            header_type="text",
            header_text="Hola {{1}}",
        )

        result = MetaAdapter().send_template_message(
            "+573001112233", template, {"1": "Ana"}
        )

        self.assertFalse(result.success)
        self.assertIn("no admite variables", result.error)
        post.assert_not_called()

    @patch("communications.adapters.meta_adapter.requests.post")
    def test_meta_adapter_rejects_media_header_without_url(self, post):
        template = TemplateRef(
            name="matricula_2026",
            body_text="Hola",
            header_type="image",
        )

        result = MetaAdapter().send_template_message(
            "+573001112233", template, {}
        )

        self.assertFalse(result.success)
        self.assertIn("encabezado multimedia", result.error)
        post.assert_not_called()

    def test_webhook_verifies_meta_subscription(self):
        response = self.client.get(
            reverse("meta-whatsapp-webhook"),
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "meta-verify-token",
                "hub.challenge": "challenge-value",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "challenge-value")

    def test_webhook_rejects_unsigned_requests(self):
        response = self.client.post(
            reverse("meta-whatsapp-webhook"),
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_webhook_updates_campaign_delivery_once(self):
        segment = AudienceSegment.objects.create(name="Aspirantes")
        campaign = Campaign.objects.create(
            name="Recordatorio",
            template_meta_id="999",
            template_name="recordatorio_web",
            template_language="es_CO",
            template_snapshot={
                "body_text": "Hola {{1}}, recuerda tu fecha {{2}}.",
                "header_type": "none",
                "header_media_url": "",
            },
            segment=segment,
        )
        recipient = BroadcastRecipient.objects.create(
            campaign=campaign,
            contact=self.contact,
            phone_snapshot=self.contact.phone,
            status=BroadcastRecipient.Status.SENT,
            provider="meta",
            provider_message_id="wamid.outbound.1",
        )
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [
                                    {
                                        "id": "wamid.outbound.1",
                                        "status": "delivered",
                                        "timestamp": "1760000000",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        first = self._post_webhook(payload)
        second = self._post_webhook(payload)

        recipient.refresh_from_db()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["processed"], 1)
        self.assertEqual(second.json()["duplicates"], 1)
        self.assertEqual(recipient.status, BroadcastRecipient.Status.DELIVERED)
        self.assertIsNotNone(recipient.delivered_at)
        self.assertEqual(
            ContactEvent.objects.filter(
                broadcast_recipient=recipient,
                event_type=ContactEvent.EventType.MESSAGE_DELIVERED,
            ).count(),
            1,
        )
        self.assertEqual(WhatsAppWebhookEvent.objects.count(), 1)

    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_text", return_value=True)
    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message", return_value=["Hola"])
    def test_webhook_sends_inbound_text_to_chatbot_once(self, handle_message, send_text):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "123456789"},
                                "messages": [
                                    {
                                        "id": "wamid.inbound.1",
                                        "from": "573001112233",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        first = self._post_webhook(payload)
        second = self._post_webhook(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["processed"], 1)
        self.assertEqual(second.json()["duplicates"], 1)
        handle_message.assert_called_once_with(
            "573001112233",
            "Hola",
            external_message_id="wamid.inbound.1",
        )
        send_text.assert_called_once_with("573001112233", "Hola")
