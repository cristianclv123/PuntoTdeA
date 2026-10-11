from itertools import count
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from cases.models import Conversation, Message
from cases.services.assignment import claim_greeting_body
from cases.services.ingestion import InboundPayload, ingest_inbound_message
from communications.adapters.base import SendResult
from tests.helpers import department, make_user

_wamid = count(1)


def _send_ok(*_a, **_k):
    return SendResult(success=True, provider_message_id=f"wamid.e2e.{next(_wamid)}")


class CasesE2ETests(TestCase):
    def setUp(self):
        self.owner = make_user("e2e_owner", first_name="Sofía", last_name="Ruiz")
        self.other = make_user("e2e_other")
        self.dept = department()
        self.api = APIClient()
        self.web = Client()

    @override_settings(ALLOW_WEBHOOK_SIMULATOR=True)
    @patch("cases.services.ingestion.send_text_message", side_effect=_send_ok)
    def test_inbound_claim_greeting_reply_close(self, send):
        sim = self.api.post(
            reverse("simulate-webhook"),
            {
                "channel": "whatsapp",
                "body": "Necesito un certificado",
                "full_name": "Laura Mesa",
                "phone": "573008887766",
                "document_number": "DOC-E2E-FLOW",
            },
            format="json",
        )
        self.assertEqual(sim.status_code, 201)
        conv_id = sim.data["conversation_id"]

        self.api.force_authenticate(self.owner)
        listed = self.api.get("/api/cases/tickets/", {"channel": "whatsapp"})
        ids = [row["id"] for row in listed.data]
        self.assertIn(conv_id, ids)

        claim = self.api.post(f"/api/cases/tickets/{conv_id}/claim/")
        self.assertEqual(claim.status_code, 200)
        send.assert_any_call("573008887766", claim_greeting_body(self.owner))

        conflict = APIClient()
        conflict.force_authenticate(self.other)
        self.assertEqual(conflict.post(f"/api/cases/tickets/{conv_id}/claim/").status_code, 409)

        reply = self.api.post(
            f"/api/cases/tickets/{conv_id}/reply/",
            {"body": "Claro, te ayudo con el certificado"},
            format="json",
        )
        self.assertEqual(reply.status_code, 201)

        closed = self.api.post(
            f"/api/cases/tickets/{conv_id}/close/",
            {"department_id": self.dept.id},
            format="json",
        )
        self.assertEqual(closed.status_code, 200)
        conv = Conversation.objects.get(pk=conv_id)
        self.assertEqual(conv.status, Conversation.Status.CERRADO)

        after = self.api.post(
            f"/api/cases/tickets/{conv_id}/reply/",
            {"body": "Ya no debería salir"},
            format="json",
        )
        self.assertEqual(after.status_code, 403)
        self.assertTrue(
            Message.objects.filter(
                conversation=conv,
                direction=Message.Direction.OUTBOUND,
                body__icontains="certificado",
            ).exists()
        )

    def test_ingest_idempotente_mismo_external_id(self):
        payload = InboundPayload(
            channel_code="whatsapp",
            external_thread_id="wa-idem-1",
            body="Hola",
            external_message_id="wamid.in.idem",
            contact_full_name="Idem User",
            contact_document_number="DOC-IDEM-1",
            contact_phone="573001010101",
        )
        c1, m1, created1 = ingest_inbound_message(payload)
        c2, m2, created2 = ingest_inbound_message(payload)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(c1.id, c2.id)
        self.assertEqual(m1.id, m2.id)
