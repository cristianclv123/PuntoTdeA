from unittest.mock import Mock, patch

from django.test import TestCase

from cases.models import Conversation as CaseConversation, Message as CaseMessage
from knowledge.chatbot.whatsapp import handle_message
from knowledge.models import ChatConversation


class KnowledgeE2ETests(TestCase):
    @patch(
        "knowledge.chatbot.workflow.generate_response",
        new=Mock(
            return_value={
                "answer": "La matrícula abre en enero.",
                "confidence": 0.9,
                "needs_human_attention": False,
                "sources": [],
            }
        ),
    )
    def test_whatsapp_bot_answer_without_ticket(self):
        hello = handle_message("573000111222", "Hola")
        self.assertTrue(hello)
        reply = handle_message("573000111222", "¿Cuándo son las matrículas?")
        self.assertTrue(reply[0])
        self.assertFalse(CaseConversation.objects.filter(external_thread_id="573000111222").exists())

    def test_pedir_asesor_crea_ticket_en_cases(self):
        handle_message("573000111223", "Hola")
        handle_message("573000111223", "Quiero hablar con un asesor")
        responses = handle_message("573000111223", "No pude matricularme")
        case = CaseConversation.objects.get(
            channel__code="whatsapp",
            external_thread_id="573000111223",
        )
        self.assertTrue(any(case.ticket_number in r for r in responses))
        bot = ChatConversation.objects.get(external_user_id="573000111223")
        self.assertEqual(bot.case_conversation_id, case.id)
        self.assertEqual(bot.status, ChatConversation.STATUS_ACTIVE)
        self.assertEqual(bot.flow_state, "help_options")
        self.assertEqual(
            CaseMessage.objects.get(conversation=case).body,
            "No pude matricularme",
        )

    @patch(
        "knowledge.chatbot.workflow.generate_response",
        new=Mock(
            return_value={
                "answer": "No encontré información.",
                "confidence": 0.0,
                "needs_human_attention": True,
                "sources": [],
            }
        ),
    )
    def test_baja_confianza_crea_ticket(self):
        handle_message("573000111224", "Hola")
        responses = handle_message("573000111224", "Tema muy específico que el bot no cubre")
        self.assertTrue(CaseConversation.objects.filter(external_thread_id="573000111224").exists())
        self.assertTrue(any("TDEA-" in r for r in responses))
