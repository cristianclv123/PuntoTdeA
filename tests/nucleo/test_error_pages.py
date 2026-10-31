from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from PuntoTdeA.errors import render_error


class ErrorPageTests(TestCase):
    def test_unknown_route_renders_404_and_redirects_home(self):
        response = self.client.get("/esta-pagina-no-existe/")
        self.assertEqual(response.status_code, 404)
        body = response.content.decode()
        self.assertIn('data-error-page="404"', body)
        self.assertIn('http-equiv="refresh" content="3;url=/"', body)
        self.assertIn("Página no encontrada", body)
        self.assertIn("Ir al inicio ahora", body)

    def test_module_without_permission_renders_403_page(self):
        user = get_user_model().objects.create_user(username="sin-avisos", password="secret123")
        self.client.force_login(user)
        response = self.client.get("/avisos/")
        self.assertEqual(response.status_code, 403)
        body = response.content.decode()
        self.assertIn('data-error-page="403"', body)
        self.assertIn("No tienes permiso para acceder a Announcements.", body)
        self.assertIn('content="3;url=/"', body)

    def test_payment_required_page_redirects_home(self):
        response = render_error(RequestFactory().get("/pago/"), 402)
        self.assertEqual(response.status_code, 402)
        body = response.content.decode()
        self.assertIn('data-error-page="402"', body)
        self.assertIn("Pago requerido", body)
        self.assertIn('content="3;url=/"', body)

    def test_api_not_found_stays_json(self):
        response = self.client.get("/api/esto-no-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"data-error-page", response.content)
        self.assertIn("application/json", response["Content-Type"])
