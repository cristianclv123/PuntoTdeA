from django.contrib.auth import authenticate
from django.test import TestCase
from django.urls import reverse

from tests.helpers import make_user


class NucleoAuthUnitTests(TestCase):
    def setUp(self):
        self.user = make_user("login_user", password="secret123")
        self.user.email = "login_user@tdea.edu.co"
        self.user.save(update_fields=["email"])

    def test_login_with_username(self):
        res = self.client.post(
            reverse("login"),
            {"username": "login_user", "password": "secret123"},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse("dashboard:index"))

    def test_login_with_email(self):
        res = self.client.post(
            reverse("login"),
            {"username": "login_user@tdea.edu.co", "password": "secret123"},
        )
        self.assertEqual(res.status_code, 302)

    def test_bad_password_does_not_authenticate(self):
        self.assertIsNone(authenticate(username="login_user", password="mala"))
        self.assertIsNotNone(authenticate(username="login_user", password="secret123"))

    def test_profile_requires_login(self):
        res = self.client.get(reverse("profile"))
        self.assertEqual(res.status_code, 302)
