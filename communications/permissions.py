# API interna de comunicaciones (/campanas/api/).
"""Permisos de la API interna.

Aunque nacio como API "solo BFF", la UI de `/campanas/` la consume desde el
navegador con la sesion iniciada (mismo origen). Por eso se acepta cualquiera de
las dos vias:

- sesion autenticada (como el resto de APIs del proyecto), o
- header `X-Internal-Token` que coincida con `settings.INTERNAL_API_TOKEN`
  (consumidores de servicio / BFF con DEBUG=False).

En desarrollo (`DEBUG=True`) se permite todo para facilitar pruebas locales.
Reemplazar el token por autenticacion real (mTLS, JWT de servicio, etc.) cuando
se defina con el equipo de BFF.
"""

from django.conf import settings
from rest_framework.permissions import BasePermission


class IsInternalService(BasePermission):
    message = "Esta API es de uso interno (BFF)."

    def has_permission(self, request, view):
        if settings.DEBUG:
            return True

        # La pagina /campanas/ llama a esta API desde el navegador con su sesion.
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return True

        expected_token = getattr(settings, "INTERNAL_API_TOKEN", None)
        provided_token = request.headers.get("X-Internal-Token")
        return bool(expected_token) and provided_token == expected_token