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
    campaign_personalization_service.py # validación Excel y autorizaciones
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
| `CampaignPersonalization` | Validación temporal del Excel y conjunto autorizado de destinatarios |
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

Health: `GET /api/whatsapp/health/`, parte de la consola protegida: requiere sesión staff y permiso explícito de Communications. Sin sesión responde 302 al login. Render acepta respuestas 2xx y 3xx para su health check (ver `docs/despliegue-render.md`), por eso la ruta actual funciona sin hacer público el estado de la integración.

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

### Personalización desde Excel

El asistente de campañas permite subir un `.xlsx` independiente del importador de
audiencias. Primero se inspeccionan las columnas y luego se mapea el documento
y cada variable numérica `{{n}}` a una columna o a un valor fijo. La validación
relaciona filas exclusivamente por `Contact.document_number`, comprueba que el
contacto pertenezca al segmento, rechaza documentos duplicados y valida los
datos/variables requeridos. Los rechazados incluyen fila y motivo; sus valores
no se copian a `Contact`.

La API interna añade:

- `POST /campanas/api/campaigns/personalization/inspect/` (multipart `file`):
  devuelve encabezados e índices de columna.
- `POST /campanas/api/campaigns/personalization/validate/` (multipart `file`,
  segmento, snapshot y mapeo): devuelve la vista previa, filas válidas y
  rechazadas, y un identificador de validación con vigencia de 30 minutos.

Al crear la campaña se envía `personalization_validation_id`; si hubo filas
rechazadas también se requiere `confirm_partial=true`. El backend verifica que
la validación corresponda a la misma audiencia y plantilla, crea únicamente los
destinatarios válidos y almacena sus parámetros en `BroadcastRecipient.params`.
Los datos intermedios del Excel se eliminan al consumir la validación. Antes de
cualquier envío, el servicio verifica que los destinatarios sigan coincidiendo
con la autorización y que todas las variables estén completas. Los envíos
directos por API y la acción de administración usan la misma protección.
Las validaciones no consumidas expiran a los 30 minutos; para retirar sus datos
se puede programar `python manage.py cleanup_campaign_personalizations
--ejecutar` (sin la opción, el comando solo informa).

## API interna `/campanas/api/`

ViewSets: `contacts`, `templates`, `segments`, `campaigns` (acción `send` desde `draft`/`scheduled`).

Permiso `IsInternalService`: permiso explícito `communications.access_communications` en sesión o `X-Internal-Token` válido para consumidores de servicio. `DEBUG=True` no omite este control. Como excepción funcional, `announcements.access_announcements` permite solo listar segmentos y consultar la vista previa acotada de sus contactos; no permite ver el detalle ni crear, importar, modificar o eliminar segmentos.

## Consola staff

Todas las vistas de la consola requieren `is_staff` y acceso explícito a Communications. El superusuario activo conserva el acceso por la regla modular global.

| Ruta | Uso |
| --- | --- |
| `/whatsapp-prueba/` | Enviar texto/plantilla de prueba, ventana 24 h |
| `/whatsapp-prueba/resultados/` | Movimientos por pestañas (estados, eventos, chats, destinatarios, campañas en Meta) |
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
