from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from cases.models import Channel, Contact, Conversation, Department, Message
from cases.services.assignment import (
    ClaimError,
    CloseError,
    advisor_can_reply,
    claim_conversation,
    close_conversation,
    user_can_act_on_conversation,
)
from cases.services.ingestion import create_outbound_message
from communications.adapters.base import SendResult
from communications.models import MessageTemplate

User = get_user_model()


class AssignmentOutboundFixtures(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="unit_owner", password="secret123")
        self.other = User.objects.create_user(username="unit_other", password="secret123")
        self.staff = User.objects.create_user(
            username="unit_staff", password="secret123", is_staff=True
        )
        self.dept = Department.objects.get(code="registro_academico")
        self.web = Channel.objects.get(code="web")
        self.whatsapp = Channel.objects.get(code="whatsapp")
        self.contact = Contact.objects.create(
            full_name="Unit Contact",
            document_number="DOC-UNIT-1",
            email="unit@tdea.edu.co",
            phone="573004445566",
            academic_program="Sistemas",
            semester=2,
        )

    def _conv(self, *, channel=None, **kwargs):
        defaults = {
            "channel": channel or self.whatsapp,
            "contact": self.contact,
            "external_thread_id": kwargs.pop("external_thread_id", f"unit-{Conversation.objects.count()}"),
        }
        defaults.update(kwargs)
        return Conversation.objects.create(**defaults)


class UserCanActTests(AssignmentOutboundFixtures):
    def test_owner_and_staff_can_act_other_cannot(self):
        conversation = self._conv(assigned_to=self.owner)
        self.assertTrue(user_can_act_on_conversation(conversation, self.owner))
        self.assertTrue(user_can_act_on_conversation(conversation, self.staff))
        self.assertFalse(user_can_act_on_conversation(conversation, self.other))
        self.assertFalse(user_can_act_on_conversation(conversation, None))

    def test_unassigned_only_staff_can_act(self):
        conversation = self._conv()
        self.assertFalse(user_can_act_on_conversation(conversation, self.owner))
        self.assertTrue(user_can_act_on_conversation(conversation, self.staff))

    def test_advisor_cannot_reply_when_closed(self):
        conversation = self._conv(
            assigned_to=self.owner,
            status=Conversation.Status.CERRADO,
        )
        self.assertFalse(advisor_can_reply(conversation, self.owner))
        self.assertFalse(advisor_can_reply(conversation, self.staff))

    def test_staff_can_reply_unassigned_open_case(self):
        conversation = self._conv()
        self.assertTrue(advisor_can_reply(conversation, self.staff))
        self.assertFalse(advisor_can_reply(conversation, self.owner))


class ClaimConversationUnitTests(AssignmentOutboundFixtures):
    def test_unauthenticated_and_missing(self):
        with self.assertRaises(ClaimError) as ctx:
            claim_conversation(1, None)
        self.assertEqual(ctx.exception.code, "unauthenticated")
        with self.assertRaises(ClaimError) as ctx:
            claim_conversation(999999, self.owner)
        self.assertEqual(ctx.exception.code, "not_found")

    def test_closed_cannot_be_claimed_even_by_staff(self):
        conversation = self._conv(
            assigned_to=self.owner,
            status=Conversation.Status.CERRADO,
        )
        with self.assertRaises(ClaimError) as ctx:
            claim_conversation(conversation.id, self.staff)
        self.assertEqual(ctx.exception.code, "closed")

    def test_first_claim_assigns_owner_second_is_noop(self):
        conversation = self._conv()
        first = claim_conversation(conversation.id, self.owner)
        self.assertEqual(first.assigned_to_id, self.owner.id)
        second = claim_conversation(conversation.id, self.owner)
        self.assertEqual(second.assigned_to_id, self.owner.id)
        self.assertEqual(
            Message.objects.filter(
                conversation=conversation,
                direction=Message.Direction.SYSTEM,
            ).count(),
            1,
        )

    def test_other_advisor_cannot_claim_staff_can_reassign(self):
        conversation = self._conv()
        claim_conversation(conversation.id, self.owner)
        with self.assertRaises(ClaimError) as ctx:
            claim_conversation(conversation.id, self.other)
        self.assertEqual(ctx.exception.code, "already_assigned")
        taken = claim_conversation(conversation.id, self.staff)
        self.assertEqual(taken.assigned_to_id, self.staff.id)


