from django.test import RequestFactory, TestCase
from django.urls import reverse

from cases.views import _bandeja_list_context
from tests.helpers import make_conversation, make_user


class NucleoE2ETests(TestCase):
    def test_login_abre_bandeja_con_ticket_whatsapp(self):
        user = make_user("flow_user", first_name="Juan")
        conv = make_conversation(document="DOC-FLOW-1")

        login = self.client.post(
            reverse("login"),
            {"username": "flow_user", "password": "secret123"},
        )
        self.assertEqual(login.status_code, 302)
        self.assertEqual(login.url, reverse("dashboard:index"))

        request = RequestFactory().get(reverse("cases:bandeja"))
        request.user = user
        ids = {row["id"] for row in _bandeja_list_context(request)["conversations"]}
        self.assertIn(conv.id, ids)
