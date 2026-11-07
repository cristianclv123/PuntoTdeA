from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.middleware.csrf import CsrfViewMiddleware
from django.test import RequestFactory, TestCase

from PuntoTdeA.views import LOGIN_NEXT_SESSION_KEY, login_view


def _with_session(request):
    request.user = AnonymousUser()
    SessionMiddleware(lambda _request: None).process_request(request)
    request.session.save()
    return request


class LoginSecurityTests(TestCase):
    def test_login_does_not_reflect_next_or_username(self):
        request = _with_session(RequestFactory().get("/login/?next=/avisos/"))
        response = login_view(request)

        body = response.content.decode()
        self.assertNotIn("/avisos/", body)
        self.assertNotIn("fonts.googleapis.com", body)
        self.assertNotIn("<script>", body)
        self.assertEqual(request.session[LOGIN_NEXT_SESSION_KEY], "/avisos/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("script-src 'self'", response["Content-Security-Policy"])

        failed = _with_session(
            RequestFactory().post(
                "/login/",
                {"username": '"><script>', "password": "no-es-la-clave"},
            )
        )
        failed_response = login_view(failed)
        failed_body = failed_response.content.decode()
        self.assertNotIn("<script>", failed_body)
        self.assertIn("Credenciales inválidas", failed_body)

    def test_external_next_is_discarded_and_internal_next_still_redirects(self):
        external = _with_session(
            RequestFactory().get("/login/?next=https://evil.example/phish")
        )
        login_view(external)
        self.assertNotIn(LOGIN_NEXT_SESSION_KEY, external.session)

        User = get_user_model()
        User.objects.create_user("asesor_login", password="secret123")
        opened = _with_session(RequestFactory().get("/login/?next=/bandeja/"))
        login_view(opened)
        posted = _with_session(
            RequestFactory().post(
                "/login/",
                {"username": "asesor_login", "password": "secret123"},
            )
        )
        posted.session = opened.session
        response = login_view(posted)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/bandeja/")

    def test_csrf_cookie_on_login_is_httponly(self):
        request = _with_session(RequestFactory().get("/login/"))
        response = CsrfViewMiddleware(login_view)(request)
        self.assertTrue(response.cookies["csrftoken"]["httponly"])
