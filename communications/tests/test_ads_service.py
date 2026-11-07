"""Pruebas del servicio de anuncios en WhatsApp Status (Marketing API)."""

import hashlib
import json
from unittest.mock import Mock, patch

import requests
from django.core.files.base import ContentFile
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
    def test_get_page_keeps_get_method_and_query_authentication(self, request):
        request.return_value = _ok_response({"id": "page-1", "name": "Página"})

        result = ads_service.get_page()

        self.assertTrue(result.ok)
        args, kwargs = request.call_args
        self.assertEqual(args[0], "GET")
        self.assertTrue(args[1].endswith("/1382768948252522"))
        self.assertEqual(kwargs["params"]["access_token"], "ads-token")
        self.assertEqual(kwargs["params"]["fields"], "id,name,is_published")

    @patch("communications.services.ads_service.requests.request")
    @override_settings(META_APP_ID="fake-app-id", META_APP_SECRET="fake-app-secret")
    def test_debug_token_keeps_query_authentication(self, request):
        request.return_value = _ok_response({"data": {"is_valid": True, "scopes": ["ads_management"]}})

        result = ads_service.debug_token()

        self.assertTrue(result.ok)
        _args, kwargs = request.call_args
        self.assertEqual(kwargs["params"]["access_token"], "fake-app-id|fake-app-secret")
        self.assertEqual(kwargs["params"]["input_token"], "ads-token")

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
    def test_delete_object_calls_delete_and_reports_success(self, request):
        request.return_value = _ok_response({"success": True})

        result = ads_service.delete_object("52600610368322")

        self.assertTrue(result.ok)
        args, kwargs = request.call_args
        self.assertEqual(args[0], "DELETE")
        self.assertTrue(args[1].endswith("/52600610368322"))
        self.assertEqual(kwargs["params"]["access_token"], "ads-token")

    @patch("communications.services.ads_service.requests.request")
    def test_delete_object_without_id_never_calls_meta(self, request):
        result = ads_service.delete_object("")

        self.assertFalse(result.ok)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_upload_ad_image_keeps_extension_though_label_has_none(self, request):
        # create_status_ad pasa el nombre del anuncio como `name`; el nombre de
        # archivo debe salir del propio archivo (Meta rechaza nombres sin
        # extension con code 100, subcode 1487411).
        request.return_value = _ok_response({"images": {"aviso.jpg": {"hash": "abc"}}})
        image = ContentFile(b"fake-jpeg", name="aviso.jpg")

        result = ads_service.upload_ad_image(image, name="Aviso: promo de matricula")

        self.assertTrue(result.ok)
        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/act_1607889164123842/adimages"))
        self.assertEqual(kwargs["params"]["access_token"], "ads-token")
        filename, _file, mime = kwargs["files"]["filename"]
        self.assertEqual(filename, "aviso.jpg")
        self.assertEqual(mime, "image/jpeg")

    @patch("communications.services.ads_service.requests.request")
    def test_upload_ad_image_adds_extension_when_missing(self, request):
        request.return_value = _ok_response({"images": {"foto.png": {"hash": "abc"}}})
        image = ContentFile(b"fake-png", name="foto")
        image.content_type = "image/png"

        result = ads_service.upload_ad_image(image)

        self.assertTrue(result.ok)
        _args, kwargs = request.call_args
        filename, _file, mime = kwargs["files"]["filename"]
        self.assertEqual(filename, "foto.png")
        self.assertEqual(mime, "image/png")

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
        self.assertIn("error de comunicación", result.error)
        self.assertNotIn("Pagina no vinculada", result.error)

    @override_settings(
        META_ACCESS_TOKEN="fake-meta-access-token",
        META_ADS_ACCESS_TOKEN="fake-ads-access-token",
        META_APP_SECRET="fake-app-secret",
        META_VERIFY_TOKEN="fake-verify-token",
    )
    def test_request_exceptions_never_return_sensitive_urls_or_credentials(self):
        sensitive_url = (
            "https://graph.facebook.com/v21.0/act_1/campaigns?"
            "access_token=fake-ads-access-token&app_secret=fake-app-secret"
        )
        cases = [
            (requests.ConnectionError, "Error de conexión"),
            (requests.Timeout, "Tiempo de espera agotado"),
            (requests.HTTPError, "error HTTP"),
            (RuntimeError, "error inesperado"),
        ]
        secrets = (
            "fake-meta-access-token",
            "fake-ads-access-token",
            "fake-app-secret",
            "fake-verify-token",
        )

        for exception_type, expected_category in cases:
            with self.subTest(exception_type=exception_type.__name__):
                with patch(
                    "communications.services.ads_service.requests.request",
                    side_effect=exception_type(f"falló {sensitive_url}"),
                ):
                    result = ads_service.create_campaign("Aviso")

                self.assertFalse(result.ok)
                self.assertIn(expected_category, result.error)
                self.assertNotIn("graph.facebook.com", result.error)
                for secret in secrets:
                    self.assertNotIn(secret, result.error)

    @override_settings(
        META_ACCESS_TOKEN="fake-meta-access-token",
        META_ADS_ACCESS_TOKEN="fake-ads-access-token",
        META_APP_SECRET="fake-app-secret",
        META_VERIFY_TOKEN="fake-verify-token",
    )
    @patch("communications.services.ads_service.requests.request")
    def test_meta_json_error_keeps_safe_codes_but_not_untrusted_message(self, request):
        response = Mock()
        response.status_code = 400
        response.json.return_value = {
            "error": {
                "message": "Token fake-ads-access-token rechazado",
                "type": "OAuthException",
                "code": 190,
                "error_subcode": 463,
                "fbtrace_id": "AbC-123_trace",
            }
        }
        response.raise_for_status.side_effect = requests.HTTPError(
            "HTTP 400 https://graph.facebook.com/?access_token=fake-ads-access-token"
        )
        request.return_value = response

        result = ads_service.create_campaign("Aviso")

        self.assertFalse(result.ok)
        self.assertIn("código 190", result.error)
        self.assertIn("subcódigo 463", result.error)
        self.assertIn("tipo OAuthException", result.error)
        self.assertIn("seguimiento AbC-123_trace", result.error)
        self.assertNotIn("graph.facebook.com", result.error)
        for secret in (
            "fake-meta-access-token",
            "fake-ads-access-token",
            "fake-app-secret",
            "fake-verify-token",
        ):
            self.assertNotIn(secret, result.error)

    @override_settings(
        META_ACCESS_TOKEN="fake-meta-access-token",
        META_ADS_ACCESS_TOKEN="fake-ads-access-token",
        META_APP_SECRET="fake-app-secret",
        META_VERIFY_TOKEN="fake-verify-token",
    )
    @patch("communications.services.ads_service.requests.request")
    def test_non_json_http_error_does_not_return_body_or_url(self, request):
        response = Mock()
        response.status_code = 502
        response.json.side_effect = ValueError("invalid json")
        response.text = "https://graph.facebook.com/?access_token=fake-ads-access-token"
        response.raise_for_status.side_effect = requests.HTTPError(
            "HTTP 502 https://graph.facebook.com/?access_token=fake-ads-access-token"
        )
        request.return_value = response

        result = ads_service.create_campaign("Aviso")

        self.assertFalse(result.ok)
        self.assertIn("HTTP 502", result.error)
        self.assertNotIn("graph.facebook.com", result.error)
        self.assertNotIn("access_token", result.error)
        for secret in (
            "fake-meta-access-token",
            "fake-ads-access-token",
            "fake-app-secret",
            "fake-verify-token",
        ):
            self.assertNotIn(secret, result.error)
