"""Pruebas del servicio de anuncios en WhatsApp Status (Marketing API)."""

import hashlib
import json
from unittest.mock import Mock, patch

import requests
from django.test import TestCase, override_settings

from communications.models import AudienceSegment, Contact, SegmentMembership
from communications.services import ads_service

ADS_SETTINGS = dict(
    META_GRAPH_API_URL="https://graph.facebook.com",
    WHATSAPP_API_VERSION="v21.0",
    META_ADS_ACCESS_TOKEN="ads-token",
    META_AD_ACCOUNT_ID="act_1607889164123842",
    META_FB_PAGE_ID="1382768948252522",
    META_WHATSAPP_PHONE="+57 333 2664480",
    META_REQUEST_TIMEOUT=5,
)


def _ok_response(body):
    response = Mock()
    response.json.return_value = body
    response.raise_for_status.return_value = None
    return response


@override_settings(**ADS_SETTINGS)
class AdsServiceHelpersTests(TestCase):
    def test_normalize_phone_strips_everything_but_digits(self):
        self.assertEqual(ads_service.normalize_phone("+57 333 266-4480"), "573332664480")
        self.assertEqual(ads_service.normalize_phone(""), "")

    def test_hash_phone_is_sha256_of_normalized_number(self):
        expected = hashlib.sha256(b"573332664480").hexdigest()
        self.assertEqual(ads_service.hash_phone("+57 333 266 4480"), expected)

    def test_build_targeting_uses_whatsapp_status_placement(self):
        targeting = ads_service.build_targeting()
        self.assertEqual(targeting["publisher_platforms"], ["instagram", "whatsapp"])
        self.assertEqual(targeting["instagram_positions"], ["story"])
        self.assertEqual(targeting["whatsapp_positions"], ["status"])
        self.assertFalse(targeting["user_age_unknown"])
        self.assertEqual(targeting["geo_locations"], {"countries": ["CO"]})
        self.assertNotIn("custom_audiences", targeting)

    def test_build_targeting_with_audience_and_advantage_flag(self):
        targeting = ads_service.build_targeting(
            custom_audiences=["777"], advantage_audience=True
        )
        self.assertEqual(targeting["custom_audiences"], [{"id": "777"}])
        self.assertEqual(targeting["targeting_automation"], {"advantage_audience": 1})

        restricted = ads_service.build_targeting(custom_audiences=["777"])
        self.assertEqual(restricted["targeting_automation"], {"advantage_audience": 0})

    def test_configuration_errors_reports_missing_settings(self):
        with override_settings(META_FB_PAGE_ID=""):
            self.assertIn("META_FB_PAGE_ID", ads_service.configuration_errors())

    def test_phones_from_segment_only_subscribed(self):
        segment = AudienceSegment.objects.create(name="Aspirantes")
        for name, phone, opt_in in [
            ("Ana", "+573001112233", Contact.OptInStatus.SUSCRITO),
            ("Beto", "+573004445566", Contact.OptInStatus.BAJA),
            ("Caro", "+573007778899", Contact.OptInStatus.SUSCRITO),
        ]:
            contact = Contact.objects.create(
                full_name=name, document_number=name, phone=phone, whatsapp_opt_in=opt_in
            )
            SegmentMembership.objects.create(segment=segment, contact=contact)

        self.assertEqual(
            ads_service.phones_from_segment(segment),
            ["573001112233", "573007778899"],
        )


@override_settings(**ADS_SETTINGS)
class AdsServiceApiTests(TestCase):
    @patch("communications.services.ads_service.requests.request")
    def test_create_campaign_posts_expected_payload(self, request):
        request.return_value = _ok_response({"id": "555"})

        result = ads_service.create_campaign("Aviso", status="PAUSED")

        self.assertTrue(result.ok)
        self.assertEqual(result.object_id, "555")
        request.assert_called_once()
        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/act_1607889164123842/campaigns"))
        self.assertEqual(kwargs["params"]["access_token"], "ads-token")
        self.assertEqual(kwargs["data"]["objective"], "OUTCOME_ENGAGEMENT")
        self.assertEqual(kwargs["data"]["status"], "PAUSED")
        self.assertEqual(kwargs["data"]["is_adset_budget_sharing_enabled"], "false")

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_set_builds_whatsapp_status_targeting(self, request):
        request.return_value = _ok_response({"id": "666"})

        result = ads_service.create_status_ad_set(
            "555",
            name="Aviso - Ad set",
            daily_budget=2000000,
            custom_audiences=["777"],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.object_id, "666")
        _args, kwargs = request.call_args
        self.assertTrue(_args[1].endswith("/act_1607889164123842/adsets"))
        data = kwargs["data"]
        self.assertEqual(data["optimization_goal"], "CONVERSATIONS")
        self.assertEqual(data["destination_type"], "WHATSAPP")
        self.assertEqual(data["bid_strategy"], "LOWEST_COST_WITHOUT_CAP")
        self.assertEqual(data["daily_budget"], 2000000)
        promoted = json.loads(data["promoted_object"])
        self.assertEqual(promoted["page_id"], "1382768948252522")
        self.assertEqual(promoted["whatsapp_phone_number"], "573332664480")
        targeting = json.loads(data["targeting"])
        self.assertEqual(targeting["whatsapp_positions"], ["status"])
        self.assertEqual(targeting["custom_audiences"], [{"id": "777"}])

    @patch("communications.services.ads_service.requests.request")
    def test_add_phones_to_audience_sends_hashed_payload(self, request):
        request.return_value = _ok_response({})

        result = ads_service.add_phones_to_audience("777", ["+573001112233", "573004445566"])

        self.assertTrue(result.ok)
        self.assertEqual(result.data["added"], 2)
        _args, kwargs = request.call_args
        self.assertTrue(_args[1].endswith("/777/users"))
        payload = json.loads(kwargs["data"]["payload"])
        self.assertEqual(payload["schema"], ["PHONE"])
        self.assertEqual(
            payload["data"],
            [
                [hashlib.sha256(b"573001112233").hexdigest()],
                [hashlib.sha256(b"573004445566").hexdigest()],
            ],
        )

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_stops_on_first_error_and_reports_trace(self, request):
        # La campana se crea bien; el ad set falla.
        def side_effect(method, url, **kwargs):
            if url.endswith("/campaigns"):
                return _ok_response({"id": "555"})
            raise requests.RequestException("Pagina no vinculada")

        request.side_effect = side_effect

        result = ads_service.create_status_ad(
            name="Aviso", message="Hola", daily_budget=2000000
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.data.get("campaign_id"), "555")
        self.assertNotIn("ad_set_id", result.data)
        self.assertIn("Pagina no vinculada", result.error)
