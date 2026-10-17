from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from io import StringIO
from unittest.mock import patch

from communications import meta_console_views
from communications.models import WhatsAppWebhookEvent
from communications.services import meta_config, meta_templates
from communications.services.ads_service import AdsResult

from announcements.models import Announcement, StatusAd


class MetaConfigStatusTests(TestCase):
    def test_empty_environment_reports_everything_missing(self):
        with override_settings(
            META_VERIFY_TOKEN="",
            META_APP_SECRET="",
            META_ACCESS_TOKEN="",
            META_APP_ID="",
            WHATSAPP_PHONE_NUMBER_ID="",
            WHATSAPP_BUSINESS_ACCOUNT_ID="",
        ):
            config = meta_config.capability_status()

        self.assertFalse(config["can_send"])
        self.assertFalse(config["can_receive"])
        self.assertFalse(config["can_verify"])
        self.assertFalse(config["can_manage_templates"])
        self.assertIn("META_ACCESS_TOKEN", config["missing"])
        self.assertIn("META_APP_SECRET", config["missing"])
        # Las opcionales van aparte: no bloquean la integración.
        self.assertEqual(
            config["optional_missing"],
            ["META_APP_ID", "WHATSAPP_BUSINESS_ACCOUNT_ID"],
        )
        self.assertNotIn("META_APP_ID", config["missing"])
        self.assertNotIn("WHATSAPP_BUSINESS_ACCOUNT_ID", config["missing"])

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
            WHATSAPP_BUSINESS_ACCOUNT_ID="waba-123",
        ):
            self.assertTrue(meta_config.is_fully_configured())
            self.assertTrue(meta_config.can_receive_webhooks())
            self.assertTrue(meta_config.can_verify_subscription())
            self.assertTrue(meta_config.can_manage_templates())


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


class MetaHealthEndpointTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="staff", password="x", is_staff=True
        )
        self.client.force_login(self.staff)

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
        self.assertIn(reverse("meta-whatsapp-results"), body)

    def test_regular_user_does_not_see_it(self):
        self.client.force_login(self.regular)
        body = self._sidebar()
        self.assertNotIn(reverse("meta-whatsapp-config"), body)
        self.assertNotIn(reverse("meta-whatsapp-results"), body)

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
        self.assertEqual(
            self.client.get(reverse("meta-whatsapp-results")).context["active_nav"],
            "whatsapp-results",
        )


