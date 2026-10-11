"""Integración con las plantillas de Meta WhatsApp Cloud API.

Meta es la fuente de verdad de las plantillas: aquí se listan
(``GET /{WABA}/message_templates``), se consulta una
(``GET /{template_id}``), se crean (``POST /{WABA}/message_templates``), se
editan (``POST /{template_id}``) y se eliminan
(``DELETE /{WABA}/message_templates?hsm_id=...``).

La base local solo guarda borradores; al crear una plantilla a partir de un
borrador, el borrador se elimina y la plantilla pasa a vivir únicamente en
Meta. Por eso este módulo nunca escribe estado en el modelo local: devuelve
diccionarios normalizados que la vista consume.

Solo lee ``django.conf.settings``; nunca registra el valor de un secreto.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

import requests
from django.conf import settings

from .meta_errors import explain


logger = logging.getLogger(__name__)


#: Idioma con el que se crean las plantillas desde PuntoTdeA.
META_LANGUAGE = "es_CO"

#: Categoría local -> categoría que espera Meta (en mayúsculas).
CATEGORY_TO_META = {
    "marketing": "MARKETING",
    "utility": "UTILITY",
    "authentication": "AUTHENTICATION",
}

#: Campos que se piden a Meta al listar o consultar una plantilla.
TEMPLATE_FIELDS = "id,name,status,category,language,rejected_reason,components"

#: Muestras por tipo de variable. Meta exige un ejemplo por cada variable del
#: cuerpo para poder revisar la plantilla.
EXAMPLE_BY_TYPE = {
    "text": "Ejemplo",
    "number": "123",
    "date": "01/01/2026",
    "datetime": "01/01/2026 10:00",
}

#: Tipos de resultado, para que la vista elija el código HTTP correcto.
KIND_CONFIG = "config"
KIND_BUILD = "build"
KIND_META = "meta"
KIND_NOT_FOUND = "not_found"


class TemplateBuildError(ValueError):
    """La plantilla local no se puede traducir al formato de Meta."""


@dataclass
class TemplateResult:
    """Resultado de una operación sobre una sola plantilla de Meta."""

    ok: bool
    message: str = ""
    kind: str = ""
    meta_id: str = ""
    meta_status: str = ""
    template: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateListResult:
    """Resultado de listar las plantillas de la cuenta de Meta."""

    ok: bool
    message: str = ""
    kind: str = ""
    templates: list[dict[str, Any]] = field(default_factory=list)


def _setting(name: str) -> str:
    return str(getattr(settings, name, "") or "").strip()


def is_configured() -> bool:
    """True cuando hay token y WABA: se puede operar con plantillas en Meta."""
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


def _body_example(body_text: str, variable_types: dict | None) -> dict[str, Any] | None:
    order = _variable_order(body_text)
    if not order:
        return None
    types = variable_types or {}
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


def slugify_meta_name(name: str) -> str:
    """Convierte un nombre libre en el slug que exige Meta (``[a-z0-9_]``)."""
    normalized = unicodedata.normalize("NFKD", str(name or ""))
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")
    return (slug or "plantilla")[:512]


def build_components(
    body_text: str,
    variable_types: dict | None = None,
    buttons: Any = None,
    header_type: str = "none",
) -> list[dict[str, Any]]:
    """Traduce los campos de una plantilla a la lista ``components`` de Meta."""
    if header_type and header_type != "none":
        raise TemplateBuildError(
            "Meta no permite crear encabezados de imagen, video o documento por "
            "API sin subir antes el archivo. Quita el encabezado o crea la "
            "plantilla directamente en WhatsApp Manager."
        )

    body: dict[str, Any] = {"type": "BODY", "text": body_text}
    example = _body_example(body_text, variable_types)
    if example:
        body["example"] = example

    components: list[dict[str, Any]] = [body]
    meta_buttons = _meta_buttons(buttons)
    if meta_buttons:
        components.append({"type": "BUTTONS", "buttons": meta_buttons})
    return components


def build_payload(
    name: str, language: str, category: str, components: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "name": name,
        "language": language or META_LANGUAGE,
        "category": CATEGORY_TO_META.get(str(category or "").lower(), "UTILITY"),
        "components": components,
    }


def normalize_meta_template(data: dict[str, Any]) -> dict[str, Any]:
    """Convierte la respuesta cruda de Meta en un diccionario uniforme.

    Se usa tanto para el listado como para el detalle y para el resultado de
    una edición, de modo que la interfaz siempre recibe la misma forma.
    """
    body_text = ""
    header_type = "none"
    buttons: list[dict[str, str]] = []
    for component in data.get("components") or []:
        if not isinstance(component, dict):
            continue
        component_type = str(component.get("type", "")).upper()
        if component_type == "BODY":
            body_text = component.get("text") or ""
        elif component_type == "HEADER":
            fmt = str(component.get("format", "")).upper()
            header_type = {
                "IMAGE": "image",
                "VIDEO": "video",
                "DOCUMENT": "document",
            }.get(fmt, "none")
        elif component_type == "BUTTONS":
            for button in component.get("buttons") or []:
                if not isinstance(button, dict):
                    continue
                button_type = str(button.get("type", "")).upper()
                if button_type in {"URL", "QUICK_REPLY"}:
                    buttons.append(
                        {
                            "text": str(button.get("text", "")),
                            "url": str(button.get("url", "")),
                        }
                    )

    rejection_reason = str(data.get("rejected_reason", "") or "")
    # Meta responde "NONE" cuando no hay rechazo: no es un motivo real.
    if rejection_reason.strip().upper() in {"", "NONE"}:
        rejection_reason = ""

    order = _variable_order(body_text)
    return {
        "meta_id": str(data.get("id", "") or ""),
        "name": str(data.get("name", "") or ""),
        "status": str(data.get("status", "") or "").upper(),
        "category": str(data.get("category", "") or "").lower(),
        "language": str(data.get("language", "") or META_LANGUAGE),
        "rejected_reason": rejection_reason,
        "body_text": body_text,
        "header_type": header_type,
        "buttons": buttons,
        "indexes": [int(number) for number in order],
        "param_count": len(order),
    }


def to_template_ref(template: dict[str, Any]):
    """Construye un ``TemplateRef`` envíable a partir de una plantilla de Meta."""
    from ..adapters.base import TemplateRef

    return TemplateRef(
        name=str(template.get("name", "") or ""),
        language=str(template.get("language", "") or META_LANGUAGE),
        body_text=str(template.get("body_text", "") or ""),
        header_type=str(template.get("header_type", "") or "none"),
        header_media_url=str(template.get("header_media_url", "") or ""),
    )


def list_templates() -> TemplateListResult:
    """Lista las plantillas de la WABA configurada."""
    error = _configuration_error()
    if error:
        return TemplateListResult(ok=False, message=error, kind=KIND_CONFIG)

    try:
        response = requests.get(
            _graph_url(f"{_setting('WHATSAPP_BUSINESS_ACCOUNT_ID')}/message_templates"),
            headers=_headers(),
            params={"fields": TEMPLATE_FIELDS, "limit": 200},
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("No se pudo listar las plantillas de Meta: %s", exc)
        return TemplateListResult(ok=False, message=explain(str(exc)), kind=KIND_META)

    if response.status_code >= 400:
        detail = _error_detail(response)
        logger.warning("Meta no devolvió las plantillas: %s", detail)
        return TemplateListResult(ok=False, message=explain(detail), kind=KIND_META)

    try:
        data = response.json() or {}
    except ValueError:
        return TemplateListResult(
            ok=False, message="Meta devolvió una respuesta ilegible.", kind=KIND_META
        )

    templates = [normalize_meta_template(item) for item in data.get("data") or []]
    return TemplateListResult(ok=True, templates=templates)


def get_template(meta_id: str) -> TemplateResult:
    """Consulta una plantilla concreta por su id de Meta."""
    error = _configuration_error()
    if error:
        return TemplateResult(ok=False, message=error, kind=KIND_CONFIG)

    try:
        response = requests.get(
            _graph_url(meta_id),
            headers=_headers(),
            params={"fields": TEMPLATE_FIELDS},
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("No se pudo consultar la plantilla %s en Meta: %s", meta_id, exc)
        return TemplateResult(ok=False, message=explain(str(exc)), kind=KIND_META)

    if response.status_code >= 400:
        detail = _error_detail(response)
        logger.warning("Meta no devolvió la plantilla %s: %s", meta_id, detail)
        return TemplateResult(ok=False, message=explain(detail), kind=KIND_META)

    try:
        data = response.json() or {}
    except ValueError:
        return TemplateResult(
            ok=False, message="Meta devolvió una respuesta ilegible.", kind=KIND_META
        )

    template = normalize_meta_template(data)
    return TemplateResult(
        ok=True,
        message="Plantilla consultada.",
        meta_id=template["meta_id"],
        meta_status=template["status"],
        template=template,
        raw=data,
    )


def create_from_draft(draft, meta_name: str = "") -> TemplateResult:
    """Crea en Meta la plantilla descrita por un borrador local."""
    error = _configuration_error()
    if error:
        return TemplateResult(ok=False, message=error, kind=KIND_CONFIG)

    try:
        components = build_components(
            draft.body_text,
            draft.variable_types,
            draft.buttons,
            draft.header_type,
        )
    except TemplateBuildError as exc:
        return TemplateResult(ok=False, message=str(exc), kind=KIND_BUILD)

    name = slugify_meta_name(meta_name or draft.name)
    payload = build_payload(name, META_LANGUAGE, draft.category, components)

    try:
        response = requests.post(
            _graph_url(f"{_setting('WHATSAPP_BUSINESS_ACCOUNT_ID')}/message_templates"),
            headers=_headers(),
            json=payload,
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("No se pudo crear la plantilla %s en Meta: %s", draft.pk, exc)
        return TemplateResult(ok=False, message=explain(str(exc)), kind=KIND_META)

    if response.status_code >= 400:
        detail = _error_detail(response)
        logger.warning("Meta rechazó la plantilla %s: %s", draft.pk, detail)
        return TemplateResult(ok=False, message=explain(detail), kind=KIND_META)

    try:
        data = response.json() or {}
    except ValueError:
        data = {}

    meta_id = str(data.get("id", "") or "")
    meta_status = str(data.get("status", "") or "PENDING")
    return TemplateResult(
        ok=True,
        message=f"Plantilla enviada a Meta. Estado: {meta_status}.",
        meta_id=meta_id,
        meta_status=meta_status,
        raw=data,
    )


def edit_template(
    meta_id: str,
    body_text: str,
    variable_types: dict | None = None,
    buttons: Any = None,
    header_type: str = "none",
) -> TemplateResult:
    """Edita una plantilla existente en Meta (``POST /{template_id}``).

    Meta solo permite editar plantillas ``APPROVED``, ``REJECTED`` o
    ``PAUSED`` y reabre la revisión automáticamente. No se puede cambiar la
    categoría de una plantilla aprobada: por eso aquí solo van los componentes.
    """
    error = _configuration_error()
    if error:
        return TemplateResult(ok=False, message=error, kind=KIND_CONFIG)

    try:
        components = build_components(body_text, variable_types, buttons, header_type)
    except TemplateBuildError as exc:
        return TemplateResult(ok=False, message=str(exc), kind=KIND_BUILD)

    try:
        response = requests.post(
            _graph_url(meta_id),
            headers=_headers(),
            json={"components": components},
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("No se pudo editar la plantilla %s en Meta: %s", meta_id, exc)
        return TemplateResult(ok=False, message=explain(str(exc)), kind=KIND_META)

    if response.status_code >= 400:
        detail = _error_detail(response)
        logger.warning("Meta rechazó la edición de la plantilla %s: %s", meta_id, detail)
        return TemplateResult(ok=False, message=explain(detail), kind=KIND_META)

    try:
        data = response.json() or {}
    except ValueError:
        data = {}

    return TemplateResult(
        ok=True,
        message="Plantilla actualizada en Meta. Volverá a revisión.",
        meta_id=meta_id,
        meta_status=str(data.get("status", "") or ""),
        raw=data,
    )


def delete_template(meta_id: str, name: str = "") -> TemplateResult:
    """Elimina una plantilla de Meta (``DELETE /{WABA}/message_templates``)."""
    error = _configuration_error()
    if error:
        return TemplateResult(ok=False, message=error, kind=KIND_CONFIG)

    params: dict[str, str] = {"hsm_id": meta_id}
    if name:
        params["name"] = name

    try:
        response = requests.delete(
            _graph_url(f"{_setting('WHATSAPP_BUSINESS_ACCOUNT_ID')}/message_templates"),
            headers=_headers(),
            params=params,
            timeout=settings.META_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("No se pudo eliminar la plantilla %s en Meta: %s", meta_id, exc)
        return TemplateResult(ok=False, message=explain(str(exc)), kind=KIND_META)

    if response.status_code >= 400:
        detail = _error_detail(response)
        logger.warning("Meta rechazó la eliminación de la plantilla %s: %s", meta_id, detail)
        return TemplateResult(ok=False, message=explain(detail), kind=KIND_META)

    return TemplateResult(ok=True, message="Plantilla eliminada de Meta.", meta_id=meta_id)
