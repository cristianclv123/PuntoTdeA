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
        self.template = MessageTemplate.objects.create(
            name="Recordatorio",
            meta_template_name="recordatorio_2026",
            language="es_CO",
            category=MessageTemplate.Category.UTILITY,
            body_text="Hola {{1}}, tu cita es el {{2}}.",
            variable_types={"1": "text", "2": "date"},
        )

    @patch("communications.services.meta_templates.requests.post")
    def test_create_stores_id_and_pending_status(self, post):
        post.return_value = _response(
            {"id": "999", "status": "PENDING", "category": "UTILITY"}
        )

        result = meta_templates.create_template(self.template)

        self.assertTrue(result.ok)
        self.template.refresh_from_db()
        self.assertEqual(self.template.meta_template_id, "999")
        self.assertEqual(self.template.meta_status, "PENDING")
        self.assertEqual(self.template.status, MessageTemplate.Status.PENDING)
        self.assertEqual(self.template.meta_rejection_reason, "")
        self.assertIsNotNone(self.template.meta_synced_at)

        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        self.assertIn("waba-123/message_templates", url)
        self.assertEqual(payload["name"], "recordatorio_2026")
        self.assertEqual(payload["category"], "UTILITY")
        self.assertEqual(payload["components"][0]["type"], "BODY")
        # Un ejemplo por variable, en el orden en que aparecen.
        self.assertEqual(
            payload["components"][0]["example"]["body_text"],
            [["Ejemplo", "01/01/2026"]],
        )

    @patch("communications.services.meta_templates.requests.post")
    def test_meta_error_is_reported(self, post):
        post.return_value = _response(
            {"error": {"message": "Template name already exists", "code": 100}},
            status_code=400,
        )

        result = meta_templates.create_template(self.template)

        self.assertFalse(result.ok)
        self.assertIn("Template name already exists", result.message)
        self.template.refresh_from_db()
        self.assertEqual(self.template.meta_template_id, "")

    @override_settings(WHATSAPP_BUSINESS_ACCOUNT_ID="")
    def test_missing_config_is_reported(self):
        result = meta_templates.create_template(self.template)

        self.assertFalse(result.ok)
        self.assertEqual(result.kind, meta_templates.KIND_CONFIG)

    def test_media_header_is_rejected_locally(self):
        self.template.header_type = MessageTemplate.HeaderType.IMAGE
        result = meta_templates.create_template(self.template)

        self.assertFalse(result.ok)
        self.assertEqual(result.kind, meta_templates.KIND_BUILD)

    @patch("communications.services.meta_templates.requests.get")
    def test_fetch_status_updates_to_approved(self, get):
        self.template.meta_template_id = "999"
        self.template.status = MessageTemplate.Status.PENDING
        self.template.save()
        get.return_value = _response(
            {
                "id": "999",
                "status": "APPROVED",
                "category": "UTILITY",
                "rejected_reason": "NONE",
            }
        )

        result = meta_templates.fetch_template_status(self.template)

        self.assertTrue(result.ok)
        self.template.refresh_from_db()
        self.assertEqual(self.template.meta_status, "APPROVED")
        self.assertEqual(self.template.status, MessageTemplate.Status.APPROVED)
        # "NONE" de Meta no es un motivo de rechazo real.
        self.assertEqual(self.template.meta_rejection_reason, "")

    @patch("communications.services.meta_templates.requests.get")
    def test_fetch_status_stores_rejection_reason(self, get):
        self.template.meta_template_id = "999"
        self.template.save()
        get.return_value = _response(
            {
                "id": "999",
                "status": "REJECTED",
                "rejected_reason": "Invalid variable format",
            }
        )

        meta_templates.fetch_template_status(self.template)

        self.template.refresh_from_db()
        self.assertEqual(self.template.status, MessageTemplate.Status.REJECTED)
        self.assertEqual(self.template.meta_rejection_reason, "Invalid variable format")

    @patch("communications.services.meta_templates.requests.get")
    def test_fetch_by_name_when_id_unknown(self, get):
        get.return_value = _response(
            {
                "data": [
                    {"id": "123", "name": "recordatorio_2026", "status": "APPROVED"}
                ]
            }
        )

        result = meta_templates.fetch_template_status(self.template)

        self.assertTrue(result.ok)
        self.template.refresh_from_db()
        self.assertEqual(self.template.meta_template_id, "123")
        self.assertEqual(self.template.status, MessageTemplate.Status.APPROVED)


@override_settings(
    META_ACCESS_TOKEN="meta-access-token",
    WHATSAPP_BUSINESS_ACCOUNT_ID="waba-123",
)
class MetaTemplateAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="staff", password="secret")
        self.client.force_login(self.user)
        self.template = MessageTemplate.objects.create(
            name="Recordatorio",
            meta_template_name="recordatorio_2026",
            body_text="Hola {{1}}.",
            variable_types={"1": "text"},
        )

    @patch("communications.services.meta_templates.requests.post")
    def test_enviar_a_meta_endpoint(self, post):
        post.return_value = _response({"id": "999", "status": "PENDING"})

        response = self.client.post(
            f"/campanas/api/templates/{self.template.pk}/enviar-a-meta/"
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["meta_id"], "999")
        self.assertEqual(body["template"]["meta_status"], "PENDING")

    @patch("communications.services.meta_templates.requests.post")
    def test_enviar_a_meta_reports_meta_error(self, post):
        post.return_value = _response(
            {"error": {"message": "Invalid parameter", "code": 100}}, status_code=400
        )

        response = self.client.post(
            f"/campanas/api/templates/{self.template.pk}/enviar-a-meta/"
        )

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()["success"])

    @patch("communications.services.meta_templates.requests.get")
    def test_consultar_estado_endpoint(self, get):
        self.template.meta_template_id = "999"
        self.template.save()
        get.return_value = _response({"id": "999", "status": "APPROVED"})

        response = self.client.post(
            f"/campanas/api/templates/{self.template.pk}/consultar-estado/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["template"]["status"], "approved")

    @patch("communications.services.meta_templates.requests.get")
    def test_consultar_estados_endpoint_refreshes_linked(self, get):
        self.template.meta_template_id = "999"
        self.template.save()
        get.return_value = _response({"id": "999", "status": "APPROVED"})

        response = self.client.post("/campanas/api/templates/consultar-estados/")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["updated"][0]["meta_status"], "APPROVED")
