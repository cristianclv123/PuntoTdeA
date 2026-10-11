from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from cases.models import Message
from cases.services.assignment import (
    ClaimError,
    advisor_can_reply,
    claim_conversation,
    claim_greeting_body,
    user_can_act_on_conversation,
)
from cases.services.ingestion import create_outbound_message
from tests.helpers import make_conversation, make_user, meta_fail, meta_ok


class CasesUnitTests(TestCase):
    def setUp(self):
        self.owner = make_user("t_owner", first_name="Ana", last_name="López")
        self.other = make_user("t_other")
        self.staff = make_user("t_staff", staff=True)

    def test_permissions_owner_staff_other(self):
        conv = make_conversation(assigned_to=self.owner)
        self.assertTrue(user_can_act_on_conversation(conv, self.owner))
        self.assertTrue(user_can_act_on_conversation(conv, self.staff))
        self.assertFalse(user_can_act_on_conversation(conv, self.other))
        self.assertTrue(advisor_can_reply(conv, self.owner))

    def test_web_outbound_does_not_call_meta(self):
        conv = make_conversation(channel="web", document="DOC-WEB-U", assigned_to=self.owner)
        with patch("cases.services.ingestion.send_text_message") as send:
            msg = create_outbound_message(conv, "Hola web")
        send.assert_not_called()
        self.assertEqual(msg.direction, Message.Direction.OUTBOUND)

    @patch("cases.services.ingestion.send_text_message")
    def test_whatsapp_outbound_stores_wamid(self, send):
        send.return_value = meta_ok("wamid.unit")
        conv = make_conversation(assigned_to=self.owner)
        msg = create_outbound_message(conv, "Hola WA")
        send.assert_called_once_with("573001000000", "Hola WA")
        self.assertEqual(msg.external_id, "wamid.unit")

    @patch("cases.services.ingestion.send_text_message")
    def test_whatsapp_outbound_failure_does_not_persist(self, send):
        send.return_value = meta_fail("Sin token")
        conv = make_conversation(assigned_to=self.owner)
        with self.assertRaises(ValidationError):
            create_outbound_message(conv, "No")
        self.assertFalse(
            Message.objects.filter(conversation=conv, direction=Message.Direction.OUTBOUND).exists()
        )

    @patch("cases.services.ingestion.send_text_message")
    def test_claim_greeting_uses_advisor_name(self, send):
        send.return_value = meta_ok("wamid.hi")
        conv = make_conversation()
        claim_conversation(conv.id, self.owner)
        body = claim_greeting_body(self.owner)
        send.assert_called_once_with("573001000000", body)
        self.assertIn("Ana López", body)

    def test_claim_not_found(self):
        with self.assertRaises(ClaimError) as ctx:
            claim_conversation(999999, self.owner)
        self.assertEqual(ctx.exception.code, "not_found")
