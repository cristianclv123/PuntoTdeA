from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from announcements.models import Announcement, StatusAd


class AnnouncementsUnitTests(TestCase):
    def test_index_requires_login(self):
        res = self.client.get(reverse("announcements:index"))
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login/", res.url)

    def test_status_ad_default_is_draft_or_paused_semantics(self):
        user = get_user_model().objects.create_user(username="av", password="secret123")
        self.client.login(username="av", password="secret123")
        aviso = Announcement.objects.create(title="Cierre de caja", content="Aviso de prueba")
        self.assertFalse(aviso.is_published_in_status)
        StatusAd.objects.create(announcement=aviso, state=StatusAd.State.PAUSED)
        aviso.refresh_from_db()
        self.assertTrue(aviso.is_published_in_status)
        self.assertTrue(user.is_authenticated)
