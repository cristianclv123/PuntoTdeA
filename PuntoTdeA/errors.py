"""Páginas de error del sitio. La API sigue respondiendo JSON."""

from html import escape
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponse, JsonResponse

_PAGE = Path(settings.BASE_DIR) / "templates" / "errors" / "page.html"

HOME_URL = "/"

PAGES = {
    400: ("Solicitud no válida", "No pudimos entender lo que pediste."),
    401: ("Sesión requerida", "Necesitas entrar para ver esta página."),
    402: ("Pago requerido", "Esta acción no está disponible."),
    403: ("Sin acceso", "No tienes permiso para ver esta página."),
    404: ("Página no encontrada", "Esa ruta no existe en Punto TdeA."),
    405: ("Método no permitido", "Esta página no acepta esa acción."),
    500: ("Error del servidor", "Algo falló de nuestro lado."),
}

HTML_STATUSES = frozenset(PAGES)


def _is_api(request) -> bool:
    path = getattr(request, "path", "") or ""
    return path.startswith("/api/") or path.startswith("/admin/")


def _page_copy(status: int, detail: str = "") -> tuple[str, str]:
    title, message = PAGES.get(status, ("Algo salió mal", "No pudimos completar la solicitud."))
    text = (detail or "").strip()
    if text and text not in {"PermissionDenied", "Http404"}:
        message = text
    return title, message


def render_error(request, status: int, detail: str = ""):
    status = int(status)
    title, message = _page_copy(status, detail)
    if _is_api(request):
        return JsonResponse({"detail": message}, status=status)
    css = f"{settings.STATIC_URL.rstrip('/')}/css/errors.css"
    html = (
        _PAGE.read_text(encoding="utf-8")
        .replace("__STATUS__", str(status))
        .replace("__TITLE__", escape(title))
        .replace("__MESSAGE__", escape(message))
        .replace("__HOME__", escape(HOME_URL))
        .replace("__CSS__", escape(css))
    )
    response = HttpResponse(html, status=status)
    # La página de error es la que ZAP vio en rutas inexistentes de casos.
    # No carga scripts ni hojas de terceros.
    response["Content-Security-Policy"] = "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "img-src 'self'",
            "font-src 'self'",
            "style-src 'self'",
            "script-src 'none'",
        ]
    )
    return response


def bad_request(request, exception=None):
    return render_error(request, 400, str(exception or ""))


def permission_denied(request, exception=None):
    return render_error(request, 403, str(exception or ""))


def page_not_found(request, exception=None):
    return render_error(request, 404, str(exception or ""))


def server_error(request):
    return render_error(request, 500)


def csrf_failure(request, reason=""):
    return render_error(
        request,
        403,
        "La sesión del formulario venció. Vuelve a entrar desde el inicio.",
    )


def _status_for_exception(exception) -> int | None:
    if isinstance(exception, Http404):
        return 404
    if isinstance(exception, PermissionDenied):
        return 403
    if isinstance(exception, SuspiciousOperation):
        return 400
    return None


class ErrorPageMiddleware:
    """Sustituye el error en blanco del sitio por la página que vuelve al inicio."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if self._should_replace(request, response):
            return render_error(request, response.status_code)
        return response

    def process_exception(self, request, exception):
        if (getattr(request, "path", "") or "").startswith("/admin/"):
            return None
        status = _status_for_exception(exception)
        if status is None:
            return None
        return render_error(request, status, str(exception or ""))

    def _should_replace(self, request, response) -> bool:
        if _is_api(request) or response.status_code not in HTML_STATUSES:
            return False
        if b"data-error-page" in getattr(response, "content", b""):
            return False
        content_type = response.get("Content-Type", "")
        return content_type.startswith("text/html") or content_type.startswith("text/plain")
