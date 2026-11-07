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


@override_settings(**ADS_SETTINGS)
class AdsServiceConfigurationTests(TestCase):
    def test_configuration_errors_lists_all_four_missing_variables(self):
        with override_settings(
            META_ADS_ACCESS_TOKEN="",
            META_AD_ACCOUNT_ID="",
            META_FB_PAGE_ID="",
            META_WHATSAPP_PHONE="",
        ):
            self.assertEqual(
                set(ads_service.configuration_errors()),
                {
                    "META_ADS_ACCESS_TOKEN",
                    "META_AD_ACCOUNT_ID",
                    "META_FB_PAGE_ID",
                    "META_WHATSAPP_PHONE",
                },
            )

    def test_configuration_errors_empty_when_everything_is_configured(self):
        self.assertEqual(ads_service.configuration_errors(), [])

    def test_configuration_errors_detects_whitespace_only_values(self):
        with override_settings(META_AD_ACCOUNT_ID="   ", META_WHATSAPP_PHONE=" - "):
            errors = ads_service.configuration_errors()
            self.assertIn("META_AD_ACCOUNT_ID", errors)
            self.assertIn("META_WHATSAPP_PHONE", errors)

    def test_ad_account_id_adds_act_prefix_to_numeric_id(self):
        with override_settings(META_AD_ACCOUNT_ID="1607889164123842"):
            self.assertEqual(ads_service.ad_account_id(), "act_1607889164123842")

    def test_ad_account_id_keeps_existing_prefix(self):
        self.assertEqual(ads_service.ad_account_id(), "act_1607889164123842")

    def test_ad_account_id_empty_stays_empty(self):
        with override_settings(META_AD_ACCOUNT_ID=""):
            self.assertEqual(ads_service.ad_account_id(), "")


class AdsServiceTargetingTests(TestCase):
    def test_build_targeting_with_age_range(self):
        targeting = ads_service.build_targeting(age_min=25, age_max=40)
        self.assertEqual(targeting["age_min"], 25)
        self.assertEqual(targeting["age_max"], 40)

    def test_build_targeting_defaults_missing_age_bounds(self):
        only_min = ads_service.build_targeting(age_min=25)
        self.assertEqual(only_min["age_min"], 25)
        self.assertEqual(only_min["age_max"], 65)

        only_max = ads_service.build_targeting(age_max=40)
        self.assertEqual(only_max["age_min"], 18)
        self.assertEqual(only_max["age_max"], 40)

    def test_build_targeting_with_genders(self):
        targeting = ads_service.build_targeting(genders=[1, 2])
        self.assertEqual(targeting["genders"], [1, 2])

    def test_build_targeting_without_age_or_genders_omits_keys(self):
        targeting = ads_service.build_targeting()
        self.assertNotIn("age_min", targeting)
        self.assertNotIn("age_max", targeting)
        self.assertNotIn("genders", targeting)


@override_settings(**ADS_SETTINGS)
class AdsServiceSegmentPhonesTests(TestCase):
    def _segment_with_contacts(self):
        segment = AudienceSegment.objects.create(name="Aspirantes")
        for name, phone, opt_in in [
            ("Ana", "+573001112233", Contact.OptInStatus.SUSCRITO),
            ("Beto", "+573004445566", Contact.OptInStatus.BAJA),
            ("Caro", "+573007778899", Contact.OptInStatus.NO_CONTACTADO),
        ]:
            contact = Contact.objects.create(
                full_name=name, document_number=name, phone=phone, whatsapp_opt_in=opt_in
            )
            SegmentMembership.objects.create(segment=segment, contact=contact)
        return segment

    def test_phones_from_segment_includes_every_contact_when_not_only_subscribed(self):
        segment = self._segment_with_contacts()

        self.assertEqual(
            ads_service.phones_from_segment(segment, only_subscribed=False),
            ["573001112233", "573004445566", "573007778899"],
        )

    def test_phones_from_segment_excludes_non_subscribed_by_default(self):
        segment = self._segment_with_contacts()

        self.assertEqual(
            ads_service.phones_from_segment(segment),
            ["573001112233"],
        )


