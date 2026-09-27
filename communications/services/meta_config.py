"""Estado de la configuración de Meta WhatsApp Cloud API.

Solo lee `django.conf.settings`; nunca imprime ni devuelve el valor de un
secreto. La validación en vivo contra Graph API vive en `meta_diagnostics`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

WEBHOOK_PATH = "/api/whatsapp/webhook/"


@dataclass(frozen=True)
class SettingStatus:
    name: str
    label: str
    value: str
    is_set: bool
    is_secret: bool
    detail: str = ""
    required: bool = True

    @property
    def state(self) -> str:
        if self.is_secret:
            return "configurado" if self.is_set else ("FALTA" if self.required else "opcional")
        if not self.is_set:
            return "vacío" if self.required else "opcional"
        return self.value


def _setting(name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


def _masked(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible:
        return "•" * len(value)
    return f"{'•' * 8}{value[-visible:]}"


def is_fully_configured() -> bool:
    """True cuando se puede enviar un mensaje real a Meta."""
    return bool(_setting("META_ACCESS_TOKEN") and _setting("WHATSAPP_PHONE_NUMBER_ID"))


def can_receive_webhooks() -> bool:
    """True cuando el webhook puede validar la firma de Meta."""
    return bool(_setting("META_APP_SECRET"))


def can_verify_subscription() -> bool:
    """True cuando el desafío inicial de Meta puede responderse."""
    return bool(_setting("META_VERIFY_TOKEN"))


def setting_statuses() -> list[SettingStatus]:
    verify_token = _setting("META_VERIFY_TOKEN")
    app_secret = _setting("META_APP_SECRET")
    access_token = _setting("META_ACCESS_TOKEN")
    phone_number_id = _setting("WHATSAPP_PHONE_NUMBER_ID")

    return [
        SettingStatus(
            "META_VERIFY_TOKEN",
            "Verify token",
            "",
            bool(verify_token),
            True,
            "Debe coincidir con el registrado en Meta Developers.",
        ),
        SettingStatus(
            "META_APP_SECRET",
            "App secret",
            "",
            bool(app_secret),
            True,
            "Se usa para validar la firma X-Hub-Signature-256.",
        ),
        SettingStatus(
            "META_ACCESS_TOKEN",
            "Access token",
            "",
            bool(access_token),
            True,
            "Token permanente o de sistema con permisos de WhatsApp.",
        ),
        SettingStatus(
            "META_APP_ID",
            "App ID",
            _masked(_setting("META_APP_ID"), 6),
            bool(_setting("META_APP_ID")),
            False,
            "Solo informativo: la API no lo necesita para enviar ni para recibir.",
            required=False,
        ),
        SettingStatus(
            "WHATSAPP_PHONE_NUMBER_ID",
            "Phone Number ID",
            _masked(phone_number_id, 5),
            bool(phone_number_id),
            False,
            "Identificador del número emisor en Meta.",
        ),
        SettingStatus(
            "WHATSAPP_API_VERSION",
            "Versión de la API",
            _setting("WHATSAPP_API_VERSION") or "v21.0",
            True,
            False,
        ),
        SettingStatus(
            "META_GRAPH_API_URL",
            "Graph API",
            _setting("META_GRAPH_API_URL"),
            bool(_setting("META_GRAPH_API_URL")),
            False,
        ),
        SettingStatus(
            "META_REQUEST_TIMEOUT",
            "Timeout (s)",
            _setting("META_REQUEST_TIMEOUT") or "10",
            True,
            False,
        ),
    ]


def capability_status() -> dict[str, Any]:
    """Resumen de lo que la integración puede y no puede hacer ahora mismo."""
    can_send = is_fully_configured()
    can_receive = can_receive_webhooks()
    statuses = setting_statuses()
    return {
        "can_send": can_send,
        "can_receive": can_receive,
        "can_verify": can_verify_subscription(),
        "webhook_path": WEBHOOK_PATH,
        # Solo las obligatorias: las opcionales se listan aparte para no
        # hacer creer que la integración está incompleta sin ellas.
        "missing": [
            status.name
            for status in statuses
            if not status.is_set and status.required
        ],
        "optional_missing": [
            status.name
            for status in statuses
            if not status.is_set and not status.required
        ],
        "statuses": statuses,
    }


def readiness_lines() -> list[tuple[str, bool, str]]:
    """Filas (etiqueta, ok, detalle) para el comando de diagnóstico."""
    lines: list[tuple[str, bool, str]] = []
    for status in setting_statuses():
        lines.append((f"{status.name:<25} {status.state:<15}", status.is_set, status.detail))

    lines.append(
        (
            f"{'Verificar suscripción':<25} {'disponible' if can_verify_subscription() else 'no disponible':<15}",
            can_verify_subscription(),
            "Meta puede validar el callback con GET.",
        )
    )
    lines.append(
        (
            f"{'Recibir webhooks':<25} {'disponible' if can_receive_webhooks() else 'no disponible':<15}",
            can_receive_webhooks(),
            "POST con firma X-Hub-Signature-256.",
        )
    )
    lines.append(
        (
            f"{'Enviar mensajes':<25} {'disponible' if is_fully_configured() else 'no disponible':<15}",
            is_fully_configured(),
            "Requiere META_ACCESS_TOKEN y WHATSAPP_PHONE_NUMBER_ID.",
        )
    )
    return lines
