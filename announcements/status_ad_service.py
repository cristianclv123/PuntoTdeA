"""Publicacion de avisos como anuncios en WhatsApp Status.

Une el modulo de Avisos (`Announcement`) con el servicio de Marketing API
(`communications.services.ads_service`): construye la audiencia a partir de los
segmentos seleccionados y crea campana, ad set, creativo y anuncio.

Por defecto el anuncio queda en PAUSED (prueba, sin gastar). El rastro queda en
un `StatusAd` asociado al aviso.
"""

from __future__ import annotations

import logging

from communications.models import AudienceSegment
from communications.services import ads_service

from .models import Announcement, StatusAd

logger = logging.getLogger(__name__)

DEFAULT_DAILY_BUDGET = 2_000_000


def _segment_ids(values) -> list[int]:
    ids = []
    for value in values or []:
        try:
            ids.append(int(str(value).strip()))
        except (TypeError, ValueError):
            continue
    return ids


def _audience_phones(segments) -> list[str]:
    phones: set[str] = set()
    for segment in segments:
        phones.update(ads_service.phones_from_segment(segment))
    return sorted(phones)


def publish_announcement(
    announcement: Announcement,
    *,
    segment_ids=None,
    reuse_audience_ids=None,
    advantage_audience: bool = False,
    activate: bool = False,
    daily_budget: int = DEFAULT_DAILY_BUDGET,
    countries=None,
) -> StatusAd:
    """Crea el anuncio de Status para un aviso y registra el resultado.

    `segment_ids` son los segmentos marcados al publicar; se guardan en el
    `StatusAd` para que un reintento use siempre la misma audiencia.

    `reuse_audience_ids` permite reutilizar audiencias ya creadas en Meta (por
    ejemplo, al reintentar) en lugar de volver a subir los telefonos.

    Devuelve el `StatusAd` con su estado final (`paused`, `active` o `error`).
    """
    ids = _segment_ids(segment_ids)

    status_ad = StatusAd.objects.create(
        announcement=announcement,
        daily_budget=daily_budget,
        countries=list(countries or ads_service.DEFAULT_COUNTRIES),
        advantage_audience=advantage_audience,
        segment_ids=ids,
        state=StatusAd.State.DRAFT,
    )

    # Audiencia: se reutiliza la de Meta si llega; si no, se arma con la union
    # de telefonos de los segmentos.
    audience_ids: list[str] = [
        str(value) for value in (reuse_audience_ids or []) if str(value).strip()
    ]
    if not audience_ids and ids:
        segments = list(AudienceSegment.objects.filter(pk__in=ids))
        phones = _audience_phones(segments)
        if phones:
            created = ads_service.create_custom_audience(
                f"Status: {announcement.title[:80]}"
            )
            if not created.ok:
                return _fail(status_ad, created.error or created.summary)
            audience_id = created.object_id
            uploaded = ads_service.add_phones_to_audience(audience_id, phones)
            if not uploaded.ok:
                return _fail(status_ad, uploaded.error or uploaded.summary)
            audience_ids = [audience_id]
    status_ad.audience_ids = audience_ids

    image_path = ""
    if announcement.image:
        try:
            image_path = announcement.image.path
        except (NotImplementedError, ValueError):
            image_path = ""

    result = ads_service.create_status_ad(
        name=f"Aviso: {announcement.title}"[:200],
        message=announcement.content,
        daily_budget=daily_budget,
        image=image_path or None,
        title=announcement.title[:200],
        countries=countries,
        custom_audiences=audience_ids,
        advantage_audience=advantage_audience,
        status="ACTIVE" if activate else "PAUSED",
    )

    trace = result.data or {}
    status_ad.campaign_id = str(trace.get("campaign_id", "") or "")
    status_ad.ad_set_id = str(trace.get("ad_set_id", "") or "")
    status_ad.creative_id = str(trace.get("creative_id", "") or "")
    status_ad.ad_id = str(trace.get("ad_id", "") or "")

    if not result.ok:
        return _fail(status_ad, result.error or result.summary)

    status_ad.state = StatusAd.State.ACTIVE if activate else StatusAd.State.PAUSED
    status_ad.error = ""
    status_ad.save()
    return status_ad


def _fail(status_ad: StatusAd, error: str) -> StatusAd:
    status_ad.state = StatusAd.State.ERROR
    status_ad.error = error or "Error desconocido al publicar en WhatsApp Status."
    status_ad.save()
    return status_ad
