"""Cliente de Meta Marketing API para anuncios en WhatsApp Status.

Este es el unico punto del proyecto que habla con la Marketing API. La
mensajeria de WhatsApp (plantillas y chatbot) vive en los adapters; aqui solo
se gestionan campanas, ad sets, creativos y anuncios.

Notas de la integracion:
- El "WhatsApp Status" (historias) es un placement de anuncios, no un envio de
  mensajes. Exige `publisher_platforms=[instagram, whatsapp]`,
  `instagram_positions=[story]` y `whatsapp_positions=[status]`.
- Requiere un token de usuario con `ads_management` (el token de sistema de
  WhatsApp no sirve) y que la Pagina este vinculada a la cuenta de WhatsApp.
- Por defecto todo se crea en PAUSED para probar sin gastar presupuesto.

Ver `docs/anuncios-status-whatsapp.md` para el procedimiento completo.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import requests
from django.conf import settings

from ..models import Contact

logger = logging.getLogger(__name__)

# Placement de anuncios en WhatsApp Status. Es la razon de ser de este modulo.
DEFAULT_STATUS_PLACEMENT: dict[str, Any] = {
    "publisher_platforms": ["instagram", "whatsapp"],
    "instagram_positions": ["story"],
    "whatsapp_positions": ["status"],
    "user_age_unknown": False,
}

DEFAULT_COUNTRIES = ["CO"]
DEFAULT_OBJECTIVE = "OUTCOME_ENGAGEMENT"
DEFAULT_BID_STRATEGY = "LOWEST_COST_WITHOUT_CAP"
DEFAULT_OPTIMIZATION_GOAL = "CONVERSATIONS"
DEFAULT_BILLING_EVENT = "IMPRESSIONS"
DEFAULT_DESTINATION_TYPE = "WHATSAPP"
DEFAULT_CTA_TYPE = "WHATSAPP_MESSAGE"
DEFAULT_CTA_LINK = "https://api.whatsapp.com/send"

PHONE_BATCH_SIZE = 5000

AD_ACCOUNT_STATUS = {
    1: "ACTIVA",
    2: "INHABILITADA",
    3: "SIN CONFIRMAR",
    7: "EN REVISION",
    9: "GRACIA",
    101: "CERRADA",
}


@dataclass
class AdsResult:
    """Resultado uniforme de cualquier llamada a la Marketing API."""

    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def object_id(self) -> str:
        return str(self.data.get("id") or "")


# --------------------------------------------------------------------------- #
# Configuracion
# --------------------------------------------------------------------------- #
def _api_version() -> str:
    return str(getattr(settings, "WHATSAPP_API_VERSION", "") or "v21.0")


def _base_url() -> str:
    return f"{settings.META_GRAPH_API_URL.rstrip('/')}/{_api_version()}"


def access_token() -> str:
    return str(getattr(settings, "META_ADS_ACCESS_TOKEN", "") or "").strip()


def ad_account_id() -> str:
    value = str(getattr(settings, "META_AD_ACCOUNT_ID", "") or "").strip()
    if value and not value.startswith("act_"):
        value = f"act_{value}"
    return value


def page_id() -> str:
    return str(getattr(settings, "META_FB_PAGE_ID", "") or "").strip()


def whatsapp_phone() -> str:
    return normalize_phone(getattr(settings, "META_WHATSAPP_PHONE", ""))


def configuration_errors() -> list[str]:
    """Nombres de las variables de anuncios que faltan."""
    checks = {
        "META_ADS_ACCESS_TOKEN": access_token(),
        "META_AD_ACCOUNT_ID": ad_account_id(),
        "META_FB_PAGE_ID": page_id(),
        "META_WHATSAPP_PHONE": whatsapp_phone(),
    }
    return [name for name, value in checks.items() if not value]


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def normalize_phone(phone: str) -> str:
    """Deja solo digitos (formato E.164 sin '+'), como espera Meta."""
    return re.sub(r"\D", "", phone or "")


def hash_phone(phone: str) -> str:
    """SHA-256 del telefono normalizado, requisito de las audiencias."""
    return hashlib.sha256(normalize_phone(phone).encode("utf-8")).hexdigest()


def build_targeting(
    *,
    countries: Sequence[str] | None = None,
    custom_audiences: Sequence[str] | None = None,
    advantage_audience: bool = False,
    age_min: int | None = None,
    age_max: int | None = None,
    genders: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Placement de Status + geografia + audiencia personalizada opcional.

    `advantage_audience=True` deja que Meta amplie la entrega mas alla de la
    lista ("lista + publico amplio"); en False se limita a la lista.
    """
    targeting: dict[str, Any] = {**DEFAULT_STATUS_PLACEMENT}
    targeting["geo_locations"] = {"countries": list(countries or DEFAULT_COUNTRIES)}
    if age_min is not None or age_max is not None:
        targeting["age_min"] = age_min or 18
        targeting["age_max"] = age_max or 65
    if genders:
        targeting["genders"] = list(genders)
    if custom_audiences:
        targeting["custom_audiences"] = [{"id": str(a)} for a in custom_audiences]
        targeting["targeting_automation"] = {
            "advantage_audience": 1 if advantage_audience else 0
        }
    return targeting


