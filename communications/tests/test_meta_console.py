from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from io import StringIO

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
        # Las opcionales van aparte: no bloquean la integración.
        self.assertEqual(config["optional_missing"], ["META_APP_ID"])
        self.assertNotIn("META_APP_ID", config["missing"])

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
        self.assertContains(response, "Integración WhatsApp")
        self.assertContains(response, "Validar credenciales con Graph API")

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

    @override_settings(
        META_APP_SECRET="app-secret",
        META_VERIFY_TOKEN="verify",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=True,
    )
    def test_bot_script_advances_through_the_chatbot_states(self):
        """El guion debe recorrer la conversación, no solo el primer saludo."""
        from unittest.mock import patch

        from knowledge.models import ChatConversation

        with patch(
            "communications.webhooks.meta_webhook.chatbot_whatsapp.send_text",
            return_value=True,
        ):
            self.client.post(
                reverse("meta-whatsapp-test-simulate"),
                {"scenario": "script", "phone": "573009998877"},
            )

        conversation = ChatConversation.objects.get(external_user_id="573009998877")
        bot_messages = [
            entry["content"] for entry in conversation.messages if entry["author"] == "bot"
        ]
        self.assertEqual(len(bot_messages), 5, bot_messages)
        # 1. saludo → 2. respuesta a la pregunta → 3. ofrece más ayuda
        # 4. escala al asesor → 5. confirma que queda pendiente.
        self.assertIn("Hola, soy el asistente de Punto TdeA", bot_messages[0])
        self.assertIn("Claro. ¿Qué deseas hacer?", bot_messages[2])
        self.assertIn("transferiremos esta conversación a un asesor", bot_messages[3])
        self.assertIn("Hemos recibido tu solicitud", bot_messages[4])
        self.assertEqual(conversation.status, ChatConversation.STATUS_PENDING)
        self.assertEqual(conversation.flow_state, "pending")

    @override_settings(
        META_APP_SECRET="app-secret",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=True,
    )
    def test_custom_text_reaches_the_bot(self):
        from unittest.mock import patch

        from knowledge.models import ChatConversation

        with patch(
            "communications.webhooks.meta_webhook.chatbot_whatsapp.send_text",
            return_value=True,
        ):
            self.client.post(
                reverse("meta-whatsapp-test-simulate"),
                {
                    "scenario": "inbound",
                    "phone": "573005555444",
                    "text": "prueba con texto propio",
                },
            )

        conversation = ChatConversation.objects.get(external_user_id="573005555444")
        self.assertEqual(len(conversation.messages), 1)
        self.assertEqual(conversation.flow_state, "waiting_question")

    def test_health_endpoint_reports_missing_configuration(self):
        with override_settings(
            META_APP_SECRET="", META_ACCESS_TOKEN="", WHATSAPP_PHONE_NUMBER_ID=""
        ):
            response = self.client.get(reverse("meta-whatsapp-health"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])
        self.assertIn("META_ACCESS_TOKEN", response.json()["missing"])


