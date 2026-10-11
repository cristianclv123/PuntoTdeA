from datetime import datetime, time, timezone as dt_tz
from unittest.mock import Mock, patch

from django.test import TestCase

from knowledge.chatbot.schedule import BusinessSchedule
from knowledge.chatbot.whatsapp import handle_message
from knowledge.chatbot.workflow import ChatbotWorkflow
from knowledge.models import ChatConversation


def _wf():
    conversation = ChatConversation.objects.create()
    workflow = ChatbotWorkflow(
        conversation,
        responder=lambda q: {
            "answer": f"Respuesta: {q}",
            "confidence": 1.0,
            "needs_human_attention": False,
            "sources": [],
        },
        schedule=BusinessSchedule(
            weekdays=frozenset({0, 1, 2, 3, 4}),
            opening_time=time(8),
            closing_time=time(17),
        ),
    )
    return conversation, workflow


class KnowledgeEstadoTests(TestCase):
    def test_ciclo_pregunta_confirmacion_fin(self):
        conv, wf = _wf()
        self.assertEqual(wf.start()["state"], "waiting_question")
        self.assertEqual(wf.submit_question("¿Cuándo matrícula?")["state"], "waiting_confirmation")
        self.assertEqual(wf.confirm_more_help(False)["state"], "ended")
        conv.refresh_from_db()
        self.assertEqual(conv.status, ChatConversation.STATUS_ENDED)
        self.assertEqual(conv.flow_state, "ended")

    def test_mas_ayuda_pasa_a_help_options(self):
        _, wf = _wf()
        wf.submit_question("Horario de clases")
        self.assertEqual(wf.confirm_more_help(True)["state"], "help_options")

    def test_escalar_pide_pregunta_para_asesor_luego_pending(self):
        conv, wf = _wf()
        wf.escalate("Quiere humano")
        conv.refresh_from_db()
        self.assertEqual(conv.flow_state, "waiting_advisor_question")
        result = wf.submit_advisor_question(
            "Revisen mi caso de matrícula",
            datetime(2026, 9, 18, 15, 0, tzinfo=dt_tz.utc),
        )
        self.assertEqual(result["state"], "pending")
        conv.refresh_from_db()
        self.assertEqual(conv.status, ChatConversation.STATUS_PENDING)

    def test_pregunta_invalida_se_queda_esperando(self):
        _, wf = _wf()
        wf.start()
        bad = wf.submit_question("??")
        self.assertFalse(bad["valid"])
        self.assertEqual(bad["state"], "waiting_question")

    @patch(
        "knowledge.chatbot.workflow.generate_response",
        new=Mock(
            return_value={
                "answer": "Ok",
                "confidence": 0.9,
                "needs_human_attention": False,
                "sources": [],
            }
        ),
    )
    def test_whatsapp_pending_deja_de_avanzar_el_flujo(self):
        handle_message("573000000001", "Hola")
        handle_message("573000000001", "Quiero un asesor")
        handle_message("573000000001", "Ayuda con matrícula")
        conv = ChatConversation.objects.get(external_user_id="573000000001")
        self.assertEqual(conv.status, ChatConversation.STATUS_PENDING)
        again = handle_message("573000000001", "Otro mensaje")
        self.assertEqual(again, [])
        conv.refresh_from_db()
        self.assertEqual(conv.flow_state, "pending")
