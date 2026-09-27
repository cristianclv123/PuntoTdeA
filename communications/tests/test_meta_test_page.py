from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from communications.services import meta_config


class MetaConfigStatusTests(TestCase):
    def test_empty_environment_reports_everything_missing(self):
        with override_settings(
            META_VERIFY_TOKEN="",
            META_APP_SECRET="",
            META_ACCESS_TOKEN="",
            META_APP_ID="",
            WHATSAPP_PHONE_NUMBER_ID="",
        ):
            config = meta_config.capability_status()

        self.assertFalse(config["can_send"])
        self.assertFalse(config["can_receive"])
        self.assertFalse(config["can_verify"])
        self.assertIn("META_ACCESS_TOKEN", config["missing"])
        self.assertIn("META_APP_SECRET", config["missing"])

    def test_secrets_are_never_exposed(self):
        with override_settings(
            META_VERIFY_TOKEN="verify-secreto",
            META_APP_SECRET="app-secreto",
            META_ACCESS_TOKEN="token-secreto",
            WHATSAPP_PHONE_NUMBER_ID="",
        ):
            config = meta_config.capability_status()

        rendered = " ".join(status.state for status in config["statuses"])
        for secret in ("verify-secreto", "app-secreto", "token-secreto"):
            self.assertNotIn(secret, rendered)

    def test_ready_environment_enables_capabilities(self):
        with override_settings(
            META_VERIFY_TOKEN="verify",
            META_APP_SECRET="secret",
            META_ACCESS_TOKEN="token",
            WHATSAPP_PHONE_NUMBER_ID="123456789",
        ):
            self.assertTrue(meta_config.is_fully_configured())
            self.assertTrue(meta_config.can_receive_webhooks())
            self.assertTrue(meta_config.can_verify_subscription())


