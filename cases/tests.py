import hashlib
import hmac
import json

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

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
from cases.services.attachments import detect_kind, validate_uploaded_file
from cases.services.ingestion import InboundPayload, create_outbound_message, ingest_inbound_message
from cases.services.meta import parse_meta_webhook, validate_meta_signature, verify_meta_token


class ModelTests(TestCase):
    def test_channel_seed_and_contact_fields(self):
        self.assertTrue(Channel.objects.filter(code="whatsapp").exists())
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
            channel_code="whatsapp",
            external_thread_id="573001112233",
            body="Hola",
            external_message_id="wamid.1",
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


class MetaWebhookTests(TestCase):
    def test_verify_token(self):
        challenge = verify_meta_token("subscribe", "puntotdea-dev-verify", "12345")
        self.assertEqual(challenge, "12345")
        self.assertIsNone(verify_meta_token("subscribe", "wrong", "12345"))

    @override_settings(META_APP_SECRET="secret")
    def test_signature_validation(self):
        body = b'{"object":"whatsapp_business_account"}'
        digest = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(validate_meta_signature(body, f"sha256={digest}"))
        self.assertFalse(validate_meta_signature(body, "sha256=bad"))

    def test_parse_whatsapp_payload(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [
                                    {"profile": {"name": "Ana"}, "wa_id": "57300"}
                                ],
                                "messages": [
                                    {
                                        "from": "57300",
                                        "id": "wamid.abc",
                                        "type": "text",
                                        "text": {"body": "Hola Punto TdeA"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }
        items = parse_meta_webhook(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].body, "Hola Punto TdeA")
        self.assertEqual(items[0].channel_code, "whatsapp")

    def test_meta_webhook_get_and_post(self):
        client = Client()
        url = reverse("meta-webhook")
        ok = client.get(
            url,
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "puntotdea-dev-verify",
                "hub.challenge": "challenge-token",
            },
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.content.decode(), "challenge-token")

        body = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [
                                    {"profile": {"name": "Ana"}, "wa_id": "57300"}
                                ],
                                "messages": [
                                    {
                                        "from": "57300",
                                        "id": "wamid.post1",
                                        "type": "text",
                                        "text": {"body": "Desde Meta"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }
        response = client.post(
            url,
            data=json.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Message.objects.count(), 1)


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
        self.assertIn(contact_res.status_code, (200, 201))
        contact_id = contact_res.json()["id"]

        msg_res = client.post(
            reverse("web-messages"),
            data={"contact_id": contact_id, "body": "Necesito info de matrícula"},
            content_type="application/json",
        )
        self.assertEqual(msg_res.status_code, 201)
        self.assertEqual(Conversation.objects.filter(channel__code="web").count(), 1)

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
        self.assertTrue(Conversation.objects.filter(channel__code="instagram").exists())


class CaseActionsTests(TestCase):
    def setUp(self):
        self.client = Client()
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


class AttachmentAndTemplateTests(TestCase):
    def setUp(self):
        self.client = Client()
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
            ReplyTemplate.objects.filter(title="Bienvenida rápida", is_active=True).exists()
        )

    def test_seeded_templates_exist(self):
        self.assertTrue(ReplyTemplate.objects.filter(title="Saludo inicial").exists())
