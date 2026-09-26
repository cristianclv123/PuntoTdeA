# Solo BFF/servicios internos autorizados
"""Permisos: esta API la consume únicamente el BFF (ver arquitectura),
nunca el navegador del usuario final ni el widget público directamente.

En desarrollo (DEBUG=True) se permite todo para facilitar pruebas locales.
En producción exige un header `X-Internal-Token` que coincida con
`settings.INTERNAL_API_TOKEN` — reemplazar por autenticación real
(mTLS, JWT de servicio, etc.) cuando se defina con el equipo de BFF.
"""

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsInternalService(BasePermission):
    message = "Esta API es de uso interno (BFF)."

    def has_permission(self, request, view):
        if settings.DEBUG:
            return True
        expected_token = getattr(settings, "INTERNAL_API_TOKEN", None)
        provided_token = request.headers.get("X-Internal-Token")
        return bool(expected_token) and provided_token == expected_token