def phones_from_segment(segment, *, only_subscribed: bool = True) -> list[str]:
    """Telefonos normalizados de un AudienceSegment (por defecto suscritos)."""
    contacts = segment.contacts.all()
    if only_subscribed:
        contacts = contacts.filter(whatsapp_opt_in=Contact.OptInStatus.SUSCRITO)
    phones = {
        normalize_phone(phone)
        for phone in contacts.values_list("phone", flat=True)
        if normalize_phone(phone)
    }
    return sorted(phones)


# --------------------------------------------------------------------------- #
# Transporte
# --------------------------------------------------------------------------- #
def _graph_error(response: requests.Response | None, exc: Exception) -> str:
    if response is not None:
        try:
            error = response.json().get("error", {})
        except (TypeError, ValueError):
            detail = (response.text or "")[:300]
            if detail:
                return f"Meta Marketing API: {detail}"
            error = {}
        bits: list[str] = []
        message = error.get("message", "")
        if message:
            bits.append(str(message))
        for key in ("error_user_title", "error_user_msg"):
            value = error.get(key)
            if value and str(value) not in bits:
                bits.append(str(value))
        error_data = error.get("error_data")
        if isinstance(error_data, dict):
            blame = error_data.get("blame_field_specs") or error_data.get("blame_field")
            if blame:
                bits.append(f"campo: {blame}")
        if bits:
            text = " - ".join(bits)
            code = error.get("code")
            subcode = error.get("error_subcode")
            if code:
                text += f" (code {code}"
                if subcode:
                    text += f", subcode {subcode}"
                text += ")"
            return f"Meta Marketing API: {text}"
    return f"Meta Marketing API: {exc}"


