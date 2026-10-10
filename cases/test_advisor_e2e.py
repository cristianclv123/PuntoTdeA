from unittest.mock import patch
from itertools import count

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from cases.models import Channel, Contact, Conversation, Department, Message
from cases.services.assignment import ClaimError, claim_conversation
from cases.services.ingestion import InboundPayload, ingest_inbound_message
from cases.views import _bandeja_list_context
from communications.adapters.base import SendResult
from communications.models import MessageTemplate

User = get_user_model()


def _unique_send_result(*_args, **_kwargs):
    token = next(_unique_send_result.counter)
    return SendResult(success=True, provider_message_id=f"wamid.auto.{token}")


_unique_send_result.counter = count(1)


class AdvisorE2EMixin:
    def _make_users(self):
        self.owner = User.objects.create_user(
            username="asesor_owner", password="secret123", first_name="Ana", last_name="Dueña"
        )
        self.other = User.objects.create_user(
            username="asesor_otro", password="secret123", first_name="Luis", last_name="Otro"
        )
        self.staff = User.objects.create_user(
            username="asesor_staff",
            password="secret123",
            first_name="Sofia",
            last_name="Admin",
            is_staff=True,
        )

    def _make_whatsapp_conversation(self, **kwargs):
        channel = Channel.objects.get(code="whatsapp")
        contact = Contact.objects.create(
            full_name=kwargs.pop("full_name", "Camila Restrepo"),
            document_number=kwargs.pop("document_number", "DOC-E2E-1"),
            email=kwargs.pop("email", "camila@tdea.edu.co"),
            phone=kwargs.pop("phone", "573001112233"),
            academic_program="Sistemas",
            semester=3,
        )
        defaults = {
            "channel": channel,
            "contact": contact,
            "external_thread_id": kwargs.pop("external_thread_id", "wa-e2e-1"),
            "status": Conversation.Status.PENDIENTE,
        }
        defaults.update(kwargs)
        return Conversation.objects.create(**defaults)


