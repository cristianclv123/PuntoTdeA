"""Validaciones en vivo de la configuración de Meta WhatsApp Cloud API.

Estas funciones hacen peticiones a Graph API y solo se invocan de forma
explícita (management command o la página de prueba). No se ejecutan al iniciar
Django ni en las peticiones normales de la aplicación.
"""

from __future__ import annotations

import logging
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


def _graph_error(response: requests.Response) -> str:
    try:
        error = response.json().get("error", {})
    except (TypeError, ValueError):
        return f"Meta API respondió HTTP {response.status_code}."
    message = error.get("message") or "Error sin detalle."
    code = error.get("code")
    return f"[{code}] {message}" if code else message


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
    except requests.RequestException as exc:
        return DiagnosticResult(ok=False, summary="No se pudo contactar a Graph API.", error=str(exc))

    if response.status_code != 200:
        return DiagnosticResult(ok=False, summary="Meta rechazó la consulta del token.", error=_graph_error(response))

    data = response.json().get("data", {})
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
    except requests.RequestException as exc:
        return DiagnosticResult(ok=False, summary="No se pudo contactar a Graph API.", error=str(exc))

    if response.status_code != 200:
        return DiagnosticResult(ok=False, summary="Meta rechazó la consulta del número.", error=_graph_error(response))

    data = response.json()
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
    except requests.RequestException as exc:
        return DiagnosticResult(ok=False, summary="No se pudo contactar el callback.", error=str(exc))

    if response.status_code != 200:
        return DiagnosticResult(
            ok=False,
            summary=f"El callback respondió HTTP {response.status_code}.",
        )
    if response.text.strip() != "diagnostico":
        return DiagnosticResult(
            ok=False,
            summary="El callback respondió, pero no devolvió el challenge.",
            details={"body": response.text[:200]},
        )
    return DiagnosticResult(ok=True, summary="El callback público valida el desafío de Meta.")


def is_ready() -> bool:
    """Configuración completa y sin pendientes obvios."""
    return meta_config.is_fully_configured() and meta_config.can_receive_webhooks()