class MetaTestPageAccessTests(TestCase):
    def setUp(self):
        self.url = reverse("meta-whatsapp-test")
        self.staff = get_user_model().objects.create_user(
            username="staff", password="x", is_staff=True
        )
        self.regular = get_user_model().objects.create_user(
            username="asesor", password="x"
        )

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_non_staff_cannot_open_the_page(self):
        self.client.force_login(self.regular)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_staff_sees_the_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Estado de configuración")

    @override_settings(
        META_VERIFY_TOKEN="",
        META_APP_SECRET="",
        META_ACCESS_TOKEN="",
        WHATSAPP_PHONE_NUMBER_ID="",
    )
    def test_staff_sees_pending_variables(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertContains(response, "META_ACCESS_TOKEN")


class MetaSimulatorTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff", password="x", is_staff=True
        )
        self.client.force_login(self.staff)

    def test_simulation_requires_app_secret(self):
        from communications.models import WhatsAppWebhookEvent

        with override_settings(META_APP_SECRET="", ALLOW_WEBHOOK_SIMULATOR=True):
            response = self.client.post(
                reverse("meta-whatsapp-test-simulate"), {"scenario": "inbound"}
            )

        self.assertEqual(response.status_code, 302)
        # Sin firma válida el webhook rechaza el payload: no debe quedar registrado.
        self.assertEqual(WhatsAppWebhookEvent.objects.count(), 0)

    @override_settings(
        META_APP_SECRET="app-secret",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=False,
    )
    def test_simulation_is_refused_when_the_flag_is_off(self):
        """Con DEBUG apagado un payload firmado es indistinguible de uno real."""
        from communications.models import WhatsAppWebhookEvent

        response = self.client.post(
            reverse("meta-whatsapp-test-simulate"), {"scenario": "inbound"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(WhatsAppWebhookEvent.objects.count(), 0)

    @override_settings(
        META_APP_SECRET="app-secret",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=False,
    )
    def test_simulator_form_is_hidden_when_the_flag_is_off(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("meta-whatsapp-test"))
        self.assertNotContains(response, "meta-whatsapp-test-simulate")

    @override_settings(
        META_APP_SECRET="app-secret",
        META_VERIFY_TOKEN="verify",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=True,
    )
    def test_inbound_simulation_is_recorded(self):
        from unittest.mock import patch

        from communications.models import WhatsAppWebhookEvent

        with patch(
            "communications.adapters.meta_adapter.requests.post"
        ) as meta_post:
            meta_post.return_value.json.return_value = {
                "messages": [{"id": "wamid.simulado"}]
            }
            response = self.client.post(
                reverse("meta-whatsapp-test-simulate"), {"scenario": "inbound"}
            )

        self.assertEqual(response.status_code, 302)
        event = WhatsAppWebhookEvent.objects.get()
        self.assertEqual(event.event_type, "inbound")
        self.assertIsNotNone(event.processed_at)

    @override_settings(
        META_APP_SECRET="app-secret",
        META_VERIFY_TOKEN="verify",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=True,
    )
    def test_simulation_delivers_the_message_to_the_chatbot(self):
        """El escenario inbound debe llegar al flujo del bot, no descartarse."""
        from unittest.mock import patch

        from knowledge.models import ChatConversation

        with patch(
            "communications.webhooks.meta_webhook.chatbot_whatsapp.send_text",
            return_value=True,
        ) as send_text:
            self.client.post(reverse("meta-whatsapp-test-simulate"), {"scenario": "inbound"})

        self.assertTrue(send_text.called)
        conversation = ChatConversation.objects.get(external_user_id="573001112233")
        self.assertTrue(conversation.messages)

    @override_settings(
        META_APP_SECRET="app-secret",
        META_VERIFY_TOKEN="verify",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=True,
    )
    def test_status_simulation_without_known_wamid_is_reported(self):
        from communications.models import WhatsAppWebhookEvent

        self.client.post(
            reverse("meta-whatsapp-test-simulate"),
            {"scenario": "delivered", "reference": "wamid.desconocido"},
        )

        event = WhatsAppWebhookEvent.objects.get()
        self.assertEqual(event.event_type, "status")
        self.assertEqual(event.status, "delivered")
        self.assertIsNotNone(event.processed_at)

    def test_health_endpoint_reports_missing_configuration(self):
        with override_settings(
            META_APP_SECRET="", META_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID=""
        ):
            response = self.client.get(reverse("meta-whatsapp-health"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])
        self.assertIn("META_ACCESS_TOKEN", response.json()["missing"])


class CheckMetaCommandTests(TestCase):
    """El comando se encadena en un monitor, así que su código de salida importa."""

    @override_settings(
        META_VERIFY_TOKEN="verify",
        META_APP_ID="123456",
        META_APP_SECRET="secret",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        WHATSAPP_API_VERSION="v21.0",
        META_GRAPH_API_URL="https://graph.facebook.com",
        META_REQUEST_TIMEOUT=10,
    )
    def test_complete_configuration_exits_zero_without_network(self):
        from io import StringIO

        out = StringIO()
        try:
            call_command("check_meta_whatsapp", stdout=out, stderr=StringIO())
        except SystemExit as exit_code:  # pragma: no cover - no debe ocurrir
            self.fail(f"salió con código {exit_code.code} pese a estar configurado")
        self.assertIn("Configuración completa", out.getvalue())

    @override_settings(
        META_VERIFY_TOKEN="",
        META_APP_ID="",
        META_APP_SECRET="",
        META_ACCESS_TOKEN="",
        WHATSAPP_PHONE_NUMBER_ID="",
    )
    def test_incomplete_configuration_exits_non_zero(self):
        from io import StringIO

        with self.assertRaises(SystemExit) as ctx:
            call_command(
                "check_meta_whatsapp", stdout=StringIO(), stderr=StringIO()
            )
        self.assertEqual(ctx.exception.code, 1)

    @override_settings(
        META_VERIFY_TOKEN="",
        META_APP_ID="",
        META_APP_SECRET="secret",
        META_ACCESS_TOKEN="",
        WHATSAPP_PHONE_NUMBER_ID="",
    )
    def test_validate_reports_missing_token_instead_of_calling_meta(self):
        from io import StringIO

        out = StringIO()
        with self.assertRaises(SystemExit):
            call_command(
                "check_meta_whatsapp",
                "--validate",
                stdout=out,
                stderr=StringIO(),
            )
        self.assertIn("META_ACCESS_TOKEN no está configurado", out.getvalue())
