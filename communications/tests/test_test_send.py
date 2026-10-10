import json
from unittest.mock import patch

from django.contrib.auth import get_user_model

from django.test import TestCase, override_settings
from django.urls import reverse

from communications.adapters.base import SendResult
from communications.models import MessageTemplate, WhatsAppWebhookEvent


@override_settings(WHATSAPP_TEST_RECIPIENT="+573001234567")
class CampaignTestSendWebViewTests(TestCase):
    def setUp(self):
        self.url = reverse("communications:test_send")
        self.template = MessageTemplate.objects.create(
            name="Recordatorio web",
            meta_template_name="recordatorio_web",
            body_text="Hola {{1}}",
            status=MessageTemplate.Status.APPROVED,
        )
        self.staff = get_user_model().objects.create_user(
            username="test-send-staff",
            password="test-password",
            is_staff=True,
        )
        self.user = get_user_model().objects.create_user(
            username="test-send-user",
            password="test-password",
        )
        self.payload = {"template": self.template.pk, "params": {"1": "Juan"}}

    def post_json(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_authenticated_non_staff_user_is_rejected(self):
        self.client.force_login(self.user)

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 302)

    @override_settings(WHATSAPP_TEST_RECIPIENT="")
    @patch("communications.views.MetaAdapter.send_template_message")
    def test_staff_requires_configured_recipient(self, send_template_message):
        self.client.force_login(self.staff)

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["success"])
        send_template_message.assert_not_called()

    @patch("communications.views.MetaAdapter.send_template_message")
    def test_staff_gets_not_found_for_missing_template(self, send_template_message):
        self.client.force_login(self.staff)

        response = self.post_json({"template": 999999, "params": {}})

        self.assertEqual(response.status_code, 404)
        send_template_message.assert_not_called()

    @patch("communications.views.MetaAdapter.send_template_message")
    def test_staff_cannot_send_unapproved_template(self, send_template_message):
        self.client.force_login(self.staff)
        self.template.status = MessageTemplate.Status.DRAFT
        self.template.save(update_fields=["status"])

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 400)
        send_template_message.assert_not_called()

    @patch("communications.views.record_test_send")
    @patch(
        "communications.views.MetaAdapter.send_template_message",
        return_value=SendResult(
            success=True,
            provider_message_id="wamid.web-test.123",
        ),
    )
    def test_staff_sends_using_configured_number_and_records_wamid(
        self, send_template_message, record_test_send
    ):
        self.client.force_login(self.staff)

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        send_template_message.assert_called_once_with(
            "+573001234567",
            self.template,
            {"1": "Juan"},
        )
        record_test_send.assert_called_once_with(
            "+573001234567",
            "wamid.web-test.123",
            "test_template",
            "recordatorio_web {'1': 'Juan'}",
        )

    @patch(
        "communications.views.MetaAdapter.send_template_message",
        return_value=SendResult(
            success=True,
            provider_message_id="wamid.web-test.456",
        ),
    )
    def test_client_phone_and_to_values_are_ignored(self, send_template_message):
        self.client.force_login(self.staff)

        response = self.post_json({
            **self.payload,
            "phone": "+570000000000",
            "to": "+570000000001",
        })

        self.assertEqual(response.status_code, 200)
        send_template_message.assert_called_once_with(
            "+573001234567",
            self.template,
            {"1": "Juan"},
        )

    @patch(
        "communications.views.MetaAdapter.send_template_message",
        return_value=SendResult(
            success=False,
            error="Meta rechazó la plantilla.",
        ),
    )
    def test_meta_error_is_returned_as_bad_gateway(self, send_template_message):
        self.client.force_login(self.staff)

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["message"], "Meta rechazó la plantilla.")
        send_template_message.assert_called_once()

    def test_rejects_non_post_requests(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)


@override_settings(DEBUG=True, WHATSAPP_TEST_RECIPIENT="+573001234567")
class CampaignTestSendAPITests(TestCase):
    def setUp(self):
        self.url = reverse("communications:api-test-send")
        self.template = MessageTemplate.objects.create(
            name="Recordatorio",
            meta_template_name="recordatorio_prueba",
            body_text="Hola {{1}}",
            status=MessageTemplate.Status.APPROVED,
        )
        self.payload = {
            "template": self.template.pk,
            "params": {"1": "Juan"},
        }

    def post_json(self, payload):
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    @override_settings(WHATSAPP_TEST_RECIPIENT="")
    @patch("communications.viewsets.MetaAdapter.send_template_message")
    def test_requires_configured_test_recipient(self, send_template_message):
        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["success"])
        self.assertIn("destinatario", response.json()["message"])
        send_template_message.assert_not_called()

    @patch("communications.viewsets.MetaAdapter.send_template_message")
    def test_returns_not_found_for_missing_template(self, send_template_message):
        response = self.post_json({"template": 999999, "params": {}})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["success"])
        send_template_message.assert_not_called()

    @patch("communications.viewsets.MetaAdapter.send_template_message")
    def test_rejects_unapproved_template(self, send_template_message):
        self.template.status = MessageTemplate.Status.DRAFT
        self.template.save(update_fields=["status"])

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("aprobada", response.json()["message"])
        send_template_message.assert_not_called()

    @patch(
        "communications.viewsets.MetaAdapter.send_template_message",
        return_value=SendResult(success=True, provider_message_id="wamid.test.123"),
    )
    def test_sends_and_records_success_using_configured_recipient_without_client_phone(
        self, send_template_message
    ):
        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "success": True,
                "message": "Mensaje de prueba enviado correctamente.",
                "provider_message_id": "wamid.test.123",
            },
        )
        send_template_message.assert_called_once_with(
            "+573001234567",
            self.template,
            {"1": "Juan"},
        )
        event = WhatsAppWebhookEvent.objects.get(
            event_key="test-send:wamid.test.123"
        )
        self.assertEqual(event.payload["to"], "+573001234567")
        self.assertEqual(event.status, "test_template")

    @patch(
        "communications.viewsets.MetaAdapter.send_template_message",
        return_value=SendResult(success=True, provider_message_id="wamid.test.456"),
    )
    def test_ignores_client_phone_and_to(self, send_template_message):
        response = self.post_json({
            **self.payload,
            "phone": "+570000000000",
            "to": "+570000000001",
        })

        self.assertEqual(response.status_code, 200)
        send_template_message.assert_called_once_with(
            "+573001234567",
            self.template,
            {"1": "Juan"},
        )

    @patch(
        "communications.viewsets.MetaAdapter.send_template_message",
        return_value=SendResult(success=False, error="Meta rechazó la plantilla."),
    )
    def test_returns_adapter_error_without_recording_success(self, send_template_message):
        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {
                "success": False,
                "message": "Meta rechazó la plantilla.",
            },
        )
        self.assertFalse(WhatsAppWebhookEvent.objects.exists())
        send_template_message.assert_called_once()
