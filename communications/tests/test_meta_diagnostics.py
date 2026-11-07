"""Pruebas de errores seguros para los diagnósticos de Meta."""

from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings

from communications.services import meta_diagnostics


DIAGNOSTIC_SETTINGS = {
    "META_GRAPH_API_URL": "https://graph.facebook.com",
    "WHATSAPP_API_VERSION": "v21.0",
    "META_ACCESS_TOKEN": "fake-meta-access-token",
    "META_ADS_ACCESS_TOKEN": "fake-ads-access-token",
    "META_APP_SECRET": "fake-app-secret",
    "META_VERIFY_TOKEN": "fake-verify-token",
    "WHATSAPP_PHONE_NUMBER_ID": "phone-id-1",
    "META_REQUEST_TIMEOUT": 5,
}


def _response(*, status=200, body=None, text=""):
    response = Mock()
    response.status_code = status
    response.json.return_value = body
    response.text = text
    return response


@override_settings(**DIAGNOSTIC_SETTINGS)
class MetaDiagnosticsErrorTests(SimpleTestCase):
    secrets = (
        "fake-meta-access-token",
        "fake-ads-access-token",
        "fake-app-secret",
        "fake-verify-token",
    )

    def assert_no_credentials(self, result):
        rendered = repr(result)
        for secret in self.secrets:
            self.assertNotIn(secret, rendered)
        self.assertNotIn("graph.facebook.com", rendered)
        self.assertNotIn("hub.verify_token", rendered)

    def test_access_token_request_exceptions_are_controlled(self):
        sensitive_url = (
            "https://graph.facebook.com/debug_token?"
            "access_token=fake-meta-access-token&input_token=fake-meta-access-token"
        )
        cases = (
            (requests.ConnectionError, "Error de conexión"),
            (requests.Timeout, "Tiempo de espera agotado"),
            (RuntimeError, "Error inesperado"),
        )

        for exception_type, category in cases:
            with self.subTest(exception_type=exception_type.__name__):
                with patch(
                    "communications.services.meta_diagnostics.requests.get",
                    side_effect=exception_type(sensitive_url),
                ):
                    result = meta_diagnostics.check_access_token()

                self.assertFalse(result.ok)
                self.assertIn(category, result.error)
                self.assert_no_credentials(result)

    def test_phone_number_meta_error_keeps_code_but_not_token_in_message(self):
        response = _response(
            status=400,
            body={
                "error": {
                    "message": "Token fake-meta-access-token rechazado",
                    "type": "OAuthException",
                    "code": 190,
                    "error_subcode": 463,
                    "fbtrace_id": "Trace-9876_a",
                }
            },
        )
        with patch("communications.services.meta_diagnostics.requests.get", return_value=response):
            result = meta_diagnostics.check_phone_number()

        self.assertFalse(result.ok)
        self.assertIn("código 190", result.error)
        self.assertIn("subcódigo 463", result.error)
        self.assertIn("tipo OAuthException", result.error)
        self.assertIn("seguimiento Trace-9876_a", result.error)
        self.assertNotIn("rechazado", result.error)
        self.assert_no_credentials(result)

    def test_non_json_http_error_never_returns_response_body(self):
        response = _response(
            status=502,
            text="Proxy error https://graph.facebook.com/?access_token=fake-meta-access-token",
        )
        response.json.side_effect = ValueError(
            "invalid JSON at https://graph.facebook.com/?access_token=fake-meta-access-token"
        )
        with patch("communications.services.meta_diagnostics.requests.get", return_value=response):
            result = meta_diagnostics.check_phone_number()

        self.assertFalse(result.ok)
        self.assertIn("HTTP 502", result.error)
        self.assertNotIn("Proxy error", result.error)
        self.assert_no_credentials(result)

    def test_successful_json_decode_errors_are_returned_as_invalid_response(self):
        response = _response(status=200)
        response.json.side_effect = ValueError(
            "invalid JSON at https://graph.facebook.com/?access_token=fake-meta-access-token"
        )
        with patch("communications.services.meta_diagnostics.requests.get", return_value=response):
            token_result = meta_diagnostics.check_access_token()
        self.assertFalse(token_result.ok)
        self.assertIn("JSON inválida", token_result.error)
        self.assert_no_credentials(token_result)

        with patch("communications.services.meta_diagnostics.requests.get", return_value=response):
            phone_result = meta_diagnostics.check_phone_number()
        self.assertFalse(phone_result.ok)
        self.assertIn("JSON inválida", phone_result.error)
        self.assert_no_credentials(phone_result)

    def test_webhook_connection_error_does_not_return_callback_url_or_verify_token(self):
        callback_url = "https://example.test/api/webhook/"
        error_url = f"{callback_url}?hub.verify_token=fake-verify-token"
        with patch(
            "communications.services.meta_diagnostics.requests.get",
            side_effect=requests.Timeout(error_url),
        ) as request:
            result = meta_diagnostics.webhook_reachable(callback_url)

        self.assertFalse(result.ok)
        self.assertIn("Tiempo de espera agotado", result.error)
        self.assert_no_credentials(result)
        self.assertEqual(request.call_args.kwargs["params"]["hub.verify_token"], "fake-verify-token")

    def test_successful_diagnostics_keep_existing_safe_details(self):
        token_response = _response(
            body={
                "data": {
                    "is_valid": True,
                    "scopes": ["whatsapp_business_messaging", "ads_management"],
                    "app_id": "123456",
                    "user_id": "789012",
                    "expires_at": 1900000000,
                }
            }
        )
        phone_response = _response(
            body={
                "verified_name": "PuntoTdeA",
                "display_phone_number": "+57 300 000 0000",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "platform_type": "CLOUD_API",
            }
        )
        with patch(
            "communications.services.meta_diagnostics.requests.get",
            side_effect=[token_response, phone_response],
        ):
            token_result = meta_diagnostics.check_access_token()
            phone_result = meta_diagnostics.check_phone_number()

        self.assertTrue(token_result.ok)
        self.assertEqual(token_result.details["scopes"], ["whatsapp_business_messaging", "ads_management"])
        self.assertEqual(token_result.details["app_id"], "123456")
        self.assertTrue(phone_result.ok)
        self.assertEqual(phone_result.details["quality_rating"], "GREEN")
        self.assert_no_credentials(token_result)
        self.assert_no_credentials(phone_result)

    def test_webhook_response_mismatch_does_not_return_untrusted_body(self):
        response = _response(status=200, text="echo fake-verify-token and URL")
        with patch("communications.services.meta_diagnostics.requests.get", return_value=response):
            result = meta_diagnostics.webhook_reachable("https://example.test/api/webhook/")

        self.assertFalse(result.ok)
        self.assertEqual(result.details, {"challenge_received": False})
        self.assert_no_credentials(result)

    def test_webhook_success_keeps_the_existing_challenge_protocol(self):
        response = _response(status=200, text="diagnostico")
        callback_url = "https://example.test/api/webhook/"
        with patch("communications.services.meta_diagnostics.requests.get", return_value=response) as request:
            result = meta_diagnostics.webhook_reachable(callback_url)

        self.assertTrue(result.ok)
        self.assertEqual(result.summary, "El callback público valida el desafío de Meta.")
        self.assertEqual(request.call_args.args[0], callback_url)
        self.assertEqual(
            request.call_args.kwargs["params"],
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "fake-verify-token",
                "hub.challenge": "diagnostico",
            },
        )
