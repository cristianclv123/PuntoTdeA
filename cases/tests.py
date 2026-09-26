from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
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
from cases.services.assignment import ClaimError, claim_conversation
from cases.services.attachments import detect_kind, validate_uploaded_file
from cases.services.ingestion import InboundPayload, create_outbound_message, ingest_inbound_message

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
        self.assertIn(contact_res.status_code, (200, 201))
        contact_id = contact_res.json()["id"]

        msg_res = client.post(
            reverse("web-messages"),
            data={"contact_id": contact_id, "body": "Necesito info de matrícula"},
            content_type="application/json",
        )
        self.assertEqual(msg_res.status_code, 201)
        conv = Conversation.objects.get(channel__code="web")
        self.assertIsNone(conv.assigned_to_id)

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
        self.user = User.objects.create_user(username="asesor_case", password="secret123")
        self.client.login(username="asesor_case", password="secret123")
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
        res = self.client.get(reverse("cases:bandeja"))
        self.assertEqual(res.status_code, 200)
        ids = {c["id"] for c in res.context["conversations"]}
        self.assertIn(open_conv.id, ids)
        self.assertNotIn(closed_conv.id, ids)

        closed_res = self.client.get(reverse("cases:bandeja"), {"closed": "1"})
        self.assertEqual(closed_res.status_code, 200)
        self.assertEqual(closed_res.context["active_tab"], "closed")
        closed_ids = {c["id"] for c in closed_res.context["conversations"]}
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
        self.advisor_a = User.objects.create_user(username="adv_a", password="secret123")
        self.advisor_b = User.objects.create_user(username="adv_b", password="secret123")

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
            0,
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
            1,
        )
