from django.test import TestCase

from .services.rag_service import answer_query


class KnowledgeRagTests(TestCase):
    def test_plural_query_matches_singular_answer(self):
        self.assertGreater(answer_query('matriculas 2026')['confidence'], 0.0)
