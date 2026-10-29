"""Acceso a la API interna de comunicaciones (/campanas/api/).

La UI de `/campanas/` consume esta API desde el navegador con la sesión
iniciada y el permiso explícito del módulo. Los consumidores de servicio
pueden usar `X-Internal-Token` con DEBUG=False.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
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
        permission = Permission.objects.get(
            content_type__app_label="communications",
            codename="access_communications",
        )
        self.user.user_permissions.add(permission)

    def test_anonymous_requests_are_rejected(self):
        response = self.client.get("/campanas/api/campaigns/")
        self.assertEqual(response.status_code, 403)

    def test_authenticated_session_is_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get("/campanas/api/campaigns/")
        self.assertEqual(response.status_code, 200)

    def test_authenticated_session_without_module_permission_is_rejected(self):
        user_without_permission = get_user_model().objects.create_user(
            username="staff-sin-permiso",
            password="clave-prueba",
            is_staff=True,
        )
        self.client.force_login(user_without_permission)
        response = self.client.get("/campanas/api/campaigns/")
        self.assertEqual(response.status_code, 403)

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
