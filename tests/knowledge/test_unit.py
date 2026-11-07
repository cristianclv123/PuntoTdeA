from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from knowledge.apps import _should_start_scheduler, run_inactivity_scheduler
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


class CloseInactiveChatsCommandTests(TestCase):
    @patch("knowledge.management.commands.close_inactive_chats.process_inactivity")
    def test_runs_once_by_default(self, process_inactivity):
        process_inactivity.return_value = {"warned": 2, "closed": 1}
        out = StringIO()

        call_command("close_inactive_chats", stdout=out)

        process_inactivity.assert_called_once_with()
        self.assertIn("Avisos de inactividad enviados: 2", out.getvalue())
        self.assertIn("Conversaciones cerradas por inactividad: 1", out.getvalue())

    @patch("knowledge.management.commands.close_inactive_chats.process_inactivity")
    def test_once_wins_over_interval(self, process_inactivity):
        process_inactivity.return_value = {"warned": 0, "closed": 0}

        with patch(
            "knowledge.management.commands.close_inactive_chats.time.sleep"
        ) as sleep:
            call_command(
                "close_inactive_chats",
                interval=60,
                once=True,
                stdout=StringIO(),
            )

        process_inactivity.assert_called_once_with()
        sleep.assert_not_called()

    @patch("knowledge.management.commands.close_inactive_chats.time.sleep")
    @patch("knowledge.management.commands.close_inactive_chats.process_inactivity")
    def test_interval_repeats_until_interrupted(self, process_inactivity, sleep):
        process_inactivity.return_value = {"warned": 0, "closed": 0}
        sleep.side_effect = [None, KeyboardInterrupt]

        call_command("close_inactive_chats", interval=60, stdout=StringIO())

        self.assertEqual(process_inactivity.call_count, 2)
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(60)

    def test_rejects_non_positive_interval(self):
        with self.assertRaises(CommandError):
            call_command("close_inactive_chats", interval=0)


class InactivitySchedulerTests(TestCase):
    @override_settings(ENABLE_INACTIVITY_SCHEDULER=False)
    def test_disabled_by_default(self):
        with patch("sys.argv", ["daphne", "-b", "0.0.0.0"]):
            self.assertFalse(_should_start_scheduler())

    @override_settings(ENABLE_INACTIVITY_SCHEDULER=True)
    def test_enabled_for_daphne(self):
        with patch("sys.argv", ["daphne", "-b", "0.0.0.0"]):
            self.assertTrue(_should_start_scheduler())

    @override_settings(ENABLE_INACTIVITY_SCHEDULER=True)
    def test_disabled_for_test_command(self):
        with patch("sys.argv", ["manage.py", "test"]):
            self.assertFalse(_should_start_scheduler())

    @patch("knowledge.apps.time.sleep")
    @patch("knowledge.chatbot.whatsapp.process_inactivity")
    def test_runs_cycle_and_sleeps(self, process_inactivity, sleep):
        process_inactivity.return_value = {"warned": 1, "closed": 0}

        run_inactivity_scheduler(interval=60, max_iterations=2)

        self.assertEqual(process_inactivity.call_count, 2)
        self.assertEqual(sleep.call_count, 1)
        sleep.assert_called_once_with(60)

    @patch("knowledge.apps.time.sleep")
    @patch(
        "knowledge.chatbot.whatsapp.process_inactivity",
        side_effect=RuntimeError("boom"),
    )
    def test_survives_errors(self, process_inactivity, sleep):
        with self.assertLogs("knowledge.apps", level="ERROR"):
            run_inactivity_scheduler(interval=0, max_iterations=1)

        self.assertEqual(process_inactivity.call_count, 1)
        sleep.assert_not_called()
