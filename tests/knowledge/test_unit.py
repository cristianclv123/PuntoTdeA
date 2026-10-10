from django.test import TestCase

from knowledge.models import Category, KnowledgeArticle
from knowledge.services.rag_service import answer_query, search_knowledge


class KnowledgeRagUnitTests(TestCase):
    def setUp(self):
        cat = Category.objects.create(name="Calendario")
        KnowledgeArticle.objects.create(
            title="Fechas de matrícula",
            summary="Calendario de matrículas 2026.",
            content="Las matrículas inician en enero.",
            category=cat,
            status="published",
            published=True,
            tags=["matricula", "fechas"],
        )
        KnowledgeArticle.objects.create(
            title="Borrador interno",
            content="No debe indexarse.",
            category=cat,
            status="draft",
            published=False,
        )

    def test_published_article_is_searchable(self):
        results = search_knowledge("matrícula fechas", limit=5)
        titles = [r["title"] for r in results]
        self.assertIn("Fechas de matrícula", titles)
        self.assertNotIn("Borrador interno", titles)

    def test_answer_query_has_confidence(self):
        result = answer_query("¿Cuándo son las matrículas?")
        self.assertIn("answer", result)
        self.assertGreaterEqual(result["confidence"], 0.0)
