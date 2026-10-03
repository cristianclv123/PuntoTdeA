"""Pruebas del modulo de Avisos y su publicacion en WhatsApp Status."""

import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from communications.models import AudienceSegment, Contact, SegmentMembership
from communications.services.ads_service import AdsResult

from .models import Announcement, StatusAd


def _image(name="aviso.png"):
    return SimpleUploadedFile(name, b"fake-image-bytes", content_type="image/png")


def _ok_status_ad_result():
    return AdsResult(
        True,
        "Anuncio de WhatsApp Status creado en PAUSED.",
        {
            "campaign_id": "cmp-1",
            "ad_set_id": "set-1",
            "creative_id": "cre-1",
            "ad_id": "ad-1",
        },
    )


class AnnouncementViewsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="tester", password="clave-segura"
        )
        self.client.force_login(user)

        self._media = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.addCleanup(self._override.disable)
        self.addCleanup(shutil.rmtree, self._media, True)

    def _segment_with_contact(self):
        segment = AudienceSegment.objects.create(name="Aspirantes")
        contact = Contact.objects.create(
            full_name="Ana",
            document_number="123",
            phone="+573001112233",
            whatsapp_opt_in=Contact.OptInStatus.SUSCRITO,
        )
        SegmentMembership.objects.create(segment=segment, contact=contact)
        return segment

    def test_page_lists_segments_and_two_buttons(self):
        self._segment_with_contact()
        Announcement.objects.create(title="Aviso sin status", content="Cuerpo")

        response = self.client.get(reverse("announcements:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aspirantes")
        self.assertContains(response, 'value="create"')
        self.assertContains(response, 'value="publish_status_create"')
        self.assertContains(response, "Sin publicar")

    def test_create_button_only_saves(self):
        response = self.client.post(
            reverse("announcements:index"),
            {
                "action": "create",
                "title": "Suspension",
                "body": "Sin clases",
                "type": "urgente",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Announcement.objects.count(), 1)
        self.assertEqual(StatusAd.objects.count(), 0)

    def test_publish_button_saves_and_creates_paused_status_ad(self):
        segment = self._segment_with_contact()

        with patch(
            "announcements.status_ad_service.ads_service.create_custom_audience"
        ) as create_audience, patch(
            "announcements.status_ad_service.ads_service.add_phones_to_audience"
        ) as add_phones, patch(
            "announcements.status_ad_service.ads_service.create_status_ad"
        ) as create_ad:
            create_audience.return_value = AdsResult(True, "ok", {"id": "aud-1"})
            add_phones.return_value = AdsResult(True, "ok", {"added": 1})
            create_ad.return_value = _ok_status_ad_result()

            response = self.client.post(
                reverse("announcements:index"),
                {
                    "action": "publish_status_create",
                    "title": "Matriculas",
                    "body": "Inscripciones abiertas",
                    "type": "informativo",
                    "image": _image(),
                    "audience": [str(segment.id)],
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Announcement.objects.count(), 1)
        status_ad = StatusAd.objects.get()
        self.assertEqual(status_ad.state, StatusAd.State.PAUSED)
        self.assertEqual(status_ad.ad_id, "ad-1")
        self.assertEqual(status_ad.campaign_id, "cmp-1")
        self.assertEqual(status_ad.audience_ids, ["aud-1"])
        self.assertEqual(status_ad.segment_ids, [segment.id])

        create_audience.assert_called_once()
        add_phones.assert_called_once()
        _args, kwargs = create_ad.call_args
        self.assertEqual(kwargs["custom_audiences"], ["aud-1"])
        self.assertEqual(kwargs["status"], "PAUSED")

    def test_publish_button_without_image_warns_and_does_not_call_meta(self):
        with patch(
            "announcements.status_ad_service.ads_service.create_status_ad"
        ) as create_ad:
            response = self.client.post(
                reverse("announcements:index"),
                {
                    "action": "publish_status_create",
                    "title": "Sin imagen",
                    "body": "Cuerpo",
                    "type": "informativo",
                },
            )

        self.assertEqual(Announcement.objects.count(), 1)
        self.assertEqual(StatusAd.objects.count(), 0)
        create_ad.assert_not_called()
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("falta la imagen" in m.lower() for m in messages))

    def test_meta_error_is_recorded_on_status_ad(self):
        segment = self._segment_with_contact()

        with patch(
            "announcements.status_ad_service.ads_service.create_custom_audience"
        ) as create_audience, patch(
            "announcements.status_ad_service.ads_service.add_phones_to_audience"
        ), patch(
            "announcements.status_ad_service.ads_service.create_status_ad"
        ) as create_ad:
            create_audience.return_value = AdsResult(True, "ok", {"id": "aud-1"})
            create_ad.return_value = AdsResult(
                False,
                "No se pudo crear el creativo.",
                {"campaign_id": "cmp-1", "ad_set_id": "set-1"},
                "Meta Marketing API: app en modo desarrollo",
            )

            self.client.post(
                reverse("announcements:index"),
                {
                    "action": "publish_status_create",
                    "title": "Falla",
                    "body": "Cuerpo",
                    "type": "informativo",
                    "image": _image(),
                    "audience": [str(segment.id)],
                },
            )

        status_ad = StatusAd.objects.get()
        self.assertEqual(status_ad.state, StatusAd.State.ERROR)
        self.assertIn("modo desarrollo", status_ad.error)
        self.assertEqual(status_ad.campaign_id, "cmp-1")
        self.assertEqual(status_ad.ad_set_id, "set-1")
        self.assertEqual(status_ad.segment_ids, [segment.id])

    def test_card_retry_reuses_last_audience_and_segments(self):
        segment = self._segment_with_contact()
        announcement = Announcement.objects.create(
            title="Ya existe", content="Cuerpo", image=_image()
        )
        StatusAd.objects.create(
            announcement=announcement,
            audience_ids=["aud-1"],
            segment_ids=[segment.id],
            state=StatusAd.State.ERROR,
            error="app en modo desarrollo",
        )

        with patch(
            "announcements.status_ad_service.ads_service.create_custom_audience"
        ) as create_audience, patch(
            "announcements.status_ad_service.ads_service.add_phones_to_audience"
        ) as add_phones, patch(
            "announcements.status_ad_service.ads_service.create_status_ad"
        ) as create_ad:
            create_ad.return_value = _ok_status_ad_result()
            response = self.client.post(
                reverse("announcements:index"),
                {"action": "publish_status", "notice_id": announcement.id},
            )

        self.assertEqual(response.status_code, 302)
        create_audience.assert_not_called()
        add_phones.assert_not_called()
        _args, kwargs = create_ad.call_args
        self.assertEqual(kwargs["custom_audiences"], ["aud-1"])
        status_ad = StatusAd.objects.first()
        self.assertEqual(status_ad.state, StatusAd.State.PAUSED)
        self.assertEqual(status_ad.segment_ids, [segment.id])

    def test_card_retry_without_image_is_rejected(self):
        announcement = Announcement.objects.create(title="Sin foto", content="Cuerpo")

        response = self.client.post(
            reverse("announcements:index"),
            {"action": "publish_status", "notice_id": announcement.id},
        )

        self.assertEqual(StatusAd.objects.count(), 0)
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("no tiene imagen" in m.lower() for m in messages))

    def test_delete_is_blocked_when_published(self):
        announcement = Announcement.objects.create(title="Publicado", content="Cuerpo")
        StatusAd.objects.create(
            announcement=announcement, state=StatusAd.State.PAUSED
        )

        response = self.client.post(
            reverse("announcements:index"),
            {"action": "delete", "notice_id": announcement.id},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Announcement.objects.filter(pk=announcement.id).exists())
        messages = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("no se puede eliminar" in m.lower() for m in messages))

    def test_delete_allowed_when_only_error(self):
        announcement = Announcement.objects.create(title="Con error", content="Cuerpo")
        StatusAd.objects.create(
            announcement=announcement, state=StatusAd.State.ERROR, error="x"
        )

        self.client.post(
            reverse("announcements:index"),
            {"action": "delete", "notice_id": announcement.id},
        )

        self.assertFalse(Announcement.objects.filter(pk=announcement.id).exists())

    def test_published_card_hides_retry_and_delete(self):
        announcement = Announcement.objects.create(title="Publicado", content="Cuerpo")
        StatusAd.objects.create(
            announcement=announcement, state=StatusAd.State.PAUSED
        )

        response = self.client.get(reverse("announcements:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Publicado en WhatsApp")
        self.assertNotContains(response, 'value="publish_status"')
        self.assertNotContains(response, 'value="delete"')

    def test_unpublished_card_shows_publish_and_delete(self):
        Announcement.objects.create(title="Sin publicar", content="Cuerpo")

        response = self.client.get(reverse("announcements:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Publicar en estado WhatsApp")
        self.assertContains(response, 'value="publish_status"')
        self.assertContains(response, 'value="delete"')