class MetaResultsPageTests(TestCase):
    """La página de resultados reúne las tablas y solo la ve el staff."""

    def setUp(self):
        self.url = reverse("meta-whatsapp-results")
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
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_staff_sees_every_tab(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for label in (
            "Estados de entrega",
            "Eventos del webhook",
            "Conversaciones del chatbot",
            "Destinatarios de campañas",
            "Objetos creados en Meta",
        ):
            self.assertContains(response, label)
        self.assertNotContains(response, "Envíos de prueba")

    def test_events_tab_shows_the_test_send_recipient_and_content(self):
        WhatsAppWebhookEvent.objects.create(
            event_key="test-send:wamid-prueba",
            provider_message_id="wamid-prueba",
            event_type=WhatsAppWebhookEvent.Type.STATUS,
            status="test_text",
            payload={"to": "573001112233", "detail": "Hola desde Prueba"},
        )
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertContains(response, "573001112233")
        self.assertContains(response, "Hola desde Prueba")

    def test_the_page_is_named_movimientos(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertContains(response, "Movimientos de la integración")

    def test_the_form_page_links_to_the_results_page(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("meta-whatsapp-test"))
        self.assertContains(response, reverse("meta-whatsapp-results"))

    def test_the_form_page_no_longer_holds_the_result_tables(self):
        """Las tablas se movieron: en la página de pruebas no deben quedar."""
        self.client.force_login(self.staff)
        response = self.client.get(reverse("meta-whatsapp-test"))
        self.assertNotContains(response, "Recorrido completo")
        self.assertNotContains(response, "Estados por mensaje")


class MetaAdsCleanupTests(TestCase):
    """La pestaña «Objetos creados en Meta» lista los objetos y permite borrarlos."""

    def setUp(self):
        self.url = reverse("meta-whatsapp-results")
        self.delete_url = reverse("meta-whatsapp-results-delete")
        self.staff = get_user_model().objects.create_user(
            username="staff", password="x", is_staff=True
        )
        self.regular = get_user_model().objects.create_user(
            username="asesor", password="x"
        )
        self.announcement = Announcement.objects.create(
            title="Aviso de prueba", content="Hola"
        )
        # Intento fallido: creó campaña y ad set, pero nunca llegó al anuncio.
        self.status_ad = StatusAd.objects.create(
            announcement=self.announcement,
            campaign_id="111",
            ad_set_id="222",
            state=StatusAd.State.ERROR,
            error="app en modo desarrollo",
        )

    def test_tab_lists_the_campaign_and_flags_the_orphan(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url)
        self.assertContains(response, "Objetos creados en Meta")
        self.assertContains(response, "111")
        self.assertContains(response, "huérfano")

    def test_the_delete_action_requires_staff(self):
        self.client.force_login(self.regular)
        response = self.client.post(self.delete_url, {"status_ad": self.status_ad.id})
        self.assertEqual(response.status_code, 302)
        self.status_ad.refresh_from_db()
        self.assertEqual(self.status_ad.campaign_id, "111")

    def test_the_delete_action_requires_post(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.delete_url).status_code, 405)

    @patch("communications.services.ads_service.delete_object")
    def test_delete_calls_meta_and_clears_the_trace(self, delete_object):
        delete_object.return_value = AdsResult(True, "ok", {"id": "111"})
        self.client.force_login(self.staff)

        response = self.client.post(self.delete_url, {"status_ad": self.status_ad.id})

        self.assertEqual(response.status_code, 302)
        delete_object.assert_called_once_with("111")
        self.status_ad.refresh_from_db()
        self.assertEqual(self.status_ad.campaign_id, "")
        self.assertEqual(self.status_ad.ad_set_id, "")
        self.assertEqual(self.status_ad.state, StatusAd.State.DRAFT)

    @patch("communications.services.ads_service.delete_object")
    def test_delete_reports_the_meta_error_and_keeps_the_trace(self, delete_object):
        delete_object.return_value = AdsResult(False, "no", error="boom")
        self.client.force_login(self.staff)

        response = self.client.post(
            self.delete_url, {"status_ad": self.status_ad.id}, follow=True
        )

        self.assertContains(response, "No se pudo eliminar")
        self.status_ad.refresh_from_db()
        self.assertEqual(self.status_ad.campaign_id, "111")


class SampleTemplateLabelTests(TestCase):
    """`hello_world` es de muestra: se oculta salvo que sea la única aprobada."""

    def setUp(self):
        self.url = reverse("meta-whatsapp-test")
        self.staff = get_user_model().objects.create_user(
            username="staff", password="x", is_staff=True
        )

    @staticmethod
    def _template(name, status="APPROVED"):
        return {
            "meta_id": f"id-{name}",
            "name": name,
            "status": status,
            "category": "utility",
            "language": "es_CO",
            "is_sample": meta_templates.is_sample_template(name),
        }

    def test_approved_templates_hides_the_sample_when_there_is_an_own_template(self):
        result = meta_templates.TemplateListResult(
            ok=True,
            templates=[
                self._template("hello_world"),
                self._template("aviso_de_pago"),
                self._template("en_revision", status="PENDING"),
            ],
        )
        with patch.object(meta_templates, "list_templates", return_value=result):
            offered = meta_console_views.approved_templates()

        self.assertEqual([template["name"] for template in offered], ["aviso_de_pago"])

    def test_approved_templates_offers_the_sample_when_it_is_the_only_approved(self):
        result = meta_templates.TemplateListResult(
            ok=True,
            templates=[
                self._template("hello_world"),
                self._template("en_revision", status="PENDING"),
            ],
        )
        with patch.object(meta_templates, "list_templates", return_value=result):
            offered = meta_console_views.approved_templates()

        self.assertEqual(
            [(template["name"], template["is_sample"]) for template in offered],
            [("hello_world", True)],
        )

    def test_approved_templates_includes_body_and_buttons_for_the_preview(self):
        result = meta_templates.TemplateListResult(
            ok=True,
            templates=[
                {
                    **self._template("aviso_de_pago"),
                    "body_text": "Hola {{1}}",
                    "indexes": [1],
                    "header_type": "none",
                    "buttons": [{"text": "Ver", "url": "https://x.co"}],
                }
            ],
        )
        with patch.object(meta_templates, "list_templates", return_value=result):
            offered = meta_console_views.approved_templates()

        self.assertEqual(offered[0]["body_text"], "Hola {{1}}")
        self.assertEqual(offered[0]["buttons"], [{"text": "Ver", "url": "https://x.co"}])

    def test_the_form_hides_the_sample_when_there_is_an_own_template(self):
        result = meta_templates.TemplateListResult(
            ok=True,
            templates=[self._template("hello_world"), self._template("aviso_de_pago")],
        )
        self.client.force_login(self.staff)
        with patch.object(meta_templates, "list_templates", return_value=result):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("hello_world", content)
        self.assertIn("aviso_de_pago — utility", content)

    def test_the_form_offers_the_sample_with_its_mark_when_it_is_the_only_one(self):
        result = meta_templates.TemplateListResult(
            ok=True, templates=[self._template("hello_world")]
        )
        self.client.force_login(self.staff)
        with patch.object(meta_templates, "list_templates", return_value=result):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        # La plantilla de muestra se ofrece, pero con la marca pegada al nombre.
        self.assertIn(
            "hello_world — utility · PLANTILLA DE PRUEBA META",
            response.content.decode(),
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
