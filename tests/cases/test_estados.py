from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from cases.models import Conversation, Message
from cases.services.assignment import ClaimError, advisor_can_reply, claim_conversation, close_conversation
from tests.helpers import department, make_conversation, make_user, meta_ok


class CasesEstadoTests(TestCase):
    def setUp(self):
        self.owner = make_user("st_owner")
        self.other = make_user("st_other")
        self.staff = make_user("st_staff", staff=True)
        cases_permission = Permission.objects.get(
            content_type__app_label="cases",
            codename="access_cases",
        )
        for user in (self.owner, self.other, self.staff):
            user.user_permissions.add(cases_permission)
        self.dept = department()
        self.api = APIClient()

    def test_nuevo_ticket_queda_pendiente_sin_asesor(self):
        conv = make_conversation()
        self.assertEqual(conv.status, Conversation.Status.PENDIENTE)
        self.assertIsNone(conv.assigned_to_id)

    def test_claim_pasa_a_asignado_y_no_cambia_pendiente(self):
        conv = make_conversation()
        claimed = claim_conversation(conv.id, self.owner)
        self.assertEqual(claimed.assigned_to_id, self.owner.id)
        self.assertEqual(claimed.status, Conversation.Status.PENDIENTE)
        self.assertIsNotNone(claimed.claimed_at)

    def test_cerrado_bloquea_claim_y_reply(self):
        conv = make_conversation(assigned_to=self.owner, department=self.dept)
        close_conversation(conv.id, self.owner)
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.Status.CERRADO)
        self.assertFalse(advisor_can_reply(conv, self.owner))
        self.assertFalse(advisor_can_reply(conv, self.staff))
        with self.assertRaises(ClaimError) as ctx:
            claim_conversation(conv.id, self.staff)
        self.assertEqual(ctx.exception.code, "closed")

    def test_patch_no_puede_poner_cerrado(self):
        conv = make_conversation(assigned_to=self.owner, department=self.dept)
        self.api.force_authenticate(self.owner)
        res = self.api.patch(
            f"/api/cases/tickets/{conv.id}/",
            {"status": Conversation.Status.CERRADO},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        conv.refresh_from_db()
        self.assertNotEqual(conv.status, Conversation.Status.CERRADO)

    def test_escalado_exige_dependencia_en_api(self):
        conv = make_conversation(assigned_to=self.owner)
        self.api.force_authenticate(self.owner)
        res = self.api.patch(
            f"/api/cases/tickets/{conv.id}/",
            {"status": Conversation.Status.ESCALADO},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        ok = self.api.patch(
            f"/api/cases/tickets/{conv.id}/",
            {
                "status": Conversation.Status.ESCALADO,
                "escalated_to_id": self.dept.id,
                "department_id": self.dept.id,
            },
            format="json",
        )
        self.assertEqual(ok.status_code, 200)
        conv.refresh_from_db()
        self.assertEqual(conv.status, Conversation.Status.ESCALADO)
        self.assertEqual(conv.escalated_to_id, self.dept.id)

    def test_sistema_registra_toma_y_cierre(self):
        conv = make_conversation(assigned_to=self.owner, department=self.dept)
        claim_conversation(conv.id, self.owner)
        close_conversation(conv.id, self.owner)
        bodies = list(
            Message.objects.filter(conversation=conv, direction=Message.Direction.SYSTEM).values_list(
                "body", flat=True
            )
        )
        self.assertTrue(any("tomó el caso" in b for b in bodies))
        self.assertTrue(any("cerró el caso" in b for b in bodies))

    @patch("cases.services.ingestion.send_text_message")
    def test_claim_idempotente_no_reenvia_saludo(self, send):
        send.return_value = meta_ok("wamid.once")
        conv = make_conversation()
        claim_conversation(conv.id, self.owner)
        claim_conversation(conv.id, self.owner)
        send.assert_called_once()
