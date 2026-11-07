# API interna de comunicaciones (/campanas/api/).
"""Permisos de módulo e integración interna de Communications."""

from secrets import compare_digest

from django.conf import settings
from rest_framework.permissions import BasePermission

from PuntoTdeA.access import user_has_explicit_permission


COMMUNICATIONS_PERMISSION = "communications.access_communications"


def user_has_communications_access(user):
    return user_has_explicit_permission(user, COMMUNICATIONS_PERMISSION)


def has_internal_service_access(request):
    if user_has_communications_access(getattr(request, "user", None)):
        return True

    expected_token = getattr(settings, "INTERNAL_API_TOKEN", None)
    provided_token = request.headers.get("X-Internal-Token")
    return bool(expected_token and provided_token) and compare_digest(
        str(expected_token),
        str(provided_token),
    )


class IsInternalService(BasePermission):
    message = "Se requiere acceso a Communications o una credencial de servicio válida."

    def has_permission(self, request, view):
        return has_internal_service_access(request)


class IsAnnouncementsSegmentReader(BasePermission):
    message = "Se requiere acceso autorizado a los segmentos de avisos."

    def has_permission(self, request, view):
        return (
            request.method == "GET"
            and getattr(view, "action", None) in {"list", "contacts"}
            and user_has_explicit_permission(
                getattr(request, "user", None),
                "announcements.access_announcements",
            )
        )