def _call(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    token: str | None = None,
) -> tuple[bool, dict[str, Any], str]:
    """Llama a la Graph API y devuelve (ok, cuerpo, error)."""
    if not (token or access_token()):
        return False, {}, "Meta Marketing API: falta META_ADS_ACCESS_TOKEN."
    query = dict(params or {})
    query.setdefault("access_token", token or access_token())
    url = f"{_base_url()}/{path.lstrip('/')}"
    response = None
    try:
        response = requests.request(
            method,
            url,
            params=query,
            data=data,
            json=json_body,
            files=files,
            timeout=settings.META_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        return False, {}, _graph_error(response, exc)
    if not isinstance(body, dict):
        return False, {}, "Meta Marketing API: respuesta inesperada."
    return True, body, ""


# --------------------------------------------------------------------------- #
# Diagnostico
# --------------------------------------------------------------------------- #
def debug_token() -> AdsResult:
    """Valida el token de anuncios usando el token de app (app_id|app_secret)."""
    app_id = str(getattr(settings, "META_APP_ID", "") or "")
    app_secret = str(getattr(settings, "META_APP_SECRET", "") or "")
    if not (app_id and app_secret):
        return AdsResult(False, "Falta META_APP_ID/META_APP_SECRET para validar.", error="configuracion")
    ok, body, error = _call(
        "GET",
        "debug_token",
        params={"input_token": access_token()},
        token=f"{app_id}|{app_secret}",
    )
    if not ok:
        return AdsResult(False, "No se pudo validar el token de anuncios.", error=error)
    return AdsResult(True, "Token de anuncios validado.", {"token": body.get("data", {})})


def get_ad_account(fields: str = "id,name,account_status,currency,timezone_name,disable_reason") -> AdsResult:
    ok, body, error = _call("GET", ad_account_id(), params={"fields": fields})
    if not ok:
        return AdsResult(False, "No se pudo leer la cuenta de anuncios.", error=error)
    status = body.get("account_status")
    body["account_status_label"] = AD_ACCOUNT_STATUS.get(status, str(status))
    return AdsResult(True, "Cuenta de anuncios leida.", {"account": body})


def get_page(fields: str = "id,name,is_published") -> AdsResult:
    ok, body, error = _call("GET", page_id(), params={"fields": fields})
    if not ok:
        return AdsResult(False, "No se pudo leer la Pagina.", error=error)
    return AdsResult(True, "Pagina leida.", {"page": body})


def get_business(fields: str = "id,name,verification_status") -> AdsResult:
    business_id = str(getattr(settings, "META_BUSINESS_ID", "") or "").strip()
    if not business_id:
        return AdsResult(False, "Falta META_BUSINESS_ID.", error="configuracion")
    ok, body, error = _call("GET", business_id, params={"fields": fields})
    if not ok:
        return AdsResult(False, "No se pudo leer el portafolio de negocio.", error=error)
    return AdsResult(True, "Portafolio leido.", {"business": body})


# --------------------------------------------------------------------------- #
# Audiencias personalizadas
# --------------------------------------------------------------------------- #
def create_custom_audience(
    name: str,
    *,
    description: str = "",
    customer_file_source: str = "USER_PROVIDED_ONLY",
    retention_days: int | None = None,
) -> AdsResult:
    payload: dict[str, Any] = {
        "name": name,
        "subtype": "CUSTOM",
        "customer_file_source": customer_file_source,
    }
    if description:
        payload["description"] = description
    if retention_days:
        payload["retention_days"] = int(retention_days)
    ok, body, error = _call("POST", f"{ad_account_id()}/customaudiences", data=payload)
    if not ok:
        return AdsResult(False, "No se pudo crear la audiencia personalizada.", error=error)
    audience_id = str(body.get("id") or "")
    if not audience_id:
        return AdsResult(False, "Meta no devolvio el id de la audiencia.", error="sin id")
    return AdsResult(True, f"Audiencia creada: {audience_id}", {"id": audience_id, "response": body})


def add_phones_to_audience(
    audience_id: str, phones: Iterable[str], *, batch_size: int = PHONE_BATCH_SIZE
) -> AdsResult:
    """Carga telefonos (ya normalizados o crudos) hasheados SHA-256."""
    normalized = [normalize_phone(p) for p in (phones or [])]
    normalized = [p for p in normalized if p]
    if not normalized:
        return AdsResult(False, "No hay telefonos para cargar.", error="sin datos")
    added = 0
    for start in range(0, len(normalized), batch_size):
        batch = normalized[start : start + batch_size]
        payload = json.dumps(
            {"schema": ["PHONE"], "data": [[hash_phone(p)] for p in batch]}
        )
        ok, _body, error = _call("POST", f"{audience_id}/users", data={"payload": payload})
        if not ok:
            return AdsResult(
                False,
                f"Fallo al cargar {len(batch)} telefonos en la audiencia.",
                {"id": str(audience_id), "added": added},
                error,
            )
        added += len(batch)
    return AdsResult(
        True,
        f"{added} telefonos cargados en la audiencia {audience_id}.",
        {"id": str(audience_id), "added": added},
    )


# --------------------------------------------------------------------------- #
# Campana / ad set / creativo / anuncio
# --------------------------------------------------------------------------- #
def create_campaign(
    name: str,
    *,
    objective: str = DEFAULT_OBJECTIVE,
    status: str = "PAUSED",
    special_ad_categories: Sequence[str] | None = None,
    is_adset_budget_sharing_enabled: bool = False,
) -> AdsResult:
    payload = {
        "name": name,
        "objective": objective,
        "status": status,
        "special_ad_categories": json.dumps(list(special_ad_categories or [])),
        "is_adset_budget_sharing_enabled": json.dumps(bool(is_adset_budget_sharing_enabled)),
    }
    ok, body, error = _call("POST", f"{ad_account_id()}/campaigns", data=payload)
    if not ok:
        return AdsResult(False, "No se pudo crear la campana.", error=error)
    campaign_id = str(body.get("id") or "")
    if not campaign_id:
        return AdsResult(False, "Meta no devolvio el id de la campana.", error="sin id")
    return AdsResult(
        True, f"Campana creada en {status}: {campaign_id}",
        {"id": campaign_id, "response": body},
    )


def create_status_ad_set(
    campaign_id: str,
    *,
    name: str,
    daily_budget: int,
    page_id_value: str = "",
    whatsapp_phone_value: str = "",
    countries: Sequence[str] | None = None,
    custom_audiences: Sequence[str] | None = None,
    advantage_audience: bool = False,
    age_min: int | None = None,
    age_max: int | None = None,
    genders: Sequence[int] | None = None,
    status: str = "PAUSED",
    bid_strategy: str = DEFAULT_BID_STRATEGY,
    optimization_goal: str = DEFAULT_OPTIMIZATION_GOAL,
    billing_event: str = DEFAULT_BILLING_EVENT,
    destination_type: str = DEFAULT_DESTINATION_TYPE,
) -> AdsResult:
    page = str(page_id_value or page_id()).strip()
    phone = normalize_phone(whatsapp_phone_value or whatsapp_phone())
    if not page:
        return AdsResult(False, "Falta el id de la Pagina.", error="configuracion")
    if not phone:
        return AdsResult(False, "Falta el numero de WhatsApp para el anuncio.", error="configuracion")

    promoted_object = {"page_id": page, "whatsapp_phone_number": phone}
    targeting = build_targeting(
        countries=countries,
        custom_audiences=custom_audiences,
        advantage_audience=advantage_audience,
        age_min=age_min,
        age_max=age_max,
        genders=genders,
    )
    payload = {
        "name": name,
        "campaign_id": str(campaign_id),
        "optimization_goal": optimization_goal,
        "billing_event": billing_event,
        "bid_strategy": bid_strategy,
        "destination_type": destination_type,
        "promoted_object": json.dumps(promoted_object),
        "targeting": json.dumps(targeting),
        "status": status,
        "daily_budget": int(daily_budget),
    }
    ok, body, error = _call("POST", f"{ad_account_id()}/adsets", data=payload)
    if not ok:
        return AdsResult(False, "No se pudo crear el ad set.", error=error)
    ad_set_id = str(body.get("id") or "")
    if not ad_set_id:
        return AdsResult(False, "Meta no devolvio el id del ad set.", error="sin id")
    return AdsResult(
        True, f"Ad set creado en {status}: {ad_set_id}",
        {"id": ad_set_id, "response": body, "targeting": targeting, "promoted_object": promoted_object},
    )


def upload_ad_image(image: Any, *, name: str = "") -> AdsResult:
    """Sube una imagen (ruta en disco o archivo abierto) y devuelve su hash."""
    close_after = not hasattr(image, "read")
    file_obj = image
    filename = name or "aviso.jpg"
    try:
        if close_after:
            file_obj = open(str(image), "rb")
            filename = name or os.path.basename(str(image))
        else:
            filename = name or getattr(image, "name", "aviso.jpg") or "aviso.jpg"
        data = {"name": filename}
        ok, body, error = _call(
            "POST",
            f"{ad_account_id()}/adimages",
            data=data,
            files={"filename": (filename, file_obj)},
        )
    except OSError as exc:
        return AdsResult(False, "No se pudo abrir la imagen.", error=str(exc))
    finally:
        if close_after and hasattr(file_obj, "close"):
            file_obj.close()

    if not ok:
        return AdsResult(False, "No se pudo subir la imagen.", error=error)
    images = body.get("images") or {}
    image_hash = ""
    for meta in images.values():
        if isinstance(meta, dict) and meta.get("hash"):
            image_hash = str(meta["hash"])
            break
    if not image_hash:
        return AdsResult(False, "Meta no devolvio el hash de la imagen.", error="sin hash")
    return AdsResult(True, f"Imagen subida: {image_hash}", {"id": image_hash, "hash": image_hash, "response": body})


def create_status_ad_creative(
    *,
    name: str,
    message: str,
    image_hash: str = "",
    title: str = "",
    link: str = DEFAULT_CTA_LINK,
    page_id_value: str = "",
    instagram_actor_id: str = "",
    cta_type: str = DEFAULT_CTA_TYPE,
    page_welcome_message: str = "",
) -> AdsResult:
    page = str(page_id_value or page_id()).strip()
    if not page:
        return AdsResult(False, "Falta el id de la Pagina.", error="configuracion")
    link_data: dict[str, Any] = {
        "link": link,
        "message": message,
        "call_to_action": {"type": cta_type, "value": {"app_destination": "WHATSAPP"}},
    }
    if image_hash:
        link_data["image_hash"] = image_hash
    if title:
        link_data["name"] = title
    object_story_spec: dict[str, Any] = {"page_id": page, "link_data": link_data}
    if instagram_actor_id:
        object_story_spec["instagram_actor_id"] = str(instagram_actor_id)
    payload: dict[str, Any] = {
        "name": name,
        "object_story_spec": json.dumps(object_story_spec),
    }
    if page_welcome_message:
        payload["page_welcome_message"] = page_welcome_message
    ok, body, error = _call("POST", f"{ad_account_id()}/adcreatives", data=payload)
    if not ok:
        return AdsResult(False, "No se pudo crear el creativo.", error=error)
    creative_id = str(body.get("id") or "")
    if not creative_id:
        return AdsResult(False, "Meta no devolvio el id del creativo.", error="sin id")
    return AdsResult(True, f"Creativo creado: {creative_id}", {"id": creative_id, "response": body})


def create_ad(
    *, name: str, ad_set_id: str, creative_id: str, status: str = "PAUSED"
) -> AdsResult:
    payload = {
        "name": name,
        "adset_id": str(ad_set_id),
        "creative": json.dumps({"creative_id": str(creative_id)}),
        "status": status,
    }
    ok, body, error = _call("POST", f"{ad_account_id()}/ads", data=payload)
    if not ok:
        return AdsResult(False, "No se pudo crear el anuncio.", error=error)
    ad_id = str(body.get("id") or "")
    if not ad_id:
        return AdsResult(False, "Meta no devolvio el id del anuncio.", error="sin id")
    return AdsResult(True, f"Anuncio creado en {status}: {ad_id}", {"id": ad_id, "response": body})


def create_status_ad(
    *,
    name: str,
    message: str,
    daily_budget: int,
    image: Any = None,
    image_hash: str = "",
    title: str = "",
    countries: Sequence[str] | None = None,
    custom_audiences: Sequence[str] | None = None,
    advantage_audience: bool = False,
    status: str = "PAUSED",
    objective: str = DEFAULT_OBJECTIVE,
    campaign_id: str = "",
    ad_set_id: str = "",
    page_id_value: str = "",
    whatsapp_phone_value: str = "",
    instagram_actor_id: str = "",
    special_ad_categories: Sequence[str] | None = None,
    link: str = DEFAULT_CTA_LINK,
) -> AdsResult:
    """Crea campana + ad set + creativo + anuncio para WhatsApp Status.

    Se detiene en el primer error y deja en `data` los ids ya creados para no
    perder trazabilidad (y no repetir objetos existentes).
    """
    errors = configuration_errors()
    if errors:
        return AdsResult(False, "Falta configurar: " + ", ".join(errors) + ".", error="configuracion")

    trace: dict[str, Any] = {}

    # 1. Campana (se reutiliza si llega una).
    if campaign_id:
        trace["campaign_id"] = str(campaign_id)
    else:
        result = create_campaign(
            name, objective=objective, status=status,
            special_ad_categories=special_ad_categories,
        )
        if not result.ok:
            return AdsResult(False, result.summary, trace, result.error)
        trace["campaign_id"] = result.object_id

    # 2. Imagen (una distinta por aviso).
    if not image_hash and image:
        result = upload_ad_image(image, name=name)
        if not result.ok:
            return AdsResult(False, result.summary, trace, result.error)
        image_hash = result.object_id
        trace["image_hash"] = image_hash

    # 3. Ad set con el placement de Status (se reutiliza si llega uno).
    if ad_set_id:
        trace["ad_set_id"] = str(ad_set_id)
    else:
        result = create_status_ad_set(
            trace["campaign_id"],
            name=f"{name} - Ad set",
            daily_budget=daily_budget,
            page_id_value=page_id_value,
            whatsapp_phone_value=whatsapp_phone_value,
            countries=countries,
            custom_audiences=custom_audiences,
            advantage_audience=advantage_audience,
            status=status,
        )
        if not result.ok:
            return AdsResult(False, result.summary, trace, result.error)
        trace["ad_set_id"] = result.object_id

    # 4. Creativo.
    result = create_status_ad_creative(
        name=f"{name} - Creativo",
        message=message,
        image_hash=image_hash,
        title=title,
        link=link,
        page_id_value=page_id_value,
        instagram_actor_id=instagram_actor_id,
    )
    if not result.ok:
        return AdsResult(False, result.summary, trace, result.error)
    trace["creative_id"] = result.object_id

    # 5. Anuncio.
    result = create_ad(
        name=name,
        ad_set_id=trace["ad_set_id"],
        creative_id=trace["creative_id"],
        status=status,
    )
    if not result.ok:
        return AdsResult(False, result.summary, trace, result.error)
    trace["ad_id"] = result.object_id

    return AdsResult(True, f"Anuncio de WhatsApp Status creado en {status}.", trace)
