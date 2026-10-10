from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from communications.models import MessageTemplate
from communications.services import meta_templates

User = get_user_model()


def _response(payload, status_code=200):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload
    response.content = b"{}"
    return response


@override_settings(
    META_ACCESS_TOKEN="meta-access-token",
    WHATSAPP_BUSINESS_ACCOUNT_ID="waba-123",
    WHATSAPP_API_VERSION="v21.0",
    META_GRAPH_API_URL="https://graph.facebook.com",
    META_REQUEST_TIMEOUT=10,
)
class MetaTemplateServiceTests(TestCase):
    def setUp(self):
        self.draft = MessageTemplate.objects.create(
            name="Recordatorio de matrícula",
            category=MessageTemplate.Category.UTILITY,
            body_text="Hola {{1}}, tu cita es el {{2}}.",
            variable_types={"1": "text", "2": "date"},
        )

    def test_slugify_meta_name_strips_accents_and_symbols(self):
        self.assertEqual(
            meta_templates.slugify_meta_name("Recordatorio de Matrícula ¡2026!"),
            "recordatorio_de_matricula_2026",
        )
        # Nunca devuelve vacío: Meta exige un nombre válido.
        self.assertEqual(meta_templates.slugify_meta_name("###"), "plantilla")

    @patch("communications.services.meta_templates.requests.post")
    def test_create_from_draft_sends_components(self, post):
        post.return_value = _response(
            {"id": "999", "status": "PENDING", "category": "UTILITY"}
        )

        result = meta_templates.create_from_draft(self.draft)

        self.assertTrue(result.ok)
        self.assertEqual(result.meta_id, "999")
        self.assertEqual(result.meta_status, "PENDING")

        url = post.call_args.args[0]
        self.assertIn("waba-123/message_templates", url)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["name"], "recordatorio_de_matricula")
        self.assertEqual(payload["language"], "es_CO")
        self.assertEqual(payload["category"], "UTILITY")
        self.assertEqual(payload["components"][0]["type"], "BODY")
        # Un ejemplo por variable, en el orden en que aparecen.
        self.assertEqual(
            payload["components"][0]["example"]["body_text"],
            [["Ejemplo", "01/01/2026"]],
        )

    @patch("communications.services.meta_templates.requests.post")
    def test_create_uses_explicit_meta_name_when_given(self, post):
        post.return_value = _response({"id": "1", "status": "PENDING"})

        meta_templates.create_from_draft(self.draft, meta_name="Otro Nombre")

        self.assertEqual(post.call_args.kwargs["json"]["name"], "otro_nombre")

    @patch("communications.services.meta_templates.requests.post")
    def test_meta_error_is_reported(self, post):
        post.return_value = _response(
            {"error": {"message": "Template name already exists", "code": 100}},
            status_code=400,
        )

        result = meta_templates.create_from_draft(self.draft)

        self.assertFalse(result.ok)
        self.assertIn("Template name already exists", result.message)

    @override_settings(WHATSAPP_BUSINESS_ACCOUNT_ID="")
    def test_missing_config_is_reported(self):
        result = meta_templates.create_from_draft(self.draft)

        self.assertFalse(result.ok)
        self.assertEqual(result.kind, meta_templates.KIND_CONFIG)

    def test_media_header_is_rejected_locally(self):
        self.draft.header_type = MessageTemplate.HeaderType.IMAGE
        result = meta_templates.create_from_draft(self.draft)

        self.assertFalse(result.ok)
        self.assertEqual(result.kind, meta_templates.KIND_BUILD)

    @patch("communications.services.meta_templates.requests.get")
    def test_list_templates_normalizes_and_ignores_none_rejection(self, get):
        get.return_value = _response(
            {
                "data": [
                    {
                        "id": "999",
                        "name": "recordatorio",
                        "status": "APPROVED",
                        "category": "UTILITY",
                        "language": "es_CO",
                        "rejected_reason": "NONE",
                        "components": [
                            {"type": "BODY", "text": "Hola {{1}}"},
                            {
                                "type": "BUTTONS",
                                "buttons": [{"type": "URL", "text": "Ver", "url": "https://x.co"}],
                            },
                        ],
                    }
                ]
            }
        )

        result = meta_templates.list_templates()

        self.assertTrue(result.ok)
        self.assertEqual(len(result.templates), 1)
        template = result.templates[0]
        self.assertEqual(template["meta_id"], "999")
        self.assertEqual(template["status"], "APPROVED")
        self.assertEqual(template["category"], "utility")
        self.assertEqual(template["body_text"], "Hola {{1}}")
        self.assertEqual(template["rejected_reason"], "")
        self.assertEqual(template["buttons"][0]["text"], "Ver")

    @patch("communications.services.meta_templates.requests.get")
    def test_list_templates_reports_meta_error(self, get):
        get.return_value = _response(
            {"error": {"message": "boom", "code": 2}}, status_code=500
        )

        result = meta_templates.list_templates()

        self.assertFalse(result.ok)
        self.assertEqual(result.kind, meta_templates.KIND_META)

    @patch("communications.services.meta_templates.requests.get")
    def test_get_template_returns_normalized_detail(self, get):
        get.return_value = _response(
            {
                "id": "999",
                "name": "recordatorio",
                "status": "APPROVED",
                "components": [{"type": "BODY", "text": "Hola {{1}}"}],
            }
        )

        result = meta_templates.get_template("999")

        self.assertTrue(result.ok)
        self.assertEqual(result.template["status"], "APPROVED")
        self.assertIn("999", get.call_args.args[0])

    @patch("communications.services.meta_templates.requests.get")
    def test_get_template_not_found_is_meta_error(self, get):
        get.return_value = _response(
            {"error": {"message": "not found", "code": 100}}, status_code=404
        )

        result = meta_templates.get_template("404")

        self.assertFalse(result.ok)
        self.assertEqual(result.kind, meta_templates.KIND_META)

    @patch("communications.services.meta_templates.requests.post")
    def test_edit_template_posts_components_to_meta(self, post):
        post.return_value = _response({"status": "PENDING"})

        result = meta_templates.edit_template(
            "999", "Hola {{1}}", {"1": "text"}
        )

        self.assertTrue(result.ok)
        self.assertIn("999", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"]["components"][0]["type"], "BODY")

    @patch("communications.services.meta_templates.requests.delete")
    def test_delete_template_sends_hsm_id_and_name(self, delete):
        delete.return_value = _response({})

        result = meta_templates.delete_template("999", "recordatorio")

        self.assertTrue(result.ok)
        params = delete.call_args.kwargs["params"]
        self.assertEqual(params["hsm_id"], "999")
        self.assertEqual(params["name"], "recordatorio")


@override_settings(
    META_ACCESS_TOKEN="meta-access-token",
    WHATSAPP_BUSINESS_ACCOUNT_ID="waba-123",
    WHATSAPP_API_VERSION="v21.0",
    META_GRAPH_API_URL="https://graph.facebook.com",
    META_REQUEST_TIMEOUT=10,
)
class MetaTemplateAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="secret")
        self.client.force_login(self.user)
        self.draft = MessageTemplate.objects.create(
            name="Recordatorio",
            category=MessageTemplate.Category.UTILITY,
            body_text="Hola {{1}}.",
            variable_types={"1": "text"},
        )

    def test_create_draft_endpoint(self):
        response = self.client.post(
            "/campanas/api/templates/",
            data={
                "name": "Bienvenida",
                "category": "marketing",
                "body_text": "Hola {{1}}",
                "variable_types": {"1": "text"},
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["name"], "Bienvenida")
        self.assertEqual(body["param_count"], 1)
        self.assertTrue(MessageTemplate.objects.filter(pk=body["id"]).exists())

    def test_list_drafts_endpoint_returns_local_only(self):
        response = self.client.get("/campanas/api/templates/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data if isinstance(data, list) else data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.draft.pk)

    def test_update_draft_endpoint(self):
        response = self.client.patch(
            f"/campanas/api/templates/{self.draft.pk}/",
            data={"body_text": "Hola {{1}}, ¿cómo estás?"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.draft.refresh_from_db()
        self.assertIn("cómo estás", self.draft.body_text)

    @patch("communications.services.meta_templates.requests.post")
    def test_enviar_a_meta_deletes_draft_on_success(self, post):
        post.return_value = _response({"id": "999", "status": "PENDING"})

        response = self.client.post(
            f"/campanas/api/templates/{self.draft.pk}/enviar-a-meta/"
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["meta_id"], "999")
        self.assertEqual(body["meta_status"], "PENDING")
        self.assertEqual(body["meta_name"], "recordatorio")
        self.assertFalse(MessageTemplate.objects.filter(pk=self.draft.pk).exists())

    @patch("communications.services.meta_templates.requests.post")
    def test_enviar_a_meta_keeps_draft_on_error(self, post):
        post.return_value = _response(
            {"error": {"message": "boom", "code": 100}}, status_code=400
        )

        response = self.client.post(
            f"/campanas/api/templates/{self.draft.pk}/enviar-a-meta/"
        )

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()["success"])
        self.assertTrue(MessageTemplate.objects.filter(pk=self.draft.pk).exists())

    @patch("communications.services.meta_templates.requests.get")
    def test_meta_list_endpoint(self, get):
        get.return_value = _response(
            {"data": [{"id": "999", "name": "x", "status": "APPROVED"}]}
        )

        response = self.client.get("/campanas/api/templates/meta/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["templates"][0]["meta_id"], "999")

    @override_settings(WHATSAPP_BUSINESS_ACCOUNT_ID="")
    def test_meta_list_endpoint_reports_config_error(self):
        response = self.client.get("/campanas/api/templates/meta/")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["success"])

    @patch("communications.services.meta_templates.requests.get")
    def test_meta_detail_get_endpoint(self, get):
        get.return_value = _response(
            {
                "id": "999",
                "name": "recordatorio",
                "status": "APPROVED",
                "components": [{"type": "BODY", "text": "Hola {{1}}"}],
            }
        )

        response = self.client.get("/campanas/api/templates/meta/999/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["template"]["status"], "APPROVED")

    @patch("communications.services.meta_templates.requests.post")
    def test_meta_detail_post_edits_body(self, post):
        post.return_value = _response({"status": "PENDING"})

        response = self.client.post(
            "/campanas/api/templates/meta/999/",
            data={"body_text": "Hola {{1}}", "variable_types": {"1": "text"}},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_meta_detail_post_requires_body(self):
        response = self.client.post(
            "/campanas/api/templates/meta/999/",
            data={},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["success"])

    @patch("communications.services.meta_templates.requests.delete")
    def test_meta_detail_delete_endpoint(self, delete):
        delete.return_value = _response({})

        response = self.client.delete("/campanas/api/templates/meta/999/?name=recordatorio")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(delete.call_args.kwargs["params"]["hsm_id"], "999")
