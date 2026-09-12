from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from . import models as knowledge_models
from .services.rag_service import answer_query, search_knowledge


class KnowledgeModelsTest(TestCase):
    def setUp(self):
        self.category = getattr(knowledge_models.Category, 'objects').create(
            name='Académico',
            description='Temas relacionados con matrícula y calendario.',
        )
        self.intent = getattr(knowledge_models.Intent, 'objects').create(
            name='matricula',
            description='Consultas sobre matrículas y pago de semestre.',
            confidence_threshold=0.78,
        )

    def test_article_creation_and_str(self):
        article = getattr(knowledge_models.KnowledgeArticle, 'objects').create(
            title='Matrícula y pago de semestre',
            slug='matricula-pago-semestre',
            summary='Información de pago y matrículas.',
            content='Para matricularse se debe revisar el calendario académico y pagar la matrícula antes de la fecha límite.',
            category=self.category,
            intent=self.intent,
            published=True,
            embedding=[0.1, 0.2, 0.3],
        )

        self.assertEqual(str(article), 'Matrícula y pago de semestre')
        self.assertTrue(article.is_published)
        self.assertIn('matrícula', article.indexable_text.lower())

    def test_faq_creation(self):
        faq = getattr(knowledge_models.FAQ, 'objects').create(
            question='¿Cuándo es la fecha límite de matrícula?',
            answer='La fecha límite de matrícula se informa en el calendario académico.',
            category=self.category,
            intent=self.intent,
            is_active=True,
        )

        self.assertEqual(faq.category.name, 'Académico')
        self.assertTrue(faq.is_active)

    def test_answer_query_uses_published_knowledge(self):
        getattr(knowledge_models.KnowledgeArticle, 'objects').create(
            title='Matrícula y pago de semestre',
            summary='Consulta las fechas de matrícula y realiza el pago antes del límite.',
            content='El calendario académico contiene las fechas oficiales.',
            category=self.category,
            intent=self.intent,
            published=True,
            status='published',
        )

        response = answer_query('Cuando es la matricula')

        self.assertIn('fechas de matrícula', response['answer'])
        self.assertGreater(response['confidence'], 0)
        self.assertFalse(response['needs_human_attention'])
        self.assertEqual(response['sources'][0]['source_type'], 'article')

    def test_answer_query_escalates_unknown_question(self):
        response = answer_query('¿Cuál es el horario de la cafetería?')

        self.assertTrue(response['needs_human_attention'])
        self.assertEqual(response['sources'], [])
        self.assertEqual(search_knowledge(''), [])

    def test_faq_answer_has_priority_over_article(self):
        getattr(knowledge_models.KnowledgeArticle, 'objects').create(
            title='Matrícula y pago de semestre',
            summary='Respuesta general del artículo.',
            content='Información general sobre matrícula.',
            category=self.category,
            intent=self.intent,
            published=True,
            status='published',
        )
        getattr(knowledge_models.FAQ, 'objects').create(
            question='¿Cuándo es la matrícula?',
            answer='La FAQ indica la fecha oficial de matrícula.',
            category=self.category,
            intent=self.intent,
            is_active=True,
        )

        response = answer_query('¿Cuándo es la matrícula?')

        self.assertEqual(response['answer'], 'La FAQ indica la fecha oficial de matrícula.')
        self.assertEqual(response['sources'][0]['source_type'], 'faq')

    def test_expired_faq_is_not_used(self):
        getattr(knowledge_models.FAQ, 'objects').create(
            question='¿Cuándo es la matrícula?',
            answer='Esta respuesta ya venció.',
            category=self.category,
            intent=self.intent,
            is_active=True,
            valid_until=timezone.now() - timedelta(days=1),
        )

        response = answer_query('¿Cuándo es la matrícula?')

        self.assertNotEqual(response['answer'], 'Esta respuesta ya venció.')


class KnowledgeViewsTest(TestCase):
    def test_knowledge_page_and_ask_endpoint(self):
        client = Client()
        page = client.get('/knowledge/')
        response = client.get('/knowledge/ask/?q=matricula')

        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Asistente de conocimiento institucional')
        self.assertEqual(response.status_code, 200)
        self.assertIn('answer', response.json())
