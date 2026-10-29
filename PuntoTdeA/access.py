from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden, JsonResponse
from rest_framework.permissions import BasePermission


def user_has_explicit_permission(user, permission_name):
    """Concede al superusuario y valida acceso directo o por grupo al resto."""
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "is_active", False)
        or not isinstance(permission_name, str)
        or permission_name.count(".") != 1
    ):
        return False

    app_label, codename = permission_name.split(".", 1)
    if not app_label or not codename:
        return False
    if getattr(user, "is_superuser", False):
        return True

    direct_permission = user.user_permissions.filter(
        content_type__app_label=app_label,
        codename=codename,
    ).exists()
    return direct_permission or user.groups.filter(
        permissions__content_type__app_label=app_label,
        permissions__codename=codename,
    ).exists()


class HasModulePermission(BasePermission):
    permission_name = None

    def has_permission(self, request, view):
        permission_name = self.permission_name or getattr(view, "module_permission", None)
        return user_has_explicit_permission(
            getattr(request, "user", None),
            permission_name,
        )


def module_access_required(
    permission_name,
    login_url=None,
    *,
    api=False,
    staff_only=False,
    module_name="este módulo",
):
    """Restringe una vista Django a usuarios activos con permiso explícito."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if (
                user is None
                or not getattr(user, "is_authenticated", False)
                or not getattr(user, "is_active", False)
            ):
                if api:
                    return JsonResponse(
                        {"detail": "Autenticación requerida."},
                        status=401,
                    )
                return redirect_to_login(
                    request.get_full_path(),
                    login_url=login_url or settings.LOGIN_URL,
                )
            if not user_has_explicit_permission(user, permission_name) or (
                staff_only and not user.is_staff
            ):
                message = f"No tienes permiso para acceder a {module_name}."
                if api:
                    return JsonResponse({"detail": message}, status=403)
                return HttpResponseForbidden(message)
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
