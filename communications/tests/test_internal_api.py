"""Acceso a la API interna de comunicaciones (/campanas/api/).

La UI de `/campanas/` consume esta API desde el navegador con la sesion
iniciada. Con DEBUG=False el permiso debe aceptar sesion autenticada o el
header X-Internal-Token, y rechazar el resto.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


@override_settings(
    DEBUG=False,
    INTERNAL_API_TOKEN="service-token",
    ALLOWED_HOSTS=["testserver"],
)
class InternalApiAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="staffer",
            password="clave-prueba",
            is_staff=True,
        )

    def test_anonymous_requests_are_rejected(self):
        response = self.client.get("/campanas/api/campaigns/")
        self.assertEqual(response.status_code, 403)

    def test_authenticated_session_is_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get("/campanas/api/campaigns/")
        self.assertEqual(response.status_code, 200)

    def test_valid_service_token_is_allowed(self):
        response = self.client.get(
            "/campanas/api/campaigns/",
            headers={"X-Internal-Token": "service-token"},
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_service_token_is_rejected(self):
        response = self.client.get(
            "/campanas/api/campaigns/",
            headers={"X-Internal-Token": "otro-token"},
        )
        self.assertEqual(response.status_code, 403)
