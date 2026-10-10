from django.test import TestCase
from django.urls import reverse

from dashboard.views import _case_metrics
from tests.helpers import make_conversation, make_user


class DashboardUnitTests(TestCase):
    def test_requires_login(self):
        res = self.client.get(reverse("dashboard:index"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login/", res.url)

    def test_metrics_count_open_whatsapp_cases(self):
        make_user("dash_user")
        make_conversation(document="DOC-DASH-1")
        labels = {row["label"]: row["value"] for row in _case_metrics()}
        self.assertGreaterEqual(int(labels["Casos abiertos"]), 1)
