# Módulo Communications (`communications/`)

Campañas masivas WhatsApp, plantillas aprobadas por Meta, segmentos, contactos CDP y **la pasarela Graph API**.

UI: `/campanas/`. API interna: `/campanas/api/`. Webhook: `/api/whatsapp/webhook/`.

Contrato para el resto del sistema: [guia-uso-para-otros-modulos.md](../guia-uso-para-otros-modulos.md).

## Árbol

```
communications/
  models.py
  views.py                 # páginas de campañas
  viewsets.py              # API interna
  urls.py
  serializers.py
  permissions.py           # IsInternalService
  meta_console_views.py    # /whatsapp-prueba/, /whatsapp-prueba/resultados/, /whatsapp-configuracion/
  admin.py
  adapters/
    base.py                # ChannelAdapter, SendResult
    meta_adapter.py        # send_text_message, MetaAdapter
    mock_adapter.py        # tests
    twilio_adapter.py      # legado, no usar
  webhooks/meta_webhook.py
  services/
    campaign_service.py    # send_campaign()
    meta_config.py
    meta_diagnostics.py
    meta_errors.py
    segmentation_service.py
    dashboard_service.py
    ads_service.py
    logging_service.py
    test_send_registry.py
  management/commands/     # check_meta_whatsapp, seeds, cleanup
  tests/
```

## Modelos

| Modelo | Rol |
| --- | --- |
| `Contact` | CDP (UUID, documento único, `whatsapp_opt_in`) |
| `ContactEvent` | Timeline (enviado, entregado, leído, baja, …) |
| `MessageTemplate` | Plantilla Meta (`approved` local + nombre en Business Manager) |
| `AudienceSegment` + `SegmentMembership` | Audiencias |
| `Campaign` | Envío masivo (draft → scheduled → sending → sent / paused / cancelled / failed) |
| `BroadcastRecipient` | Un destinatario; `provider_message_id` = wamid (**solo lo escribe el envío**) |
| `WhatsAppWebhookEvent` | Idempotencia del webhook |

## Pasarela Meta (único cliente Graph)

| Función | Uso |
| --- | --- |
| `send_text_message(to, text)` | Chatbot y respuestas de la bandeja |
| `MetaAdapter.send_template_message(to, template, params)` | Campañas y reply con `template_id` |

`SendResult(success, provider_message_id, error)`. Teléfonos: solo dígitos.

**Prohibido:** segundo webhook, revalidar firma en otro app, `requests` a `graph.facebook.com` fuera de `meta_adapter.py`.

## Webhook

`POST /api/whatsapp/webhook/`

- GET: verificación `hub.mode` + `META_VERIFY_TOKEN`.
- POST: firma `X-Hub-Signature-256` con `META_APP_SECRET`.
- Textos inbound → `chatbot_whatsapp.handle_message` + `send_text` por cada reply.
- Status (sent/delivered/read/failed) → actualiza `BroadcastRecipient` por wamid.

Health: `GET /api/whatsapp/health/`.

## Campañas

```python
from communications.services.campaign_service import send_campaign
send_campaign(campaign)            # MetaAdapter
send_campaign(campaign, adapter)   # tests
```

Por destinatario `pending`:

- opt-in `baja` → `opted_out`, no llama Meta
- Meta OK → `sent` + wamid
- Meta error → `failed` + `error_message`

Plantilla: `status=approved`, `meta_template_name` real en Meta, idioma, params `{{n}}`, header media si aplica.

UI: listado, nueva, detalle, plantillas, audiencias, interacciones, test-send.

## API interna `/campanas/api/`

ViewSets: `contacts`, `templates`, `segments`, `campaigns` (acción `send` desde `draft`/`scheduled`).

Permiso `IsInternalService`: sesión autenticada o `X-Internal-Token`. Con `DEBUG=True` permite todo.

## Consola staff

| Ruta | Uso |
| --- | --- |
| `/whatsapp-prueba/` | Enviar texto/plantilla de prueba, ventana 24 h |
| `/whatsapp-prueba/resultados/` | Tablas de resultados por pestañas (estados, envíos, eventos, chats, destinatarios) |
| `/whatsapp-configuracion/` | Estado de variables |

Ver [pagina-pruebas-whatsapp.md](../pagina-pruebas-whatsapp.md).

## Comandos

```bash
python manage.py check_meta_whatsapp [--validate]
python manage.py seed_demo_whatsapp
python manage.py seed_whatsapp_test_templates
python manage.py cleanup_whatsapp_events [--days N] [--ejecutar]
python manage.py reset_whatsapp_test_data [--ejecutar]
python manage.py check_meta_ads
```

Sin `--ejecutar`, cleanup/reset solo informan.

## Pruebas

```bash
python manage.py test communications
```

Integración Meta usa `@override_settings` con secretos falsos; no pega a Graph de verdad.
