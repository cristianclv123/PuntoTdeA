from django.test import TestCase

from knowledge.models import Category, FAQ, Intent, KnowledgeArticle


class KnowledgeModelsTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Académico',
            description='Temas relacionados con matrícula y calendario.',
        )
        self.intent = Intent.objects.create(
            name='matricula',
            description='Consultas sobre matrículas y pago de semestre.',
            confidence_threshold=0.78,
        )

    def test_article_creation_and_str(self):
        article = KnowledgeArticle.objects.create(
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
        faq = FAQ.objects.create(
            question='¿Cuándo es la fecha límite de matrícula?',
            answer='La fecha límite de matrícula se informa en el calendario académico.',
            category=self.category,
            intent=self.intent,
            is_active=True,
        )

        self.assertEqual(faq.category.name, 'Académico')
        self.assertTrue(faq.is_active)
