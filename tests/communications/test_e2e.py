import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from communications.models import WhatsAppWebhookEvent


@override_settings(
    META_ACCESS_TOKEN="meta-access-token",
    META_APP_SECRET="meta-app-secret",
    META_VERIFY_TOKEN="meta-verify-token",
    WHATSAPP_PHONE_NUMBER_ID="123456789",
    WHATSAPP_API_VERSION="v21.0",
)
class CommunicationsWebhookE2ETests(TestCase):
    def _sign(self, body: bytes) -> str:
        digest = hmac.new(b"meta-app-secret", body, hashlib.sha256).hexdigest()
        return f"sha256={digest}"

    def test_verify_challenge(self):
        res = self.client.get(
            reverse("meta-whatsapp-webhook"),
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "meta-verify-token",
                "hub.challenge": "12345",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content.decode(), "12345")

    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.handle_message", return_value=["Hola"])
    @patch("communications.webhooks.meta_webhook.chatbot_whatsapp.send_text", return_value=True)
    def test_inbound_text_goes_to_chatbot_once(self, send_text, handle):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "123456789"},
                                "messages": [
                                    {
                                        "id": "wamid.e2e.in",
                                        "from": "573001112233",
                                        "type": "text",
                                        "text": {"body": "Hola"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }
        body = json.dumps(payload).encode()
        res = self.client.post(
            reverse("meta-whatsapp-webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=self._sign(body),
        )
        self.assertEqual(res.status_code, 200)
        handle.assert_called_once_with("573001112233", "Hola")
        send_text.assert_called_once_with("573001112233", "Hola")
        self.assertTrue(
            WhatsAppWebhookEvent.objects.filter(provider_message_id="wamid.e2e.in").exists()
        )

        res2 = self.client.post(
            reverse("meta-whatsapp-webhook"),
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=self._sign(body),
        )
        self.assertEqual(res2.status_code, 200)
        handle.assert_called_once()
