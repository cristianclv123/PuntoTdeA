# Documentación de Punto TdeA

Índice de la carpeta `docs/`. El código, la UI y esta documentación están en español.

## Por módulo

| Documento | App Django | Qué cubre |
| --- | --- | --- |
| [Arquitectura](arquitectura.md) | todo el repo | Stack, apps, flujos, puertos, reglas transversales |
| [Núcleo](modulos/nucleo.md) | `PuntoTdeA/` | Settings, auth, landing, ASGI, URLs raíz |
| [Cases / Bandeja](modulos/cases.md) | `cases/` | Tickets, claim, reply Meta, cierre, API, WebSocket |
| [Knowledge / Chatbot](modulos/knowledge.md) | `knowledge/` | FAQ, RAG, workflow WhatsApp, escalación a casos |
| [Communications](modulos/communications.md) | `communications/` | Campañas, plantillas Meta, webhook, CDP |
| [Announcements](modulos/announcements.md) | `announcements/` | Avisos y anuncios de WhatsApp Status |
| [Dashboard](modulos/dashboard.md) | `dashboard/` | Home autenticado y métricas WhatsApp |

## WhatsApp / Meta (ya existente)

Estas guías no se duplican aquí; son el contrato de la pasarela:

- [Uso desde otros módulos](guia-uso-para-otros-modulos.md) — **no** llamar Graph API a mano
- [Consumo del webhook](guia-consumo-webhook.md)
- [WhatsApp Meta](whatsapp-meta.md)
- [Página de pruebas](pagina-pruebas-whatsapp.md)
- [Avisos en Status](anuncios-status-whatsapp.md)
- [Despliegue en Render](despliegue-render.md)

Chatbot (detalle de flujo en el app): [`knowledge/README.md`](../knowledge/README.md).

## Cómo leer el código

1. Empieza por [arquitectura.md](arquitectura.md).
2. Abre la ficha del módulo que vas a tocar.
3. Si el cambio habla con WhatsApp, lee [guia-uso-para-otros-modulos.md](guia-uso-para-otros-modulos.md).
4. No inventes un segundo webhook ni un cliente Graph paralelo.

## Pruebas

Suite organizada por módulo (unitarias, estados, E2E): [`tests/README.md`](../tests/README.md).

```bash
python manage.py test --noinput          # todo (apps + tests/)
python manage.py test tests --noinput    # solo la carpeta tests/
```