class AdsServiceTransportTests(TestCase):
    def test_exception_category_maps_http_error_and_value_error(self):
        self.assertEqual(ads_service._exception_category(requests.HTTPError()), "error HTTP")
        self.assertEqual(ads_service._exception_category(ValueError()), "respuesta inválida")

    @patch("communications.services.ads_service.requests.request")
    def test_call_without_token_returns_error_and_does_not_call_meta(self, request):
        with override_settings(META_ADS_ACCESS_TOKEN=""):
            ok, body, error = ads_service._call("GET", "me")

        self.assertFalse(ok)
        self.assertEqual(body, {})
        self.assertIn("falta META_ADS_ACCESS_TOKEN", error)
        request.assert_not_called()


@override_settings(**ADS_SETTINGS)
class AdsServiceDebugTokenTests(TestCase):
    @patch("communications.services.ads_service.requests.request")
    def test_debug_token_requires_app_id_and_secret(self, request):
        with override_settings(META_APP_ID="", META_APP_SECRET=""):
            result = ads_service.debug_token()

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "configuracion")
        self.assertIn("META_APP_ID/META_APP_SECRET", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_debug_token_requires_both_app_credentials(self, request):
        with override_settings(META_APP_ID="fake-app-id", META_APP_SECRET=""):
            result = ads_service.debug_token()

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "configuracion")
        request.assert_not_called()