class MetaConfigPageTests(TestCase):
    def setUp(self):
        self.url = reverse("meta-whatsapp-config")
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

    def test_non_staff_is_redirected_away(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(self.url).status_code, 302)

    @override_settings(
        META_VERIFY_TOKEN="",
        META_APP_SECRET="",
        META_ACCESS_TOKEN="",
        META_APP_ID="",
        WHATSAPP_PHONE_NUMBER_ID="",
    )
    def test_lists_the_missing_variables(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertContains(response, "META_ACCESS_TOKEN")
        self.assertContains(response, "META_APP_SECRET")
        self.assertContains(response, "Faltan")

    @override_settings(
        META_VERIFY_TOKEN="verify",
        META_APP_SECRET="secret",
        META_ACCESS_TOKEN="token",
        META_APP_ID="",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
    )
    def test_complete_configuration_is_reported_as_ready(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertContains(response, "Configuración completa")

    @override_settings(
        META_VERIFY_TOKEN="super-secreto-de-prueba",
        META_APP_SECRET="otro-secreto",
        META_ACCESS_TOKEN="tercer-secreto",
        META_APP_ID="123456",
        WHATSAPP_PHONE_NUMBER_ID="987654321",
    )
    def test_never_renders_a_secret(self):
        self.client.force_login(self.staff)
        body = self.client.get(self.url).content.decode()
        for secret in ("super-secreto-de-prueba", "otro-secreto", "tercer-secreto"):
            self.assertNotIn(secret, body)

    def test_page_is_read_only(self):
        """No debe haber ningún campo que permita escribir credenciales."""
        self.client.force_login(self.staff)
        body = self.client.get(self.url).content.decode()
        for field in ('name="META_APP_SECRET"', 'name="META_ACCESS_TOKEN"', 'type="password"'):
            self.assertNotIn(field, body)

    def test_shows_the_callback_path_to_register_in_meta(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(self.url), "/api/whatsapp/webhook/")


class SidebarMenuTests(TestCase):
    """El grupo del menú solo puede existir para personal staff."""

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff", password="x", is_staff=True
        )
        self.regular = get_user_model().objects.create_user(
            username="asesor", password="x"
        )

    def _sidebar(self):
        return self.client.get(reverse("dashboard:index")).content.decode()

    def test_staff_sees_the_whatsapp_group(self):
        self.client.force_login(self.staff)
        body = self._sidebar()
        self.assertIn(reverse("meta-whatsapp-config"), body)
        self.assertIn(reverse("meta-whatsapp-test"), body)

    def test_regular_user_does_not_see_it(self):
        self.client.force_login(self.regular)
        body = self._sidebar()
        self.assertNotIn(reverse("meta-whatsapp-config"), body)

    def test_the_group_follows_the_same_markup_as_knowledge(self):
        self.client.force_login(self.staff)
        body = self._sidebar()
        self.assertIn("WhatsApp (Meta)", body)
        # Mismo patrón de grupo plegable y submenú que usa Base de conocimiento.
        self.assertEqual(body.count('class="sidebar-group"'), body.count("<details"))
        self.assertIn("sidebar-link--sub", body)


class MetaConfigPageActiveNavTests(TestCase):
    def test_pages_mark_themselves_as_active(self):
        staff = get_user_model().objects.create_user(
            username="staff", password="x", is_staff=True
        )
        self.client.force_login(staff)
        self.assertEqual(
            self.client.get(reverse("meta-whatsapp-config")).context["active_nav"],
            "whatsapp-config",
        )
        self.assertEqual(
            self.client.get(reverse("meta-whatsapp-test")).context["active_nav"],
            "whatsapp-test",
        )


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
        META_VERIFY_TOKEN="verify",
        META_APP_ID="",
        META_APP_SECRET="secret",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
    )
    def test_missing_app_id_does_not_block(self):
        """META_APP_ID no lo usa la API: dejarlo vacío no debe marcar la integración como rota."""
        from io import StringIO

        out, err = StringIO(), StringIO()
        call_command("check_meta_whatsapp", stdout=out, stderr=err)
        output = out.getvalue()
        self.assertIn("Configuración completa", output)
        self.assertNotIn("Faltan valores", output)
        self.assertIn("no bloquean la integración", output)
        self.assertEqual(err.getvalue(), "")

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


class MetaSimulatorSuggestionTests(TestCase):
    """La página de prueba sugiere un wamid listo para ejercitar los estados.

    El runner de tests pone DEBUG=False; el entorno de desarrollo se declara
    explícito para poder usar el seed (que se niega a correr sin DEBUG salvo
    --force) y habilitar el simulador.
    """

    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff-sug", password="x", is_staff=True
        )

    @override_settings(
        DEBUG=True,
        META_APP_SECRET="app-secret",
        META_VERIFY_TOKEN="verify",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=True,
    )
    def test_suggests_a_wamid_that_can_still_advance(self):
        from communications.models import BroadcastRecipient

        call_command("seed_demo_whatsapp", stdout=StringIO(), stderr=StringIO())
        suggested = (
            BroadcastRecipient.objects.exclude(provider_message_id="")
            .filter(status=BroadcastRecipient.Status.SENT)
            .order_by("-id")
            .first()
        )
        self.assertIsNotNone(suggested)

        self.client.force_login(self.staff)
        response = self.client.get(reverse("meta-whatsapp-test"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'name="reference" value="%s"' % suggested.provider_message_id
        )

    @override_settings(
        DEBUG=True,
        META_APP_SECRET="app-secret",
        META_VERIFY_TOKEN="verify",
        META_ACCESS_TOKEN="token",
        WHATSAPP_PHONE_NUMBER_ID="123456789",
        ALLOW_WEBHOOK_SIMULATOR=True,
    )
    def test_no_suggestion_when_there_are_no_recipients(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("meta-whatsapp-test"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="reference"')
        self.assertNotContains(response, 'value="wamid')
