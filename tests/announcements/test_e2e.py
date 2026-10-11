from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from announcements.models import Announcement


class AnnouncementsE2ETests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(username="av_e2e", password="secret123")
        self.client.login(username="av_e2e", password="secret123")

    def test_crear_aviso_por_post_y_queda_persistido(self):
        res = self.client.post(
            reverse("announcements:index"),
            {
                "action": "create",
                "title": "Grado 2026",
                "body": "Inscripciones abiertas",
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Announcement.objects.filter(title="Grado 2026").exists())