@override_settings(**ADS_SETTINGS, META_BUSINESS_ID="business-123")
class AdsServiceObjectTests(TestCase):
    @patch("communications.services.ads_service.requests.request")
    def test_get_ad_account_labels_known_status(self, request):
        request.return_value = _ok_response({
            "id": "act_1607889164123842",
            "name": "Cuenta",
            "account_status": 1,
            "currency": "COP",
            "timezone_name": "America/Bogota",
            "disable_reason": 0,
        })

        result = ads_service.get_ad_account()

        self.assertTrue(result.ok)
        self.assertEqual(result.data["account"]["account_status_label"], "ACTIVA")
        args, kwargs = request.call_args
        self.assertEqual(args[0], "GET")
        self.assertTrue(args[1].endswith("/act_1607889164123842"))
        self.assertEqual(
            kwargs["params"]["fields"],
            "id,name,account_status,currency,timezone_name,disable_reason",
        )

    @patch("communications.services.ads_service.requests.request")
    def test_get_ad_account_keeps_raw_value_for_unknown_status(self, request):
        request.return_value = _ok_response({"id": "act_1", "account_status": 42})

        result = ads_service.get_ad_account()

        self.assertTrue(result.ok)
        self.assertEqual(result.data["account"]["account_status_label"], "42")

    @patch("communications.services.ads_service.requests.request")
    def test_get_ad_account_reports_communication_error(self, request):
        request.side_effect = requests.ConnectionError("sin red")

        result = ads_service.get_ad_account()

        self.assertFalse(result.ok)
        self.assertIn("Error de conexión", result.error)

    @patch("communications.services.ads_service.requests.request")
    def test_get_business_reads_business(self, request):
        request.return_value = _ok_response({
            "id": "business-123",
            "name": "Negocio",
            "verification_status": "verified",
        })

        result = ads_service.get_business()

        self.assertTrue(result.ok)
        self.assertEqual(result.data["business"]["id"], "business-123")
        args, kwargs = request.call_args
        self.assertTrue(args[1].endswith("/business-123"))
        self.assertEqual(kwargs["params"]["fields"], "id,name,verification_status")

    @patch("communications.services.ads_service.requests.request")
    def test_get_business_requires_business_id(self, request):
        with override_settings(META_BUSINESS_ID=""):
            result = ads_service.get_business()

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "configuracion")
        self.assertIn("META_BUSINESS_ID", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_create_custom_audience_posts_payload(self, request):
        request.return_value = _ok_response({"id": "888"})

        result = ads_service.create_custom_audience(
            "Aspirantes", description="Segmento", retention_days=30
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.object_id, "888")
        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/act_1607889164123842/customaudiences"))
        self.assertEqual(kwargs["data"]["name"], "Aspirantes")
        self.assertEqual(kwargs["data"]["subtype"], "CUSTOM")
        self.assertEqual(kwargs["data"]["customer_file_source"], "USER_PROVIDED_ONLY")
        self.assertEqual(kwargs["data"]["description"], "Segmento")
        self.assertEqual(kwargs["data"]["retention_days"], 30)

    @patch("communications.services.ads_service.requests.request")
    def test_create_custom_audience_without_id_reports_error(self, request):
        request.return_value = _ok_response({})

        result = ads_service.create_custom_audience("Aspirantes")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sin id")

    @patch("communications.services.ads_service.requests.request")
    def test_create_custom_audience_reports_timeout(self, request):
        request.side_effect = requests.Timeout()

        result = ads_service.create_custom_audience("Aspirantes")

        self.assertFalse(result.ok)
        self.assertIn("Tiempo de espera agotado", result.error)

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_creative_posts_expected_payload(self, request):
        request.return_value = _ok_response({"id": "999"})

        result = ads_service.create_status_ad_creative(
            name="Creativo",
            message="Hola",
            image_hash="hash-1",
            title="Titulo",
            page_id_value="page-1",
            instagram_actor_id="actor-1",
            page_welcome_message="Bienvenido",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.object_id, "999")
        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/act_1607889164123842/adcreatives"))
        spec = json.loads(kwargs["data"]["object_story_spec"])
        self.assertEqual(spec["page_id"], "page-1")
        self.assertEqual(spec["instagram_actor_id"], "actor-1")
        link_data = spec["link_data"]
        self.assertEqual(link_data["image_hash"], "hash-1")
        self.assertEqual(link_data["message"], "Hola")
        self.assertEqual(link_data["name"], "Titulo")
        self.assertEqual(link_data["call_to_action"]["type"], "WHATSAPP_MESSAGE")
        self.assertEqual(
            link_data["call_to_action"]["value"], {"app_destination": "WHATSAPP"}
        )
        self.assertEqual(kwargs["data"]["page_welcome_message"], "Bienvenido")

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_creative_without_page_reports_config_error(self, request):
        with override_settings(META_FB_PAGE_ID=""):
            result = ads_service.create_status_ad_creative(name="Creativo", message="Hola")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "configuracion")
        self.assertIn("Pagina", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_creative_without_id_reports_error(self, request):
        request.return_value = _ok_response({})

        result = ads_service.create_status_ad_creative(name="Creativo", message="Hola")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sin id")

    @patch("communications.services.ads_service.requests.request")
    def test_create_ad_posts_expected_payload(self, request):
        request.return_value = _ok_response({"id": "111"})

        result = ads_service.create_ad(
            name="Anuncio", ad_set_id="666", creative_id="999", status="PAUSED"
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.object_id, "111")
        args, kwargs = request.call_args
        self.assertEqual(args[0], "POST")
        self.assertTrue(args[1].endswith("/act_1607889164123842/ads"))
        self.assertEqual(kwargs["data"]["name"], "Anuncio")
        self.assertEqual(kwargs["data"]["adset_id"], "666")
        self.assertEqual(json.loads(kwargs["data"]["creative"]), {"creative_id": "999"})
        self.assertEqual(kwargs["data"]["status"], "PAUSED")

    @patch("communications.services.ads_service.requests.request")
    def test_create_ad_without_id_reports_error(self, request):
        request.return_value = _ok_response({})

        result = ads_service.create_ad(name="Anuncio", ad_set_id="666", creative_id="999")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sin id")


@override_settings(**ADS_SETTINGS)
class AdsServiceAudienceBatchTests(TestCase):
    @patch("communications.services.ads_service.requests.request")
    def test_add_phones_to_audience_without_phones_reports_error(self, request):
        result = ads_service.add_phones_to_audience("777", [])

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sin datos")
        self.assertIn("No hay telefonos", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_add_phones_to_audience_ignores_blank_numbers(self, request):
        result = ads_service.add_phones_to_audience("777", ["", "   ", "+"])

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sin datos")
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_add_phones_to_audience_splits_batches_over_5000(self, request):
        request.return_value = _ok_response({})
        phones = [f"57300000{i:04d}" for i in range(5001)]

        result = ads_service.add_phones_to_audience("777", phones)

        self.assertTrue(result.ok)
        self.assertEqual(result.data["added"], 5001)
        self.assertEqual(request.call_count, 2)
        first_payload = json.loads(request.call_args_list[0].kwargs["data"]["payload"])
        second_payload = json.loads(request.call_args_list[1].kwargs["data"]["payload"])
        self.assertEqual(len(first_payload["data"]), 5000)
        self.assertEqual(len(second_payload["data"]), 1)

    @patch("communications.services.ads_service.requests.request")
    def test_add_phones_to_audience_stops_on_batch_failure(self, request):
        calls = {"count": 0}

        def side_effect(method, url, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return _ok_response({})
            raise requests.HTTPError("HTTP 400")

        request.side_effect = side_effect

        result = ads_service.add_phones_to_audience(
            "777",
            ["573001112233", "573004445566", "573007778899"],
            batch_size=2,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.data["added"], 2)
        self.assertEqual(result.data["id"], "777")
        self.assertIn("error HTTP", result.error)
        self.assertEqual(request.call_count, 2)


@override_settings(**ADS_SETTINGS)
class AdsServiceAdSetValidationTests(TestCase):
    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_set_without_page_reports_config_error(self, request):
        with override_settings(META_FB_PAGE_ID=""):
            result = ads_service.create_status_ad_set(
                "camp-1", name="Ad set", daily_budget=1000
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "configuracion")
        self.assertIn("Pagina", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_set_without_phone_reports_config_error(self, request):
        with override_settings(META_WHATSAPP_PHONE=""):
            result = ads_service.create_status_ad_set(
                "camp-1", name="Ad set", daily_budget=1000
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "configuracion")
        self.assertIn("WhatsApp", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_set_validates_page_before_phone(self, request):
        with override_settings(META_FB_PAGE_ID="", META_WHATSAPP_PHONE=""):
            result = ads_service.create_status_ad_set(
                "camp-1", name="Ad set", daily_budget=1000
            )

        self.assertFalse(result.ok)
        self.assertIn("Pagina", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_set_without_id_reports_error(self, request):
        request.return_value = _ok_response({})

        result = ads_service.create_status_ad_set(
            "camp-1", name="Ad set", daily_budget=1000
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sin id")


@override_settings(**ADS_SETTINGS)
class AdsServiceUploadImageTests(TestCase):
    @patch("communications.services.ads_service.requests.request")
    def test_upload_ad_image_reports_oserror_for_missing_file(self, request):
        result = ads_service.upload_ad_image("/ruta/que/no/existe/aviso.jpg")

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "Error de archivo local.")
        self.assertIn("No se pudo abrir", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_upload_ad_image_without_hash_reports_error(self, request):
        request.return_value = _ok_response({"images": {}})
        image = ContentFile(b"fake-jpeg", name="aviso.jpg")

        result = ads_service.upload_ad_image(image)

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "sin hash")
        self.assertIn("hash", result.summary)

    @patch("communications.services.ads_service.requests.request")
    def test_upload_ad_image_passed_content_type_overrides_inference(self, request):
        request.return_value = _ok_response({"images": {"aviso.jpg": {"hash": "abc"}}})
        image = ContentFile(b"fake-jpeg", name="aviso.jpg")

        result = ads_service.upload_ad_image(image, content_type="image/png")

        self.assertTrue(result.ok)
        _args, kwargs = request.call_args
        filename, _file, mime = kwargs["files"]["filename"]
        self.assertEqual(filename, "aviso.jpg")
        self.assertEqual(mime, "image/png")

    @patch("communications.services.ads_service.requests.request")
    def test_upload_ad_image_passed_content_type_adds_extension(self, request):
        request.return_value = _ok_response({"images": {"archivo.png": {"hash": "abc"}}})
        image = ContentFile(b"fake-png", name="archivo")

        result = ads_service.upload_ad_image(image, content_type="image/png")

        self.assertTrue(result.ok)
        _args, kwargs = request.call_args
        filename, _file, mime = kwargs["files"]["filename"]
        self.assertEqual(filename, "archivo.png")
        self.assertEqual(mime, "image/png")


@override_settings(**ADS_SETTINGS)
class AdsServiceCreateStatusAdFlowTests(TestCase):
    def _meta_dispatcher(self, method, url, **kwargs):
        if url.endswith("/campaigns"):
            return _ok_response({"id": "camp-1"})
        if url.endswith("/adimages"):
            return _ok_response({"images": {"aviso.jpg": {"hash": "hash-1"}}})
        if url.endswith("/adsets"):
            return _ok_response({"id": "set-1"})
        if url.endswith("/adcreatives"):
            return _ok_response({"id": "crea-1"})
        if url.endswith("/ads"):
            return _ok_response({"id": "ad-1"})
        raise AssertionError(f"URL inesperada: {url}")

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_full_flow_creates_every_object(self, request):
        request.side_effect = self._meta_dispatcher
        image = ContentFile(b"fake-jpeg", name="aviso.jpg")

        result = ads_service.create_status_ad(
            name="Aviso", message="Hola", daily_budget=2000000, image=image
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["campaign_id"], "camp-1")
        self.assertEqual(result.data["image_hash"], "hash-1")
        self.assertEqual(result.data["ad_set_id"], "set-1")
        self.assertEqual(result.data["creative_id"], "crea-1")
        self.assertEqual(result.data["ad_id"], "ad-1")
        self.assertEqual(request.call_count, 5)
        urls = [call.args[1] for call in request.call_args_list]
        for suffix in ("/campaigns", "/adimages", "/adsets", "/adcreatives", "/ads"):
            self.assertTrue(any(url.endswith(suffix) for url in urls), suffix)

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_reuses_campaign_and_ad_set(self, request):
        request.side_effect = self._meta_dispatcher
        image = ContentFile(b"fake-jpeg", name="aviso.jpg")

        result = ads_service.create_status_ad(
            name="Aviso",
            message="Hola",
            daily_budget=2000000,
            image=image,
            campaign_id="camp-existing",
            ad_set_id="set-existing",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["campaign_id"], "camp-existing")
        self.assertEqual(result.data["ad_set_id"], "set-existing")
        self.assertEqual(result.data["creative_id"], "crea-1")
        self.assertEqual(result.data["ad_id"], "ad-1")
        self.assertEqual(request.call_count, 3)
        urls = [call.args[1] for call in request.call_args_list]
        self.assertFalse(any(url.endswith("/campaigns") for url in urls))
        self.assertFalse(any(url.endswith("/adsets") for url in urls))

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_with_image_hash_skips_upload(self, request):
        request.side_effect = self._meta_dispatcher

        result = ads_service.create_status_ad(
            name="Aviso",
            message="Hola",
            daily_budget=2000000,
            image_hash="hash-1",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.data["ad_id"], "ad-1")
        self.assertEqual(request.call_count, 4)
        urls = [call.args[1] for call in request.call_args_list]
        self.assertFalse(any(url.endswith("/adimages") for url in urls))

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_without_configuration_reports_missing_variables(self, request):
        with override_settings(
            META_ADS_ACCESS_TOKEN="",
            META_AD_ACCOUNT_ID="",
            META_FB_PAGE_ID="",
            META_WHATSAPP_PHONE="",
        ):
            result = ads_service.create_status_ad(
                name="Aviso", message="Hola", daily_budget=2000000
            )

        self.assertFalse(result.ok)
        self.assertEqual(result.error, "configuracion")
        self.assertIn("Falta configurar", result.summary)
        request.assert_not_called()

    @patch("communications.services.ads_service.requests.request")
    def test_create_status_ad_stops_when_image_upload_fails(self, request):
        def side_effect(method, url, **kwargs):
            if url.endswith("/campaigns"):
                return _ok_response({"id": "camp-1"})
            raise requests.ConnectionError("sin red")

        request.side_effect = side_effect
        image = ContentFile(b"fake-jpeg", name="aviso.jpg")

        result = ads_service.create_status_ad(
            name="Aviso", message="Hola", daily_budget=2000000, image=image
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.data["campaign_id"], "camp-1")
        self.assertNotIn("ad_set_id", result.data)
        self.assertIn("Error de conexión", result.error)
