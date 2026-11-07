"""Cabeceras de seguridad de las páginas HTML de casos.

El informe ZAP marcó la bandeja y las rutas de casos por tres hallazgos:
falta Content-Security-Policy, la hoja de Google Fonts no trae integridad,
y en HTTPS no se envía Strict-Transport-Security. HSTS vive en settings
porque el navegador lo aplica a todo el sitio. Aquí queda la política
de contenido de las pantallas de casos.
"""

CASES_HTML_PREFIXES = ("/bandeja/", "/casos/")

# script-src queda en el mismo origen: el JS de la bandeja es archivo propio.
# style-src permite estilos en línea porque el compositor ajusta su alto
# con el DOM y eso cuenta como estilo en línea para el navegador.
CASES_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'self'",
        "form-action 'self'",
        "img-src 'self' data: blob:",
        "media-src 'self' blob:",
        "font-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "script-src 'self'",
        "connect-src 'self'",
    ]
)


class CasesContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path or ""
        if not path.startswith(CASES_HTML_PREFIXES):
            return response
        content_type = response.get("Content-Type", "")
        if not content_type.startswith("text/html"):
            return response
        response.headers.setdefault(
            "Content-Security-Policy",
            CASES_CONTENT_SECURITY_POLICY,
        )
        return response
