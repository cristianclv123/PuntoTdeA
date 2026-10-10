"""Alta y seguimiento de plantillas en Meta WhatsApp Cloud API.

Meta es la fuente de verdad del estado de una plantilla, no el formulario
local: aquí se crea (``POST /{WABA}/message_templates``), se consulta su estado
(``GET /{template_id}`` o por nombre dentro de la WABA) y se traduce ese estado
al ``MessageTemplate.Status`` local. El modelo conserva además el id, el valor
crudo del estado y el motivo de rechazo para poder mostrarlos.

Solo lee ``django.conf.settings``; nunca registra el valor de un secreto.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

from ..models import MessageTemplate
from .meta_errors import explain


logger = logging.getLogger(__name__)


#: Categoría local -> categoría que espera Meta (en mayúsculas).
CATEGORY_TO_META = {
    MessageTemplate.Category.MARKETING: "MARKETING",
    MessageTemplate.Category.UTILITY: "UTILITY",
    MessageTemplate.Category.AUTHENTICATION: "AUTHENTICATION",
}

#: Estado que reporta Meta -> estado local. Los que no están aquí (PAUSED,
#: DISABLED, DELETED...) se guardan en ``meta_status`` tal cual y no pisan
#: ``status``.
META_TO_STATUS = {
    "APPROVED": MessageTemplate.Status.APPROVED,
    "REJECTED": MessageTemplate.Status.REJECTED,
    "PENDING": MessageTemplate.Status.PENDING,
    "IN_APPEAL": MessageTemplate.Status.PENDING,
    "PENDING_DELETION": MessageTemplate.Status.PENDING,
}

#: Muestras por tipo de variable. Meta exige un ejemplo por cada variable del
#: cuerpo para poder revisar la plantilla.
EXAMPLE_BY_TYPE = {
    "text": "Ejemplo",
    "number": "123",
    "date": "01/01/2026",
    "datetime": "01/01/2026 10:00",
}

#: Campos que se piden al consultar el estado de una plantilla.
STATUS_FIELDS = "id,name,status,category,rejected_reason"

#: Tipos de resultado, para que la vista elija el código HTTP correcto.
KIND_CONFIG = "config"
KIND_BUILD = "build"
KIND_META = "meta"
KIND_NOT_FOUND = "not_found"


class TemplateBuildError(ValueError):
    """La plantilla local no se puede traducir al formato de Meta."""


@dataclass
class TemplateSyncResult:
    ok: bool
    message: str = ""
    kind: str = ""
    meta_id: str = ""
    meta_status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


def _setting(name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


def is_configured() -> bool:
    """True cuando hay token y WABA: se puede crear/consultar plantillas."""
    return bool(_setting("META_ACCESS_TOKEN") and _setting("WHATSAPP_BUSINESS_ACCOUNT_ID"))


def _configuration_error() -> str:
    missing = [
        name
        for name in ("META_ACCESS_TOKEN", "WHATSAPP_BUSINESS_ACCOUNT_ID")
        if not _setting(name)
    ]
    if missing:
        return f"Falta configurar: {', '.join(missing)}."
    return ""


def _graph_url(path: str) -> str:
    root = str(settings.META_GRAPH_API_URL or "https://graph.facebook.com").rstrip("/")
    version = str(settings.WHATSAPP_API_VERSION or "v21.0")
    return f"{root}/{version}/{path.lstrip('/')}"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_setting('META_ACCESS_TOKEN')}",
        "Content-Type": "application/json",
    }


def _error_detail(response: requests.Response) -> str:
    try:
        error = response.json().get("error", {})
    except (TypeError, ValueError):
        return f"Meta respondió HTTP {response.status_code}."
    message = error.get("message") or "Error sin detalle."
    code = error.get("code")
    return f"[{code}] {message}" if code else message


def _variable_order(body: str) -> list[str]:
    """Números de variable en el orden en que aparecen en el cuerpo."""
    order: list[str] = []
    for match in re.finditer(r"\{\{(\d+)\}\}", body or ""):
        number = match.group(1)
        if number not in order:
            order.append(number)
    return order


def _body_example(template: MessageTemplate) -> dict[str, Any] | None:
    order = _variable_order(template.body_text)
    if not order:
        return None
    types = template.variable_types or {}
    samples = [
        EXAMPLE_BY_TYPE.get(str(types.get(number, "")), "Ejemplo")
        for number in order
    ]
    return {"body_text": [samples]}


def _meta_buttons(buttons: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for button in buttons or []:
        if not isinstance(button, dict):
            continue
        text = str(button.get("text", "")).strip()
        url = str(button.get("url", "")).strip()
        if text and url:
            result.append({"type": "URL", "text": text, "url": url})
    # Meta admite hasta 3 botones por plantilla.
    return result[:3]


def build_components(template: MessageTemplate) -> list[dict[str, Any]]:
    """Traduce la plantilla local a la lista ``components`` de Meta."""
    if template.header_type != MessageTemplate.HeaderType.NONE:
        raise TemplateBuildError(
            "Meta no permite crear encabezados de imagen, video o documento por "
            "API sin subir antes el archivo. Quita el encabezado o crea la "
            "plantilla directamente en WhatsApp Manager."
        )

    body: dict[str, Any] = {"type": "BODY", "text": template.body_text}
    example = _body_example(template)
    if example:
        body["example"] = example

    components: list[dict[str, Any]] = [body]
    buttons = _meta_buttons(template.buttons)
    if buttons:
        components.append({"type": "BUTTONS", "buttons": buttons})
    return components


def build_payload(template: MessageTemplate) -> dict[str, Any]:
    return {
        "name": template.meta_template_name,
        "language": template.language,
        "category": CATEGORY_TO_META.get(template.category, "UTILITY"),
        "components": build_components(template),
    }


def apply_meta_status(
    template: MessageTemplate,
    *,
    meta_id: str = "",
    meta_status: str = "",
    rejection_reason: str | None = None,
) -> MessageTemplate:
    """Vuelca la respuesta de Meta en el modelo y traduce el estado."""
    if meta_id:
        template.meta_template_id = meta_id
    if meta_status:
        template.meta_status = meta_status
    if rejection_reason is not None:
        template.meta_rejection_reason = rejection_reason

    mapped = META_TO_STATUS.get((meta_status or "").upper())
    if mapped:
        template.status = mapped

    template.meta_synced_at = timezone.now()
    template.save()
    return template


def create_template(template: MessageTemplate) -> TemplateSyncResult:
    """Crea la plantilla en Meta y guarda id + estado devueltos."""
    error = _configuration_error()
    if error:
        return TemplateSyncResult(ok=False, message=error, kind=KIND_CONFIG)

    if template.meta_template_id:
        return TemplateSyncResult(
            ok=False,
            message="Esta plantilla ya fue enviada a Meta. Consulta su estado.",
            kind=KIND_BUILD,
        )

    try:
        payload = build_payload(template)
    except TemplateBuildError as exc:
        return TemplateSyncResult(ok=False, message=str(exc), kind=KIND_BUILD)

    try:
        response = requests.post(
            _graph_url(f"{_setting('WHATSAPP_BUSINESS_ACCOUNT_ID')}/message_templates"),
            headers=_headers(),
            json=payload,
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("No se pudo crear la plantilla %s en Meta: %s", template.pk, exc)
        return TemplateSyncResult(ok=False, message=explain(str(exc)), kind=KIND_META)

    if response.status_code >= 400:
        detail = _error_detail(response)
        logger.warning("Meta rechazó la plantilla %s: %s", template.pk, detail)
        return TemplateSyncResult(ok=False, message=explain(detail), kind=KIND_META)

    try:
        data = response.json() or {}
    except ValueError:
        data = {}

    meta_id = str(data.get("id", "") or "")
    meta_status = str(data.get("status", "") or "PENDING")
    apply_meta_status(
        template, meta_id=meta_id, meta_status=meta_status, rejection_reason=""
    )
    return TemplateSyncResult(
        ok=True,
        message=f"Plantilla enviada a Meta. Estado: {meta_status}.",
        meta_id=meta_id,
        meta_status=meta_status,
        raw=data,
    )


def _result_from_data(
    template: MessageTemplate, data: dict[str, Any]
) -> TemplateSyncResult:
    meta_id = str(data.get("id", "") or template.meta_template_id)
    meta_status = str(data.get("status", "") or "")
    rejection_reason = str(data.get("rejected_reason", "") or "")
    # Meta responde "NONE" cuando no hay rechazo: no es un motivo real.
    if rejection_reason.strip().upper() in {"", "NONE"}:
        rejection_reason = ""
    apply_meta_status(
        template,
        meta_id=meta_id,
        meta_status=meta_status,
        rejection_reason=rejection_reason,
    )
    return TemplateSyncResult(
        ok=True,
        message=f"Estado actualizado: {meta_status or 'sin estado'}.",
        meta_id=meta_id,
        meta_status=meta_status,
        raw=data,
    )


def fetch_template_status(template: MessageTemplate) -> TemplateSyncResult:
    """Consulta a Meta el estado actual de la plantilla y lo guarda."""
    error = _configuration_error()
    if error:
        return TemplateSyncResult(ok=False, message=error, kind=KIND_CONFIG)

    if template.meta_template_id:
        url = _graph_url(template.meta_template_id)
        params = {"fields": STATUS_FIELDS}
    else:
        # Plantilla creada directamente en Meta: se busca por nombre.
        url = _graph_url(f"{_setting('WHATSAPP_BUSINESS_ACCOUNT_ID')}/message_templates")
        params = {"name": template.meta_template_name, "fields": STATUS_FIELDS}

    try:
        response = requests.get(
            url,
            headers=_headers(),
            params=params,
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning(
            "No se pudo consultar el estado de la plantilla %s: %s", template.pk, exc
        )
        return TemplateSyncResult(ok=False, message=explain(str(exc)), kind=KIND_META)

    if response.status_code >= 400:
        detail = _error_detail(response)
        logger.warning("Meta no devolvió el estado de la plantilla %s: %s", template.pk, detail)
        return TemplateSyncResult(ok=False, message=explain(detail), kind=KIND_META)

    try:
        data = response.json() or {}
    except ValueError:
        return TemplateSyncResult(
            ok=False,
            message="Meta devolvió una respuesta ilegible.",
            kind=KIND_META,
        )

    if not template.meta_template_id:
        entries = data.get("data") or []
        if not entries:
            return TemplateSyncResult(
                ok=False,
                message=(
                    "Meta no tiene una plantilla con ese nombre en la cuenta. "
                    "Envíala primero desde aquí."
                ),
                kind=KIND_NOT_FOUND,
            )
        data = entries[0]

    return _result_from_data(template, data)


def refresh_linked(limit: int = 50) -> list[tuple[MessageTemplate, TemplateSyncResult]]:
    """Consulta el estado de las plantillas ya enlazadas con Meta.

    Solo toca las que tienen ``meta_template_id``: las que nunca se enviaron
    todavía no existen en Meta.
    """
    results: list[tuple[MessageTemplate, TemplateSyncResult]] = []
    queryset = (
        MessageTemplate.objects.exclude(meta_template_id="")
        .order_by("-updated_at")[:limit]
    )
    for template in queryset:
        results.append((template, fetch_template_status(template)))
    return results
