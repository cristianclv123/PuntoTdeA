# Módulo Announcements (`announcements/`)

Avisos institucionales y su publicación opcional en **WhatsApp Status** (Meta Marketing API), no Cloud API de mensajería.

UI: `/avisos/`. Detalle Status: [anuncios-status-whatsapp.md](../anuncios-status-whatsapp.md).

## Árbol

```
announcements/
  models.py              # Announcement, StatusAd
  views.py
  urls.py
  admin.py
  status_ad_service.py   # crea/pausa objetos en Meta Ads
  mock_data.py
  tests.py
```

## Modelos

| Modelo | Rol |
| --- | --- |
| `Announcement` | Título, contenido, imagen, `is_urgent` |
| `StatusAd` | Rastro en Meta: campaign/adset/creative/ad ids, presupuesto, países, `state` |

Estados de `StatusAd`: `draft`, `paused` (default de prueba, no gasta), `active`, `error`.

`Announcement.is_published_in_status`: hay un StatusAd `paused` o `active`.

`segment_ids` guarda audiencias de `communications.AudienceSegment` para reintentar sin depender de que la custom audience ya exista en Meta.

## UI

`GET /avisos/` (`announcements:index`): listado y acciones de publicación según `views.py` + `status_ad_service`.

Alias `/announcements/` redirige aquí.

## Relación con otros módulos

- Audiencias: `communications.AudienceSegment`
- Ads: `communications.services.ads_service` y comando `check_meta_ads` / `create_whatsapp_status_ad`
- **No** usa `send_text_message` ni el webhook de Cloud API

## Pruebas

```bash
python manage.py test announcements
```