class InboundE2ETests(AdvisorE2EMixin, TestCase):
    def setUp(self):
        self._make_users()
        self.api = APIClient()
        self.api.force_authenticate(user=self.owner)

    def test_ingest_inbound_appears_in_api_and_bandeja(self):
        conversation, message, created = ingest_inbound_message(
            InboundPayload(
                channel_code="whatsapp",
                external_thread_id="wa-e2e-inbound",
                body="Hola, necesito un certificado",
                external_message_id="wamid.inbound.1",
                contact_full_name="Camila Restrepo",
                contact_document_number="DOC-E2E-IN",
                contact_email="camila.in@tdea.edu.co",
                contact_phone="573009998877",
            )
        )
        self.assertTrue(created)
        self.assertEqual(conversation.channel.code, "whatsapp")
        self.assertIsNone(conversation.assigned_to_id)

        listed = self.api.get("/api/cases/tickets/", {"channel": "whatsapp"})
        self.assertEqual(listed.status_code, 200)
        payload = listed.data["results"] if isinstance(listed.data, dict) and "results" in listed.data else listed.data
        ids = {item["id"] for item in payload}
        self.assertIn(conversation.id, ids)

        request = RequestFactory().get(reverse("cases:bandeja"))
        request.user = self.owner
        bandeja_ids = {row["id"] for row in _bandeja_list_context(request)["conversations"]}
        self.assertIn(conversation.id, bandeja_ids)
        self.assertEqual(message.body, "Hola, necesito un certificado")

    @override_settings(ALLOW_WEBHOOK_SIMULATOR=True)
    def test_simulate_webhook_creates_whatsapp_ticket(self):
        res = self.api.post(
            reverse("simulate-webhook"),
            {
                "channel": "whatsapp",
                "body": "Mensaje simulado de WhatsApp",
                "full_name": "Sim WA",
                "phone": "573001234567",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            Conversation.objects.filter(
                channel__code="whatsapp",
                contact__phone="573001234567",
            ).exists()
        )


class OutboundClaimReplyCloseE2ETests(AdvisorE2EMixin, TestCase):
    def setUp(self):
        self._make_users()
        self.dept = Department.objects.get(code="registro_academico")
        self.conversation = self._make_whatsapp_conversation()
        self.api = APIClient()

    def _auth(self, user):
        self.api.force_authenticate(user=user)
        return self.api

    def test_claim_unassigned_then_second_advisor_conflict_staff_can_reclaim(self):
        owner_client = self._auth(self.owner)
        res = owner_client.post(f"/api/cases/tickets/{self.conversation.id}/claim/")
        self.assertEqual(res.status_code, 200)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.assigned_to_id, self.owner.id)

        other_client = self._auth(self.other)
        conflict = other_client.post(f"/api/cases/tickets/{self.conversation.id}/claim/")
        self.assertEqual(conflict.status_code, 409)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.assigned_to_id, self.owner.id)

        staff_client = self._auth(self.staff)
        takeover = staff_client.post(f"/api/cases/tickets/{self.conversation.id}/claim/")
        self.assertEqual(takeover.status_code, 200)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.assigned_to_id, self.staff.id)

    @patch("cases.services.ingestion.send_text_message")
    def test_reply_calls_meta_and_stores_wamid(self, send_text):
        send_text.side_effect = _unique_send_result
        claim_conversation(self.conversation.id, self.owner)

        res = self._auth(self.owner).post(
            f"/api/cases/tickets/{self.conversation.id}/reply/",
            {"body": "Claro, te ayudo con el certificado"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        send_text.assert_any_call("573001112233", "Claro, te ayudo con el certificado")
        self.assertGreaterEqual(send_text.call_count, 2)
        message = Message.objects.get(pk=res.data["id"])
        self.assertEqual(message.direction, Message.Direction.OUTBOUND)
        self.assertTrue(message.external_id.startswith("wamid.auto."))

    @patch("cases.services.ingestion.send_text_message")
    def test_reply_meta_failure_does_not_persist_message(self, send_text):
        send_text.return_value = SendResult(success=False, error="Meta rechazó el mensaje.")
        claim_conversation(self.conversation.id, self.owner)

        res = self._auth(self.owner).post(
            f"/api/cases/tickets/{self.conversation.id}/reply/",
            {"body": "Este no debe salir"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            Message.objects.filter(
                conversation=self.conversation,
                direction=Message.Direction.OUTBOUND,
            ).count(),
            0,
        )

    @patch("cases.services.ingestion.MetaAdapter.send_template_message")
    def test_reply_with_meta_template(self, send_template):
        send_template.return_value = SendResult(success=True, provider_message_id="wamid.tpl.9")
        claim_conversation(self.conversation.id, self.owner)
        template = MessageTemplate.objects.create(
            name="Certificado",
            meta_template_name="certificado_ok",
            body_text="Hola {{1}}, tu certificado está listo.",
            status=MessageTemplate.Status.APPROVED,
        )

        res = self._auth(self.owner).post(
            f"/api/cases/tickets/{self.conversation.id}/reply/",
            {"template_id": template.id, "template_params": {"1": "Camila"}},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        send_template.assert_called_once()
        message = Message.objects.get(pk=res.data["id"])
        self.assertEqual(message.external_id, "wamid.tpl.9")
        self.assertIn("Camila", message.body)

    def test_close_validations_permissions_and_blocks_reply(self):
        claim_conversation(self.conversation.id, self.owner)

        missing = self._auth(self.owner).post(f"/api/cases/tickets/{self.conversation.id}/close/")
        self.assertEqual(missing.status_code, 400)

        forbidden = self._auth(self.other).post(
            f"/api/cases/tickets/{self.conversation.id}/close/",
            {"department_id": self.dept.id},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)

        closed = self._auth(self.owner).post(
            f"/api/cases/tickets/{self.conversation.id}/close/",
            {"department_id": self.dept.id},
            format="json",
        )
        self.assertEqual(closed.status_code, 200)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.CERRADO)

        with self.assertRaises(ClaimError):
            claim_conversation(self.conversation.id, self.staff)

        reply = self._auth(self.owner).post(
            f"/api/cases/tickets/{self.conversation.id}/reply/",
            {"body": "Ya cerrado"},
            format="json",
        )
        self.assertEqual(reply.status_code, 403)

    @patch("cases.services.ingestion.send_text_message")
    def test_staff_can_reply_without_being_owner(self, send_text):
        send_text.side_effect = _unique_send_result
        claim_conversation(self.conversation.id, self.owner)
        res = self._auth(self.staff).post(
            f"/api/cases/tickets/{self.conversation.id}/reply/",
            {"body": "Respuesta de staff"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        send_text.assert_any_call("573001112233", "Respuesta de staff")
        self.assertGreaterEqual(send_text.call_count, 2)


class HtmlClaimCloseE2ETests(AdvisorE2EMixin, TestCase):
    def setUp(self):
        self._make_users()
        self.dept = Department.objects.get(code="registro_academico")
        self.conversation = self._make_whatsapp_conversation()
        self.client = Client()

    @patch("cases.services.ingestion.send_text_message")
    def test_html_claim_reply_close(self, send_text):
        send_text.side_effect = _unique_send_result
        self.client.login(username="asesor_owner", password="secret123")
        claim_res = self.client.post(reverse("cases:claim", args=[self.conversation.id]))
        self.assertEqual(claim_res.status_code, 302)

        reply_res = self.client.post(
            reverse("cases:detail", args=[self.conversation.id]),
            {"action": "reply", "body": "Te confirmo por WhatsApp"},
        )
        self.assertEqual(reply_res.status_code, 302)
        send_text.assert_any_call("573001112233", "Te confirmo por WhatsApp")
        self.assertGreaterEqual(send_text.call_count, 2)

        close_res = self.client.post(
            reverse("cases:detail", args=[self.conversation.id]),
            {
                "action": "close_case",
                "priority": "media",
                "assigned_to": str(self.owner.id),
                "department": str(self.dept.id),
            },
        )
        self.assertEqual(close_res.status_code, 302)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, Conversation.Status.CERRADO)
