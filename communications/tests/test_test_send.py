import json
from unittest.mock import patch

from django.contrib.auth import get_user_model

from django.test import TestCase, override_settings
from django.urls import reverse

from communications.adapters.base import SendResult, TemplateRef
from communications.models import WhatsAppWebhookEvent
from communications.services import meta_templates


def _meta_template(status="APPROVED", meta_id="999"):
    return {
        "meta_id": meta_id,
        "name": "recordatorio_web",
        "status": status,
        "category": "utility",
        "language": "es_CO",
        "body_text": "Hola {{1}}",
        "header_type": "none",
        "header_media_url": "",
        "buttons": [],
    }


def _fetched_ok(status="APPROVED"):
    return meta_templates.TemplateResult(
        ok=True,
        message="Plantilla consultada.",
        meta_id="999",
        meta_status=status,
        template=_meta_template(status),
    )


def _fetched_error(kind=meta_templates.KIND_META, message="No existe."):
    return meta_templates.TemplateResult(ok=False, message=message, kind=kind)


@override_settings(WHATSAPP_TEST_RECIPIENT="+573001234567")
class CampaignTestSendWebViewTests(TestCase):
    def setUp(self):
        self.url = reverse("communications:test_send")
        self.staff = get_user_model().objects.create_user(
            username="test-send-staff",
            password="test-password",
            is_staff=True,
        )
        self.user = get_user_model().objects.create_user(
            username="test-send-user",
            password="test-password",
        )
        # El id de la plantilla es el que asigna Meta (string).
        self.payload = {"template": "999", "params": {"1": "Juan"}}

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

    @patch("communications.views.meta_templates.get_template")
    @patch("communications.views.MetaAdapter.send_template_message")
    def test_staff_gets_bad_gateway_for_missing_template(
        self, send_template_message, get_template
    ):
        get_template.return_value = _fetched_error()
        self.client.force_login(self.staff)

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 502)
        send_template_message.assert_not_called()

    @patch("communications.views.meta_templates.get_template")
    @patch("communications.views.MetaAdapter.send_template_message")
    def test_staff_cannot_send_unapproved_template(
        self, send_template_message, get_template
    ):
        get_template.return_value = _fetched_ok(status="PENDING")
        self.client.force_login(self.staff)

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 400)
        send_template_message.assert_not_called()

    @patch("communications.views.record_test_send")
    @patch("communications.views.meta_templates.get_template")
    @patch(
        "communications.views.MetaAdapter.send_template_message",
        return_value=SendResult(
            success=True,
            provider_message_id="wamid.web-test.123",
        ),
    )
    def test_staff_sends_using_configured_number_and_records_wamid(
        self, send_template_message, get_template, record_test_send
    ):
        get_template.return_value = _fetched_ok()
        self.client.force_login(self.staff)

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        send_template_message.assert_called_once_with(
            "+573001234567",
            TemplateRef(name="recordatorio_web", language="es_CO", body_text="Hola {{1}}"),
            {"1": "Juan"},
        )
        record_test_send.assert_called_once_with(
            "+573001234567",
            "wamid.web-test.123",
            "test_template",
            "recordatorio_web {'1': 'Juan'}",
        )

    @patch("communications.views.meta_templates.get_template")
    @patch(
        "communications.views.MetaAdapter.send_template_message",
        return_value=SendResult(
            success=True,
            provider_message_id="wamid.web-test.456",
        ),
    )
    def test_client_phone_and_to_values_are_ignored(
        self, send_template_message, get_template
    ):
        get_template.return_value = _fetched_ok()
        self.client.force_login(self.staff)

        response = self.post_json({
            **self.payload,
            "phone": "+570000000000",
            "to": "+570000000001",
        })

        self.assertEqual(response.status_code, 200)
        send_template_message.assert_called_once()
        self.assertEqual(send_template_message.call_args.args[0], "+573001234567")

    @patch("communications.views.meta_templates.get_template")
    @patch(
        "communications.views.MetaAdapter.send_template_message",
        return_value=SendResult(success=False, error="Meta rechazó la plantilla."),
    )
    def test_meta_error_is_returned_as_bad_gateway(
        self, send_template_message, get_template
    ):
        get_template.return_value = _fetched_ok()
        self.client.force_login(self.staff)

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["message"], "Meta rechazó la plantilla.")

    @patch("communications.views.meta_templates.get_template")
    def test_rejects_non_string_template(self, get_template):
        self.client.force_login(self.staff)

        response = self.post_json({"template": 999, "params": {}})

        self.assertEqual(response.status_code, 400)
        get_template.assert_not_called()

    def test_rejects_non_post_requests(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)


@override_settings(WHATSAPP_TEST_RECIPIENT="+573001234567")
class CampaignTestSendAPITests(TestCase):
    def setUp(self):
        self.url = reverse("communications:api-test-send")
        self.user = get_user_model().objects.create_user(
            username="api-test-send", password="test-password"
        )
        self.client.force_login(self.user)
        self.payload = {
            "template": "999",
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

    @patch("communications.viewsets.meta_templates.get_template")
    @patch("communications.viewsets.MetaAdapter.send_template_message")
    def test_reports_error_for_missing_template(self, send_template_message, get_template):
        get_template.return_value = _fetched_error()
        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 502)
        send_template_message.assert_not_called()

    @patch("communications.viewsets.meta_templates.get_template")
    @patch("communications.viewsets.MetaAdapter.send_template_message")
    def test_cannot_send_unapproved_template(self, send_template_message, get_template):
        get_template.return_value = _fetched_ok(status="PENDING")

        response = self.post_json(self.payload)

        self.assertEqual(response.status_code, 400)
        send_template_message.assert_not_called()

    @patch("communications.viewsets.meta_templates.get_template")
    @patch(
        "communications.viewsets.MetaAdapter.send_template_message",
        return_value=SendResult(success=True, provider_message_id="wamid.test.123"),
    )
    def test_sends_and_records_success_using_configured_recipient_without_client_phone(
        self, send_template_message, get_template
    ):
        get_template.return_value = _fetched_ok()
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
            TemplateRef(name="recordatorio_web", language="es_CO", body_text="Hola {{1}}"),
            {"1": "Juan"},
        )
        event = WhatsAppWebhookEvent.objects.get(
            event_key="test-send:wamid.test.123"
        )
        self.assertEqual(event.payload["to"], "+573001234567")
        self.assertEqual(event.status, "test_template")

    @patch("communications.viewsets.meta_templates.get_template")
    @patch(
        "communications.viewsets.MetaAdapter.send_template_message",
        return_value=SendResult(success=True, provider_message_id="wamid.test.456"),
    )
    def test_ignores_client_phone_and_to(self, send_template_message, get_template):
        get_template.return_value = _fetched_ok()
        response = self.post_json({
            **self.payload,
            "phone": "+570000000000",
            "to": "+570000000001",
        })

        self.assertEqual(response.status_code, 200)
        send_template_message.assert_called_once_with(
            "+573001234567",
            TemplateRef(name="recordatorio_web", language="es_CO", body_text="Hola {{1}}"),
            {"1": "Juan"},
        )

    @patch("communications.viewsets.meta_templates.get_template")
    @patch(
        "communications.viewsets.MetaAdapter.send_template_message",
        return_value=SendResult(success=False, error="Meta rechazó la plantilla."),
    )
    def test_returns_adapter_error_without_recording_success(
        self, send_template_message, get_template
    ):
        get_template.return_value = _fetched_ok()
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

    def test_invalid_payload_is_rejected(self):
        response = self.post_json({"params": {}})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])
