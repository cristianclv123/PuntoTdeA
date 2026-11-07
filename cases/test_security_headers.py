from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.middleware.security import SecurityMiddleware

from PuntoTdeA.errors import render_error
from cases.security import (
    CASES_CONTENT_SECURITY_POLICY,
    CasesContentSecurityPolicyMiddleware,
)


class CasesSecurityHeaderTests(TestCase):
    def test_bandeja_html_receives_content_security_policy(self):
        request = RequestFactory().get("/bandeja/")
        response = HttpResponse("<html></html>", content_type="text/html; charset=utf-8")
        result = CasesContentSecurityPolicyMiddleware(lambda _request: response)(request)

        self.assertEqual(result["Content-Security-Policy"], CASES_CONTENT_SECURITY_POLICY)
        self.assertIn("script-src 'self'", result["Content-Security-Policy"])
        self.assertNotIn("fonts.googleapis.com", result["Content-Security-Policy"])

    def test_other_pages_keep_their_own_headers(self):
        request = RequestFactory().get("/login/")
        response = HttpResponse("<html></html>", content_type="text/html")
        result = CasesContentSecurityPolicyMiddleware(lambda _request: response)(request)

        self.assertNotIn("Content-Security-Policy", result)

    def test_cases_json_is_not_rewritten(self):
        request = RequestFactory().get("/bandeja/")
        response = HttpResponse("{}", content_type="application/json")
        result = CasesContentSecurityPolicyMiddleware(lambda _request: response)(request)

        self.assertNotIn("Content-Security-Policy", result)

    @override_settings(SECURE_HSTS_SECONDS=31536000, SECURE_SSL_REDIRECT=False)
    def test_secure_cases_response_sends_hsts(self):
        request = RequestFactory().get("/bandeja/1/", secure=True)
        response = HttpResponse("<html></html>", content_type="text/html")
        result = SecurityMiddleware(
            lambda req: CasesContentSecurityPolicyMiddleware(lambda _request: response)(req)
        )(request)

        self.assertIn("max-age=31536000", result["Strict-Transport-Security"])
        self.assertIn("Content-Security-Policy", result)

    def test_missing_cases_path_error_page_has_no_third_party_font(self):
        request = RequestFactory().get("/app/cases/urls.py")
        response = render_error(request, 404)

        body = response.content.decode()
        self.assertNotIn("fonts.googleapis.com", body)
        self.assertNotIn("<script", body)
        self.assertIn("script-src 'none'", response["Content-Security-Policy"])
        self.assertIn('data-error-page="404"', body)
