from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import (
    Client,
    RequestFactory,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from django.urls import reverse
from django.conf import settings
from tempfile import TemporaryDirectory
from time import time as current_time
from unittest.mock import patch

from cases.models import (
    CaseComment,
    Channel,
    Contact,
    Conversation,
    Department,
    Message,
    MessageAttachment,
    ReplyTemplate,
)
from cases.services.assignment import ClaimError, claim_conversation
from cases.services.attachments import detect_kind, validate_uploaded_file
from cases.services.ingestion import InboundPayload, create_outbound_message, ingest_inbound_message
from cases.routing import websocket_urlpatterns
from cases.views import _bandeja_list_context

User = get_user_model()


class ModelTests(TestCase):
    def test_channel_seed_and_contact_fields(self):
        self.assertTrue(Channel.objects.filter(code="web").exists())
        contact = Contact.objects.create(
            full_name="Ana Pérez",
            document_number="123",
            email="ana@tdea.edu.co",
            phone="3001112233",
            academic_program="Ingeniería de Sistemas",
            semester=3,
        )
        self.assertEqual(contact.initials, "AP")


class IngestionTests(TestCase):
    def test_ingest_is_idempotent_by_external_id(self):
        payload = InboundPayload(
            channel_code="web",
            external_thread_id="web-573001112233",
            body="Hola",
            external_message_id="web-msg-1",
            contact_full_name="Ana Pérez",
            contact_document_number="DOC-1",
            contact_email="ana@tdea.edu.co",
            contact_phone="3001112233",
        )
        conv1, msg1, created1 = ingest_inbound_message(payload)
        conv2, msg2, created2 = ingest_inbound_message(payload)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(conv1.id, conv2.id)
        self.assertEqual(msg1.id, msg2.id)
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertIsNone(conv1.assigned_to_id)


class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="asesor1",
            email="asesor1@tdea.edu.co",
            password="secret123",
            first_name="Ana",
            last_name="Asesor",
        )

    def test_bandeja_requires_login(self):
        res = self.client.get(reverse("cases:bandeja"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login/", res.url)

    def test_login_with_email(self):
        res = self.client.post(
            reverse("login"),
            {"username": "asesor1@tdea.edu.co", "password": "secret123"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("dashboard:index"))

    def test_profile_requires_login(self):
        res = self.client.get(reverse("profile"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login/", res.url)

    def test_profile_update(self):
        self.client.login(username="asesor1", password="secret123")
        res = self.client.post(
            reverse("profile"),
            {
                "action": "profile",
                "first_name": "Ana María",
                "last_name": "López",
                "email": "ana.lopez@tdea.edu.co",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Ana María")
        self.assertEqual(self.user.last_name, "López")
        self.assertEqual(self.user.email, "ana.lopez@tdea.edu.co")

    def test_profile_password_change(self):
        self.client.login(username="asesor1", password="secret123")
        res = self.client.post(
            reverse("profile"),
            {
                "action": "password",
                "current_password": "secret123",
                "new_password": "nuevaClave99",
                "confirm_password": "nuevaClave99",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("nuevaClave99"))


class WidgetApiTests(TestCase):
    def test_web_contact_and_message_flow(self):
        client = Client()

        contact_res = client.post(
            reverse("web-contacts"),
            data={
                "full_name": "Juan Calle",
                "document_number": "998877",
                "email": "juan@tdea.edu.co",
                "phone": "3009998877",
                "academic_program": "Sistemas",
                "semester": 5,
            },
            content_type="application/json",
        )

        self.assertEqual(contact_res.status_code, 201)

        contact_data = contact_res.json()
        self.assertIn("contact_credential", contact_data)

        msg_res = client.post(
            reverse("web-messages"),
            data={"body": "Necesito info de matrícula"},
            content_type="application/json",
            HTTP_X_WIDGET_CREDENTIAL=contact_data["contact_credential"],
        )

        self.assertEqual(
            msg_res.status_code,
            201,
            msg=f"Estado: {msg_res.status_code}. Respuesta: {msg_res.content.decode('utf-8')}",
        )

        message_data = msg_res.json()
        self.assertIn("conversation_credential", message_data)

        conv = Conversation.objects.get(
            channel__code="web",
            pk=message_data["conversation_id"],
        )

        self.assertIsNone(conv.assigned_to_id)

        list_res = client.get(
            reverse(
                "web-messages-list",
                kwargs={"conversation_id": conv.pk},
            ),
            HTTP_X_WIDGET_CREDENTIAL=message_data["conversation_credential"],
        )

        self.assertEqual(list_res.status_code, 200)

        invalid_list_res = client.get(
            reverse(
                "web-messages-list",
                kwargs={"conversation_id": conv.pk},
            ),
            HTTP_X_WIDGET_CREDENTIAL=contact_data["contact_credential"],
        )
        mismatched_conversation_res = client.get(
            reverse(
                "web-messages-list",
                kwargs={"conversation_id": conv.pk + 1},
            ),
            HTTP_X_WIDGET_CREDENTIAL=message_data["conversation_credential"],
        )
        self.assertEqual(invalid_list_res.status_code, 403)
        self.assertEqual(mismatched_conversation_res.status_code, 403)

    def test_widget_rejects_missing_and_tampered_contact_credentials(self):
        contact = self.client.post(
            reverse("web-contacts"),
            data={
                "full_name": "Contacto firmado",
                "document_number": "DOC-WIDGET-TAMPER",
                "email": "widget-tamper@example.com",
                "phone": "3001234567",
                "academic_program": "Sistemas",
                "semester": 1,
            },
            content_type="application/json",
        ).json()
        url = reverse("web-messages")
        payload = {"body": "Mensaje sin identidad"}

        missing = self.client.post(
            url,
            data=payload,
            content_type="application/json",
        )
        tampered = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_X_WIDGET_CREDENTIAL=f'{contact["contact_credential"]}tampered',
        )

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(tampered.status_code, 403)

    def test_widget_rejects_an_expired_conversation_credential(self):
        contact_response = self.client.post(
            reverse("web-contacts"),
            data={
                "full_name": "Contacto vencido",
                "document_number": "DOC-WIDGET-EXPIRED",
                "email": "widget-expired@example.com",
                "phone": "3001234568",
                "academic_program": "Sistemas",
                "semester": 1,
            },
            content_type="application/json",
        )
        message_response = self.client.post(
            reverse("web-messages"),
            data={"body": "Primer mensaje"},
            content_type="application/json",
            HTTP_X_WIDGET_CREDENTIAL=contact_response.json()["contact_credential"],
        )
        self.assertEqual(message_response.status_code, 201)

        expired_at = current_time() + 90 * 24 * 60 * 60 + 1
        with patch("django.core.signing.time.time", return_value=expired_at):
            response = self.client.get(
                reverse(
                    "web-messages-list",
                    kwargs={"conversation_id": message_response.json()["conversation_id"]},
                ),
                HTTP_X_WIDGET_CREDENTIAL=message_response.json()[
                    "conversation_credential"
                ],
            )

        self.assertEqual(response.status_code, 403)

    def test_widget_does_not_issue_a_new_credential_for_an_existing_contact(self):
        client = Client()
        payload = {
            "full_name": "Juan Calle",
            "document_number": "998877",
            "email": "juan@tdea.edu.co",
            "phone": "3009998877",
            "academic_program": "Sistemas",
            "semester": 5,
        }
        first = client.post(
            reverse("web-contacts"),
            data=payload,
            content_type="application/json",
        )
        repeated = client.post(
            reverse("web-contacts"),
            data=payload,
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(repeated.status_code, 409)
        self.assertNotIn("contact_credential", repeated.json())


class CaseIntegrationWebhookTokenTests(TestCase):
    @override_settings(CASES_WEB_WEBHOOK_TOKEN="case-integration-secret")
    def test_web_ingestion_webhook_rejects_missing_or_invalid_token(self):
        payload = {"document_number": "DOC-NOT-LOOKED-UP", "body": "Mensaje"}

        missing = self.client.post(
            reverse("web-webhook"),
            data=payload,
            content_type="application/json",
        )
        invalid = self.client.post(
            reverse("web-webhook"),
            data=payload,
            content_type="application/json",
            HTTP_X_INTEGRATION_TOKEN="wrong-token",
        )

        self.assertEqual(missing.status_code, 403)
        self.assertEqual(invalid.status_code, 403)

    @override_settings(CASES_WEB_WEBHOOK_TOKEN="case-integration-secret")
    def test_valid_integration_token_preserves_public_ingestion_flow(self):
        contact = Contact.objects.create(
            full_name="Integración autorizada",
            document_number="DOC-INTEGRATION-OK",
            email="integration@example.com",
            phone="573001112244",
            semester=1,
        )

        response = self.client.post(
            reverse("web-webhook"),
            data={"contact_id": contact.pk, "body": "Mensaje integrado"},
            content_type="application/json",
            HTTP_X_INTEGRATION_TOKEN="case-integration-secret",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(
            Conversation.objects.filter(
                channel__code=Channel.Code.WEB,
                contact=contact,
            ).exists()
        )

    def test_simulate_webhook(self):
        client = Client()
        with self.settings(ALLOW_WEBHOOK_SIMULATOR=True):
            res = client.post(
                reverse("simulate-webhook"),
                data={
                    "channel": "instagram",
                    "body": "Mensaje simulado",
                    "full_name": "Sim User",
                    "phone": "3010000000",
                },
                content_type="application/json",
            )
        self.assertEqual(res.status_code, 201)
        conv = Conversation.objects.get(channel__code="instagram")
        self.assertIsNone(conv.assigned_to_id)


class CaseActionsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
        username="asesor_case",
        password="secret123",
        )

        cases_permission = Permission.objects.get(
            content_type__app_label="cases",
            codename="access_cases",
        )
        self.user.user_permissions.add(cases_permission)

        self.client.force_login(self.user)

        self.channel = Channel.objects.get(code="web")
        self.dept = Department.objects.get(code="registro_academico")
        self.contact = Contact.objects.create(
        full_name="Valentina Soto",
        document_number="DOC-CASE-1",
        email="vale@tdea.edu.co",
        phone="3002223344",
        academic_program="Sistemas",
        semester=4,
        )
        self.conversation = Conversation.objects.create(
            channel=self.channel,
            contact=self.contact,
            external_thread_id="web-DOC-CASE-1",
            assigned_to=self.user,
        )

    def test_ticket_number_auto_assigned(self):
        self.assertEqual(self.conversation.ticket_number, f"TDEA-{self.conversation.pk:06d}")

    def test_departments_seeded(self):
        self.assertGreaterEqual(Department.objects.count(), 8)
        self.assertTrue(Department.objects.filter(code="admisiones").exists())

    def test_escalated_requires_department(self):
        url = reverse("cases:detail", args=[self.conversation.id])
        res = self.client.post(
            url,
            {
                "action": "update_case",
                "status": "escalado",
                "priority": "alta",
                "department": "",
                "escalated_to": "",
                "assigned_to": "",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.PENDIENTE)

    def test_update_case_escalated_ok(self):
        url = reverse("cases:detail", args=[self.conversation.id])
        res = self.client.post(
            url,
            {
                "action": "update_case",
                "status": "escalado",
                "priority": "urgente",
                "department": str(self.dept.id),
                "escalated_to": str(self.dept.id),
                "assigned_to": "",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.ESCALADO)
        self.assertEqual(self.conversation.escalated_to_id, self.dept.id)
        self.assertEqual(self.conversation.priority, Conversation.Priority.URGENTE)

    def test_add_comment(self):
        url = reverse("cases:detail", args=[self.conversation.id])
        res = self.client.post(
            url,
            {
                "action": "add_comment",
                "comment_body": "Llamar a la estudiante mañana.",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(CaseComment.objects.filter(conversation=self.conversation).count(), 1)

    def test_close_case_requires_management(self):
        self.conversation.assigned_to = None
        self.conversation.department = None
        self.conversation.save()
        url = reverse("cases:detail", args=[self.conversation.id])
        res = self.client.post(
            url,
            {
                "action": "close_case",
                "status": "pendiente",
                "priority": "media",
                "assigned_to": "",
                "department": "",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.conversation.refresh_from_db()
        self.assertNotEqual(self.conversation.status, Conversation.Status.CERRADO)

    def test_close_case_ok_when_managed(self):
        url = reverse("cases:detail", args=[self.conversation.id])
        res = self.client.post(
            url,
            {
                "action": "close_case",
                "status": "pendiente",
                "priority": "media",
                "assigned_to": str(self.user.id),
                "department": str(self.dept.id),
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertIn(f"/bandeja/{self.conversation.id}/", res.url)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.CERRADO)
        self.assertEqual(self.conversation.assigned_to_id, self.user.id)
        self.assertEqual(self.conversation.department_id, self.dept.id)
        self.assertIsNotNone(self.conversation.closed_at)
        self.assertEqual(self.conversation.closed_by_id, self.user.id)
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conversation,
                direction=Message.Direction.SYSTEM,
                body__icontains="cerró el caso",
            ).exists()
        )

    def test_claim_records_system_event(self):
        from cases.services.assignment import claim_conversation

        self.conversation.assigned_to = None
        self.conversation.claimed_at = None
        self.conversation.claimed_by = None
        self.conversation.save()
        claimed = claim_conversation(self.conversation.id, self.user)
        self.assertEqual(claimed.assigned_to_id, self.user.id)
        self.assertIsNotNone(claimed.claimed_at)
        self.assertEqual(claimed.claimed_by_id, self.user.id)
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conversation,
                direction=Message.Direction.SYSTEM,
                body__icontains="tomó el caso",
            ).exists()
        )

    def test_closed_cases_excluded_from_bandeja(self):
        wa = Channel.objects.get(code="whatsapp")
        contact = Contact.objects.create(
            full_name="Cerrado Demo",
            document_number="DOC-CLOSED-1",
            email="closed@tdea.edu.co",
            phone="3000000001",
            academic_program="Sistemas",
            semester=1,
        )
        open_conv = Conversation.objects.create(
            channel=wa,
            contact=contact,
            external_thread_id="wa-open-1",
            status=Conversation.Status.PENDIENTE,
        )
        closed_conv = Conversation.objects.create(
            channel=wa,
            contact=contact,
            external_thread_id="wa-closed-1",
            status=Conversation.Status.CERRADO,
            assigned_to=self.user,
            department=self.dept,
        )
        request = RequestFactory().get(reverse("cases:bandeja"))
        request.user = self.user
        ids = {c["id"] for c in _bandeja_list_context(request)["conversations"]}
        self.assertIn(open_conv.id, ids)
        self.assertNotIn(closed_conv.id, ids)

        closed_request = RequestFactory().get(reverse("cases:bandeja"), {"closed": "1"})
        closed_request.user = self.user
        closed_ctx = _bandeja_list_context(closed_request)
        self.assertEqual(closed_ctx["active_tab"], "closed")
        closed_ids = {c["id"] for c in closed_ctx["conversations"]}
        self.assertIn(closed_conv.id, closed_ids)
        self.assertNotIn(open_conv.id, closed_ids)


class AttachmentAndTemplateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="asesor_att", password="secret123")
        self.client.login(username="asesor_att", password="secret123")
        self.channel = Channel.objects.get(code="web")
        self.contact = Contact.objects.create(
            full_name="Carlos Ruiz",
            document_number="DOC-ATT-1",
            email="carlos@tdea.edu.co",
            phone="3009998877",
            academic_program="Derecho",
            semester=2,
        )
        self.conversation = Conversation.objects.create(
            channel=self.channel,
            contact=self.contact,
            external_thread_id="web-DOC-ATT-1",
            assigned_to=self.user,
        )

    def test_detect_kind_allows_office_and_rejects_exe(self):
        self.assertEqual(detect_kind("acta.pdf"), "office")
        self.assertEqual(detect_kind("foto.PNG"), "image")
        self.assertEqual(detect_kind("clip.mp4"), "video")
        with self.assertRaises(ValidationError):
            detect_kind("malware.exe")

    def test_create_outbound_with_pdf_attachment(self):
        pdf = SimpleUploadedFile(
            "certificado.pdf",
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )
        msg = create_outbound_message(
            self.conversation,
            "Adjunto certificado",
            uploaded_files=[pdf],
        )
        self.assertEqual(msg.attachments.count(), 1)
        att = msg.attachments.get()
        self.assertEqual(att.kind, MessageAttachment.Kind.OFFICE)
        self.assertEqual(att.original_name, "certificado.pdf")

    def test_reject_disallowed_extension(self):
        bad = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        with self.assertRaises(ValidationError):
            validate_uploaded_file(bad)


    def test_create_reply_template_via_post(self):
        self._grant_cases_permission()

        url = reverse("cases:detail", args=[self.conversation.id])
        res = self.client.post(
            url,
            {
                "action": "create_template",
                "template_title": "Bienvenida rápida",
                "template_body": "Hola, ¿en qué te ayudo?",
            },
        )

        self.assertEqual(res.status_code, 302)
        self.assertTrue(
            ReplyTemplate.objects.filter(
                title="Bienvenida rápida",
                is_active=True,
            ).exists()
        )

    def test_seeded_templates_exist(self):
        self.assertTrue(ReplyTemplate.objects.filter(title="Saludo inicial").exists())

    def _create_test_attachment(self):
        content = b"contenido privado de prueba"

        message = Message.objects.create(
            conversation=self.conversation,
            direction=Message.Direction.OUTBOUND,
            body="Documento de prueba",
        )

        attachment = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile(
                "documento.txt",
                content,
                content_type="text/plain",
            ),
            original_name="documento.txt",
            content_type="text/plain",
            kind=MessageAttachment.Kind.OFFICE,
            size_bytes=len(content),
        )

        return attachment, content

    def _grant_cases_permission(self):
        permission = Permission.objects.get(
            content_type__app_label="cases",
            codename="access_cases",
        )
        self.user.user_permissions.add(permission)

        # Actualiza la sesión con un usuario recién cargado.
        self.client.force_login(User.objects.get(pk=self.user.pk))

    def test_download_attachment_requires_explicit_cases_permission(self):
        attachment, _ = self._create_test_attachment()

        response = self.client.get(
            reverse(
    "cases-attachment-download",
    kwargs={"attachment_id": attachment.pk},
)
        )

        self.assertEqual(response.status_code, 403)

    def test_user_with_cases_permission_can_download_attachment(self):
        attachment, expected_content = self._create_test_attachment()
        self._grant_cases_permission()

        response = self.client.get(
            reverse(
                "cases-attachment-download",
                kwargs={"attachment_id": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), expected_content)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertIn("attachment", response["Content-Disposition"])

    def test_safe_image_and_video_attachments_can_be_previewed_inline(self):
        message = Message.objects.create(
            conversation=self.conversation,
            direction=Message.Direction.OUTBOUND,
            body="Archivos de vista previa",
        )
        attachments = [
            MessageAttachment.objects.create(
                message=message,
                file=SimpleUploadedFile(
                    "vista.jpg",
                    bytes([255, 216, 255]),
                    content_type="image/jpeg",
                ),
                original_name="vista.jpg",
                content_type="image/jpeg",
                kind=MessageAttachment.Kind.IMAGE,
                size_bytes=3,
            ),
            MessageAttachment.objects.create(
                message=message,
                file=SimpleUploadedFile(
                    "vista.mp4",
                    b"video",
                    content_type="video/mp4",
                ),
                original_name="vista.mp4",
                content_type="video/mp4",
                kind=MessageAttachment.Kind.VIDEO,
                size_bytes=5,
            ),
        ]
        self._grant_cases_permission()

        for attachment in attachments:
            with self.subTest(name=attachment.original_name):
                response = self.client.get(
                    reverse(
                        "cases-attachment-download",
                        kwargs={"attachment_id": attachment.pk},
                    )
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn("inline", response["Content-Disposition"])
                self.assertEqual(
                    response["Content-Type"],
                    attachment.content_type,
                )

    def test_attachment_with_active_content_is_forced_to_download(self):
        message = Message.objects.create(
            conversation=self.conversation,
            direction=Message.Direction.OUTBOUND,
            body="Imagen",
        )
        attachment = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile(
                "imagen.jpg",
                b"<html>contenido activo</html>",
                content_type="text/html",
            ),
            original_name="imagen.jpg",
            content_type="text/html",
            kind=MessageAttachment.Kind.IMAGE,
            size_bytes=30,
        )
        self._grant_cases_permission()

        response = self.client.get(
            reverse(
                "cases-attachment-download",
                kwargs={"attachment_id": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["Content-Type"], "application/octet-stream")


    def test_download_attachment_returns_404_for_missing_id(self):
        self._grant_cases_permission()

        response = self.client.get(
            reverse(
                "cases-attachment-download",
                kwargs={"attachment_id": 999999},
            )
        )

        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=True)
    def test_direct_media_url_for_attachment_returns_404(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.get(
                    "/media/cases/attachments/2026/10/documento.txt"
                )

        self.assertEqual(response.status_code, 404)

    def test_download_attachment_rejects_post(self):
        attachment, _ = self._create_test_attachment()

        # Autoriza al usuario para que la solicitud llegue a @require_GET.
        self._grant_cases_permission()

        response = self.client.post(
            reverse(
                "cases-attachment-download",
                kwargs={"attachment_id": attachment.pk},
            )
        )

        self.assertEqual(response.status_code, 405)


class WebSocketPermissionRevocationTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ws-revocation-user")
        self.permission = Permission.objects.get(
            content_type__app_label="cases",
            codename="access_cases",
        )
        self.user.user_permissions.add(self.permission)
        channel = Channel.objects.get(code="web")
        contact = Contact.objects.create(
            full_name="Estudiante WebSocket",
            document_number="DOC-WS-REVOKE",
            email="ws-revoke@example.edu",
            phone="3001234567",
            academic_program="Sistemas",
            semester=3,
        )
        self.conversation = Conversation.objects.create(
            channel=channel,
            contact=contact,
            external_thread_id="web-DOC-WS-REVOKE",
        )

    async def test_revoked_permission_closes_existing_subscriptions(self):
        cases = (
            ("/ws/bandeja/", "bandeja", "bandeja.event"),
            (
                f"/ws/conversations/{self.conversation.pk}/",
                f"conversation_{self.conversation.pk}",
                "conversation.event",
            ),
        )
        channel_layer = get_channel_layer()

        for path, group_name, event_type in cases:
            communicator = WebsocketCommunicator(
                URLRouter(websocket_urlpatterns),
                path,
            )
            communicator.scope["user"] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await database_sync_to_async(self.user.user_permissions.remove)(
                self.permission
            )
            await channel_layer.group_send(
                group_name,
                {"type": event_type, "private_data": "sensitive"},
            )

            close_event = await communicator.receive_output(timeout=1)
            self.assertEqual(close_event["type"], "websocket.close")
            self.assertEqual(close_event["code"], 4403)
            await communicator.wait()

            await database_sync_to_async(self.user.user_permissions.add)(
                self.permission
            )



class ClaimQueueTests(TestCase):
    def setUp(self):
        self.channel = Channel.objects.get(code="web")
        self.contact = Contact.objects.create(
        full_name="Luis Mesa",
        document_number="DOC-CLAIM-1",
        email="luis@tdea.edu.co",
        phone="3001110000",
        academic_program="Sistemas",
        semester=1,
        )
        self.conversation = Conversation.objects.create(
        channel=self.channel,
        contact=self.contact,
        external_thread_id="web-DOC-CLAIM-1",
        )

        self.advisor_a = User.objects.create_user(
            username="adv_a",
            password="secret123",
        )
        self.advisor_b = User.objects.create_user(
            username="adv_b",
            password="secret123",
        )

        cases_permission = Permission.objects.get(
            content_type__app_label="cases",
            codename="access_cases",
        )

        self.advisor_a.user_permissions.add(cases_permission)
        self.advisor_b.user_permissions.add(cases_permission)

    def test_claim_assigns_first_advisor(self):
        claimed = claim_conversation(self.conversation.id, self.advisor_a)
        self.assertEqual(claimed.assigned_to_id, self.advisor_a.id)
        with self.assertRaises(ClaimError):
            claim_conversation(self.conversation.id, self.advisor_b)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.assigned_to_id, self.advisor_a.id)

    def test_other_advisor_cannot_reply(self):
        claim_conversation(self.conversation.id, self.advisor_a)
        client = Client()
        client.login(username="adv_b", password="secret123")
        res = client.post(
            reverse("cases:detail", args=[self.conversation.id]),
            {"action": "reply", "body": "Hola desde otro"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(
            Message.objects.filter(
                conversation=self.conversation,
                direction=Message.Direction.OUTBOUND,
            ).count(),
            1,
        )

    def test_queue_lists_unassigned(self):
        self.assertTrue(
            Conversation.objects.filter(
                assigned_to__isnull=True,
                pk=self.conversation.id,
            ).exists()
        )
        claim_conversation(self.conversation.id, self.advisor_a)
        self.assertFalse(
            Conversation.objects.filter(
                assigned_to__isnull=True,
                pk=self.conversation.id,
            ).exists()
        )
        self.assertTrue(
            Conversation.objects.filter(
                assigned_to=self.advisor_a,
                pk=self.conversation.id,
            ).exists()
        )

    def test_owner_can_reply_after_claim(self):
        client = Client()
        client.login(username="adv_a", password="secret123")
        client.post(reverse("cases:claim", args=[self.conversation.id]))
        res = client.post(
            reverse("cases:detail", args=[self.conversation.id]),
            {"action": "reply", "body": "Ya te ayudo"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(
            Message.objects.filter(
                conversation=self.conversation,
                direction=Message.Direction.OUTBOUND,
            ).count(),
            2,
        )
