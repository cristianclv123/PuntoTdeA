"""Validaciones en vivo de la configuración de Meta WhatsApp Cloud API.

Estas funciones hacen peticiones a Graph API y solo se invocan de forma
explícita (management command o la página de prueba). No se ejecutan al iniciar
Django ni en las peticiones normales de la aplicación.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings

from . import meta_config


logger = logging.getLogger(__name__)

TOKEN_FIELDS = (
    "is_valid",
    "scopes",
    "app_id",
    "user_id",
    "expires_at",
)

PHONE_FIELDS = (
    "verified_name",
    "display_phone_number",
    "quality_rating",
    "code_verification_status",
    "platform_type",
)


@dataclass
class DiagnosticResult:
    ok: bool
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _safe_error_code(value: Any) -> str:
    text = ""
    if isinstance(value, int) and not isinstance(value, bool):
        text = str(value)
    elif isinstance(value, str) and re.fullmatch(r"\d{1,10}", value):
        text = value
    if not text:
        return ""
    for name in ("META_ACCESS_TOKEN", "META_ADS_ACCESS_TOKEN", "META_APP_SECRET", "META_VERIFY_TOKEN"):
        secret = str(getattr(settings, name, "") or "")
        if secret and secret in text:
            return ""
    return text


def _safe_meta_identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value):
        return ""
    for name in ("META_ACCESS_TOKEN", "META_ADS_ACCESS_TOKEN", "META_APP_SECRET", "META_VERIFY_TOKEN"):
        secret = str(getattr(settings, name, "") or "")
        if secret and secret in value:
            return ""
    return value


def _graph_error(response: requests.Response) -> str:
    status_code = getattr(response, "status_code", None)
    try:
        payload = response.json()
    except Exception:
        return f"Meta API respondió HTTP {status_code} con una respuesta inválida."

    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return f"Meta API respondió HTTP {status_code} con un error no estructurado."

    details = []
    code = _safe_error_code(error.get("code"))
    subcode = _safe_error_code(error.get("error_subcode"))
    error_type = _safe_meta_identifier(error.get("type"))
    trace_id = _safe_meta_identifier(error.get("fbtrace_id"))
    if code:
        details.append(f"código {code}")
    if subcode:
        details.append(f"subcódigo {subcode}")
    if error_type:
        details.append(f"tipo {error_type}")
    if trace_id:
        details.append(f"seguimiento {trace_id}")
    if status_code is not None:
        details.insert(0, f"HTTP {status_code}")
    suffix = f" ({', '.join(details)})" if details else ""
    return f"Meta rechazó la solicitud{suffix}; mensaje del proveedor omitido por seguridad."


def _request_error(exc: Exception, target: str = "Graph API") -> str:
    if isinstance(exc, requests.Timeout):
        return f"Tiempo de espera agotado al contactar {target}."
    if isinstance(exc, requests.ConnectionError):
        return f"Error de conexión al contactar {target}."
    if isinstance(exc, requests.HTTPError):
        return f"{target} devolvió un error HTTP."
    if isinstance(exc, requests.RequestException):
        return f"Error de comunicación con {target}."
    return f"Error inesperado de comunicación con {target}."


def _invalid_response_error() -> str:
    return "Graph API devolvió una respuesta JSON inválida."


def _request(path: str, params: dict[str, str]) -> requests.Response:
    version = str(settings.WHATSAPP_API_VERSION or "v21.0")
    return requests.get(
        f"{_graph_config()}/{version}/{path.lstrip('/')}",
        params=params,
        timeout=settings.META_REQUEST_TIMEOUT,
    )


def _graph_config() -> str:
    """Raíz de Graph API, sin barra final. Única fuente de verdad del host."""
    return str(settings.META_GRAPH_API_URL or "https://graph.facebook.com").rstrip("/")


def _debug_config() -> str:
    return f"{_graph_config()}/debug_token"


def _access_token() -> str:
    return str(settings.META_ACCESS_TOKEN or "").strip()


def check_access_token() -> DiagnosticResult:
    """Verifica el token con `debug_token` y reporta sus permisos."""
    token = _access_token()
    if not token:
        return DiagnosticResult(ok=False, summary="META_ACCESS_TOKEN no está configurado.")

    try:
        response = requests.get(
            _debug_config(),
            params={"input_token": token, "access_token": token},
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except Exception as exc:
        return DiagnosticResult(ok=False, summary="No se pudo contactar a Graph API.", error=_request_error(exc))

    if response.status_code != 200:
        return DiagnosticResult(ok=False, summary="Meta rechazó la consulta del token.", error=_graph_error(response))

    try:
        payload = response.json()
    except Exception:
        return DiagnosticResult(ok=False, summary="Graph API devolvió una respuesta inválida.", error=_invalid_response_error())
    data = payload.get("data", {}) if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return DiagnosticResult(ok=False, summary="Graph API devolvió una respuesta inválida.", error=_invalid_response_error())
    is_valid = bool(data.get("is_valid"))
    scopes = data.get("scopes") or []
    details = {key: data.get(key) for key in TOKEN_FIELDS if key in data}
    details["scopes"] = scopes
    details["whatsapp_scopes"] = sorted(s for s in scopes if "whatsapp" in s.lower())
    summary = "Token válido." if is_valid else "Meta considera el token inválido."
    return DiagnosticResult(ok=is_valid, summary=summary, details=details)


def check_phone_number() -> DiagnosticResult:
    """Consulta los datos del número emisor configurado."""
    phone_number_id = str(settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
    if not phone_number_id:
        return DiagnosticResult(ok=False, summary="WHATSAPP_PHONE_NUMBER_ID no está configurado.")
    if not _access_token():
        return DiagnosticResult(ok=False, summary="META_ACCESS_TOKEN no está configurado.")

    try:
        response = _request(
            f"{phone_number_id}",
            {
                "fields": ",".join(PHONE_FIELDS),
                "access_token": _access_token(),
            },
        )
    except Exception as exc:
        return DiagnosticResult(ok=False, summary="No se pudo contactar a Graph API.", error=_request_error(exc))

    if response.status_code != 200:
        return DiagnosticResult(ok=False, summary="Meta rechazó la consulta del número.", error=_graph_error(response))

    try:
        data = response.json()
    except Exception:
        return DiagnosticResult(ok=False, summary="Graph API devolvió una respuesta inválida.", error=_invalid_response_error())
    if not isinstance(data, dict):
        return DiagnosticResult(ok=False, summary="Graph API devolvió una respuesta inválida.", error=_invalid_response_error())
    details = {key: data.get(key) for key in PHONE_FIELDS if key in data}
    verified = bool(data.get("verified_name"))
    summary = (
        f"Número registrado como {data.get('display_phone_number') or 'sin número visible'}."
        if verified
        else "El número aún no tiene nombre verificado en Meta."
    )
    return DiagnosticResult(ok=True, summary=summary, details=details)


def run_all() -> list[tuple[str, DiagnosticResult]]:
    """Ejecuta las validaciones en el orden en que conviene revisarlas."""
    return [
        ("Token de acceso", check_access_token()),
        ("Número emisor", check_phone_number()),
    ]


def webhook_reachable(url: str) -> DiagnosticResult:
    """Comprueba que el callback público responde al desafío de Meta."""
    try:
        response = requests.get(
            url,
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": str(settings.META_VERIFY_TOKEN or ""),
                "hub.challenge": "diagnostico",
            },
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except Exception as exc:
        return DiagnosticResult(
            ok=False,
            summary="No se pudo contactar el callback.",
            error=_request_error(exc, "el callback"),
        )

    if response.status_code != 200:
        return DiagnosticResult(
            ok=False,
            summary=f"El callback respondió HTTP {response.status_code}.",
        )
    if response.text.strip() != "diagnostico":
        return DiagnosticResult(
            ok=False,
            summary="El callback respondió, pero no devolvió el challenge.",
            details={"challenge_received": False},
        )
    return DiagnosticResult(ok=True, summary="El callback público valida el desafío de Meta.")


def is_ready() -> bool:
    """Configuración completa y sin pendientes obvios."""
    return meta_config.is_fully_configured() and meta_config.can_receive_webhooks()
