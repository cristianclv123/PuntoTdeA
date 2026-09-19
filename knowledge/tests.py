from datetime import datetime, time, timezone as datetime_timezone

from django.test import TestCase

<<<<<<< Updated upstream
# Create your tests here.
=======
from .chatbot.schedule import BusinessSchedule
from .chatbot.workflow import ChatbotWorkflow
from .models import Category, ChatConversation, KnowledgeArticle
from .services.rag_service import answer_query, search_knowledge


def _manager(model):
    return getattr(model, 'objects')


class KnowledgeRagTests(TestCase):
    def setUp(self):
        category = _manager(Category).create(name='Matrículas')
        _manager(KnowledgeArticle).create(
            title='Matrícula 2026',
            summary='Información sobre las matrículas de 2026.',
            content='Consulta las fechas y requisitos de matrícula.',
            category=category,
            status='published',
            published=True,
        )
        _manager(KnowledgeArticle).create(
            title='Pago de matrícula en línea',
            summary='Puedes pagar la matrícula por los canales virtuales habilitados.',
            content='Consulta el botón de pagos institucional y descarga el comprobante.',
            category=category,
            tags=['pagar', 'pago', 'canales virtuales'],
            status='published',
            published=True,
        )

    def test_plural_query_matches_singular_answer(self):
        self.assertGreater(answer_query('matriculas 2026')['confidence'], 0.0)

    def test_keywords_match_a_differently_worded_question(self):
        results = search_knowledge('¿Cómo puedo pagar la matrícula?', limit=1)
        self.assertEqual(results[0]['title'], 'Pago de matrícula en línea')
        self.assertIn('canales virtuales', answer_query('¿Cómo puedo pagar la matrícula?')['answer'])


class ChatbotWorkflowTests(TestCase):
    def setUp(self):
        self.conversation = _manager(ChatConversation).create()
        self.workflow = ChatbotWorkflow(
            self.conversation,
            responder=lambda question: {
                'answer': f'Respuesta para: {question}',
                'confidence': 1.0,
                'needs_human_attention': False,
                'sources': [],
            },
            schedule=BusinessSchedule(
                weekdays=frozenset({0, 1, 2, 3, 4}),
                opening_time=time(8),
                closing_time=time(17),
            ),
        )

    def test_valid_question_can_end_chat(self):
        self.assertEqual(self.workflow.start()['state'], 'waiting_question')
        response = self.workflow.submit_question('¿Cuándo son las matrículas?')
        self.assertEqual(response['state'], 'waiting_confirmation')
        self.assertEqual(self.workflow.confirm_more_help(False)['state'], 'ended')
        self.assertEqual(self.conversation.refresh_from_db(), None)
        self.assertEqual(self.conversation.status, ChatConversation.STATUS_ENDED)

    def test_invalid_question_is_rejected_until_valid(self):
        invalid = self.workflow.submit_question('??')
        self.assertFalse(invalid['valid'])
        self.assertEqual(invalid['state'], 'waiting_question')
        self.assertTrue(self.workflow.submit_question('Necesito ayuda').get('valid'))

    def test_user_can_request_more_help(self):
        self.workflow.submit_question('¿Dónde consulto mi horario?')
        self.assertEqual(self.workflow.confirm_more_help(True)['state'], 'help_options')

    def test_advisor_request_during_business_hours_is_pending(self):
        self.workflow.submit_question('No puedo resolver mi caso')
        self.workflow.escalate('La respuesta requiere revisión humana')
        result = self.workflow.submit_advisor_question(
            'Necesito que revisen mi caso', datetime(2026, 9, 18, 15, 0, tzinfo=datetime_timezone.utc)
        )
        self.assertTrue(result['within_business_hours'])
        self.assertEqual(self.conversation.status, ChatConversation.STATUS_PENDING)
        self.assertEqual(self.conversation.advisor_question, 'Necesito que revisen mi caso')

    def test_advisor_request_outside_business_hours_is_pending(self):
        self.workflow.escalate('No hay respuesta disponible')
        result = self.workflow.submit_advisor_question(
            'Quiero hablar con un asesor', datetime(2026, 9, 19, 20, 0, tzinfo=datetime_timezone.utc)
        )
        self.assertFalse(result['within_business_hours'])
        self.assertIn('fuera del horario', result['message'])
>>>>>>> Stashed changes