class CloseConversationUnitTests(AssignmentOutboundFixtures):
    def test_missing_department_and_forbidden(self):
        conversation = self._conv(assigned_to=self.owner)
        with self.assertRaises(CloseError) as ctx:
            close_conversation(conversation.id, self.owner)
        self.assertEqual(ctx.exception.code, "missing_department")

        with self.assertRaises(CloseError) as ctx:
            close_conversation(
                conversation.id,
                self.other,
                department_id=self.dept.id,
            )
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_staff_can_close_unassigned_assigning_self(self):
        conversation = self._conv()
        closed = close_conversation(
            conversation.id,
            self.staff,
            department_id=self.dept.id,
        )
        self.assertEqual(closed.status, Conversation.Status.CERRADO)
        self.assertEqual(closed.assigned_to_id, self.staff.id)
        self.assertEqual(closed.department_id, self.dept.id)
        self.assertEqual(closed.closed_by_id, self.staff.id)

    def test_already_closed_and_invalid_priority(self):
        conversation = self._conv(assigned_to=self.owner, department=self.dept)
        close_conversation(conversation.id, self.owner)
        with self.assertRaises(CloseError) as ctx:
            close_conversation(conversation.id, self.owner)
        self.assertEqual(ctx.exception.code, "already_closed")

        open_conv = self._conv(
            assigned_to=self.owner,
            department=self.dept,
            external_thread_id="unit-prio",
        )
        with self.assertRaises(CloseError) as ctx:
            close_conversation(open_conv.id, self.owner, priority="no-existe")
        self.assertEqual(ctx.exception.code, "invalid_priority")

    def test_invalid_department_and_advisor(self):
        conversation = self._conv(assigned_to=self.owner)
        with self.assertRaises(CloseError) as ctx:
            close_conversation(conversation.id, self.owner, department_id=999999)
        self.assertEqual(ctx.exception.code, "invalid_department")
        with self.assertRaises(CloseError) as ctx:
            close_conversation(
                conversation.id,
                self.owner,
                assigned_to_id=999999,
                department_id=self.dept.id,
            )
        self.assertEqual(ctx.exception.code, "invalid_advisor")


class OutboundMetaUnitTests(AssignmentOutboundFixtures):
    @patch("cases.services.ingestion.send_text_message")
    def test_web_channel_does_not_call_meta(self, send_text):
        conversation = self._conv(channel=self.web, assigned_to=self.owner)
        message = create_outbound_message(conversation, "Hola por web")
        send_text.assert_not_called()
        self.assertEqual(message.external_id, "")
        self.assertEqual(message.body, "Hola por web")

    @patch("cases.services.ingestion.send_text_message")
    def test_whatsapp_text_sends_and_stores_wamid(self, send_text):
        send_text.return_value = SendResult(success=True, provider_message_id="wamid.unit.1")
        conversation = self._conv(assigned_to=self.owner)
        message = create_outbound_message(conversation, "  Hola Meta  ")
        send_text.assert_called_once_with("573004445566", "Hola Meta")
        self.assertEqual(message.external_id, "wamid.unit.1")

    @patch("cases.services.ingestion.send_text_message")
    def test_whatsapp_meta_error_rolls_back_message(self, send_text):
        send_text.return_value = SendResult(success=False, error="Sin token")
        conversation = self._conv(assigned_to=self.owner)
        with self.assertRaises(ValidationError) as ctx:
            create_outbound_message(conversation, "No debe persistir")
        self.assertIn("Sin token", ctx.exception.messages)
        self.assertEqual(
            Message.objects.filter(
                conversation=conversation,
                direction=Message.Direction.OUTBOUND,
            ).count(),
            0,
        )

    @patch("cases.services.ingestion.send_text_message")
    def test_attachment_only_skips_meta_text(self, send_text):
        conversation = self._conv(assigned_to=self.owner)
        pdf = SimpleUploadedFile("acta.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        message = create_outbound_message(conversation, "   ", uploaded_files=[pdf])
        send_text.assert_not_called()
        self.assertEqual(message.attachments.count(), 1)

    def test_empty_body_without_files_raises(self):
        conversation = self._conv(assigned_to=self.owner)
        with self.assertRaises(ValidationError):
            create_outbound_message(conversation, "   ")

    @patch("cases.services.ingestion.MetaAdapter.send_template_message")
    def test_meta_template_renders_body_and_stores_wamid(self, send_template):
        send_template.return_value = SendResult(success=True, provider_message_id="wamid.tpl.u")
        conversation = self._conv(assigned_to=self.owner)
        template = MessageTemplate.objects.create(
            name="Unit tpl",
            meta_template_name="unit_tpl_ok",
            body_text="Hola {{1}}",
            status=MessageTemplate.Status.APPROVED,
        )
        message = create_outbound_message(
            conversation,
            "",
            template=template,
            template_params={"1": "Camila"},
        )
        send_template.assert_called_once()
        self.assertEqual(message.body, "Hola Camila")
        self.assertEqual(message.external_id, "wamid.tpl.u")
