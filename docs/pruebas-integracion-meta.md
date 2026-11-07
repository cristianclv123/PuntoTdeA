# Pruebas unitarias de la integración Meta

Este documento relaciona **cada método de la integración con Meta WhatsApp Cloud
API** con la prueba unitaria que lo cubre. No es un informe de ejecución: es la
explicación del método y de cómo se verifica.

**Alcance**: `communications/adapters/meta_adapter.py`,
`communications/webhooks/meta_webhook.py`, `communications/services/`
(plantillas, configuración, diagnósticos, ads y registro de envíos de prueba) y
los modelos que persisten los eventos de Meta.

## Cómo correr las pruebas

```bash
docker compose exec -T -e DB_HOST= -e DATABASE_URL= -e REDIS_URL= web python manage.py test communications --noinput
```

Forzando `DB_HOST` y `DATABASE_URL` vacíos, Django usa SQLite dentro del contenedor
y no toca la Postgres del compose.

## Convenciones

- **Nunca se llama a la Graph API real.** Se mockea `requests.post` (adapter),
  `requests.get`/`post`/`delete` (`meta_templates`), `requests.get`
  (`meta_diagnostics`) y `requests.request` (`ads_service`).
- **Secretos falsos** con `@override_settings`.
- **Webhook**: firma HMAC `X-Hub-Signature-256` con un `META_APP_SECRET` falso.
- **Chatbot y notificaciones**: se mockean `chatbot_whatsapp.handle_message`,
  `send_replies`, `logging_service.log_event` y
  `notifications.events.notify_template_status`.
- **`SimpleTestCase`** para funciones puras; **`TestCase`** cuando se toca la BD.
- Los tests de integración E2E existentes (`test_meta_integration.py`,
  `tests/communications/test_e2e.py`) siguen vigentes; los que aparecen aquí
  cubren las ramas de validación y error que faltaban.

---

## 1. Adapter (`communications/adapters/meta_adapter.py`)

Cliente directo de WhatsApp Cloud API. Pruebas principales en
`communications/tests/test_adapters.py`; las pruebas E2E de envío de plantillas y
mensajes interactivos están en `communications/tests/test_meta_integration.py`.

| Método | Qué hace | Prueba(s) |
| --- | --- | --- |
| `_configuration_error` | Detecta si faltan `META_ACCESS_TOKEN` o `WHATSAPP_PHONE_NUMBER_ID`. | `ConfigurationErrorTests` (config ok, solo token vacío, solo phone id vacío, ambos). |
| `_messages_url` | Arma la URL de `/messages` con versión y phone id. | `UrlBuilderTests`. |
| `_media_url` | Arma la URL de `/media`. | `UrlBuilderTests`. |
| `_normalize_phone` | Deja solo dígitos (E.164 sin `+`). | `NormalizePhoneTests` (vacío, `None`, solo `+`, puntuación). |
| `_request_error` | Traduce el error de Meta a un mensaje legible con `explain()`. | `RequestErrorTests` (JSON con error, JSON inválido, `response=None`, código `131026`). |
| `_post_message` | POST a `/messages` y devuelve `SendResult` con el `wamid`. | `PostMessageTests` (éxito, URL/headers/timeout, `HTTPError`, `ConnectionError`, JSON inválido, sin id, config faltante). |
| `send_text_message` | Envía texto; `preview_url` genera miniatura de URL. | `SendTextMessageTests` (payload, `preview_url`, strip, texto/teléfono vacíos). |
| `_interactive_envelope` | Arma el sobre común de mensajes interactivos y valida longitudes. | `InteractiveEnvelopeTests` (cuerpo vacío/>1024, header/footer >60). |
| `send_interactive_buttons` | Envía hasta 3 botones de respuesta rápida. | `SendInteractiveButtonsTests` (ids duplicados, id/título vacío, título >20, cuerpo vacío, 0 botones). |
| `send_interactive_list` | Envía un mensaje de lista con hasta 10 filas. | `SendInteractiveListTests` (etiqueta vacía/>20, secciones, filas sin id/título, ids duplicados, límites de título/descripción, >10 filas). |
| `send_image_message` | Sube bytes de imagen y la envía con pie. | `SendImageMessageTests` (subida+envío, sin caption, imagen vacía, config faltante, fallo de subida, sin `media_id`, caption >1024). |
| `upload_whatsapp_media` | Sube un binario al almacén de medios de Meta. | `UploadWhatsappMediaTests` (éxito, config faltante, bytes vacíos, JSON inválido, `media_id` vacío). |
| `send_uploaded_image_message` | Envía una imagen previamente subida por `media_id`. | `SendUploadedImageMessageTests` (delegación, propagación de error). |
| `send_media_message` | Envía imagen, video o documento ya subido. | `SendMediaMessageTests` (tipo no soportado, `media_id` vacío, `filename` en documento). |
| `MetaAdapter._template_fields` | Lee los campos de envío desde un borrador, snapshot o `TemplateRef`. | `MetaAdapterTemplateFieldsTests`. |
| `MetaAdapter._parameter_values` | Ordena los parámetros `{{n}}` y valida que existan. | `MetaAdapterParameterValuesTests` (orden numérico, claves `int`/`{{n}}`, falta parámetro, repetidos). |
| `MetaAdapter._payload` | Arma el payload de plantilla (componentes de cuerpo y encabezado). | `MetaAdapterPayloadTests` (texto, header text/imagen/video/documento, tipo no soportado, idioma por defecto). |
| `MetaAdapter.send_template_message` | Envía una plantilla aprobada. | `MetaAdapterSendTemplateTests` + `MetaWhatsAppIntegrationTests` (E2E con header texto/imagen). |

---

## 2. Webhook (`communications/webhooks/meta_webhook.py`)

Único webhook de Meta: recibe mensajes del chatbot, estados de campaña y cambios de
plantillas. Pruebas en `communications/tests/test_webhooks.py`.

| Método | Qué hace | Prueba(s) |
| --- | --- | --- |
| `_verify_subscription` | Responde el desafío `GET` de Meta si el token coincide. | `VerifySubscriptionTests` (challenge 200, token incorrecto 403, `hub.mode` inválido 403, secreto vacío 403). |
| `_signature_is_valid` | Valida `X-Hub-Signature-256` con HMAC-SHA256. | `SignatureTests` (firma correcta/incorrecta, sin `sha256=`, header ausente, secreto vacío). |
| `_event` | `get_or_create` idempotente por `event_key`; `False` si ya se procesó. | `EventTests` (creación, duplicado, existente sin procesar, rama `IntegrityError`). |
| `_finish_event` | Marca `processed_at` y persiste `payload`. | `EventTests`. |
| `_compact_status` | Guarda solo `timestamp`, `recipient_id`, `pricing`, `errors` y `conversation_id`. | `CompactHelpersTests`. |
| `_compact_inbound` | Guarda lo esencial del mensaje (texto truncado a 500, interactivo). | `CompactHelpersTests`. |
| `_timestamp` | Convierte el epoch de Meta a `datetime` UTC; inválidos → `timezone.now()`. | `CompactHelpersTests`. |
| `_error_message` | Extrae el motivo de un `failed` desde `errors[]`. | `CompactHelpersTests`. |
| `_process_status` | Aplica `sent`/`delivered`/`read`/`failed` al destinatario y escribe `ContactEvent`. | `ProcessStatusTests` (progresión, duplicado, `unmatched`, regresión `read`→`delivered`, `failed` tras `read`, timestamps). |
| `_process_inbound` | Enruta el mensaje al chatbot y envía las respuestas. | `ProcessInboundTests` (texto, duplicado, phone no configurado, interactivo no soportado, texto vacío, excepción del chatbot). |
| `_process_template_status` | Notifica cambios de estado/calidad de plantillas. | `ProcessTemplateStatusTests` (mockea `notify_template_status`, `quality_update`, duplicado, ignorado). |
| `_process_payload` | Orquesta los cambios del payload y resume procesados/duplicados/ignorados. | `ProcessPayloadTests`. |
| `whatsapp_webhook` | Endpoint público: GET verificación, POST firmado. | `WebhookViewTests` (405, GET 403, JSON inválido 400, JSON no-dict 400, excepción 500, POST 200). |

---

## 3. Servicios

### 3.1 `communications/services/meta_templates.py`

Meta es la fuente de verdad de las plantillas; la base local solo guarda borradores.
Pruebas en `communications/tests/test_meta_templates.py` (clases `MetaTemplateServiceTests`,
`MetaTemplateAPITests`, `MetaTemplateComponentTests`, `MetaTemplateVerificationEdgeTests`,
`MetaTemplateNormalizeEdgeTests`, `MetaTemplateServiceErrorTests`).

| Método | Qué hace | Prueba(s) |
| --- | --- | --- |
| `is_configured` | **Código muerto**: no tiene referencias en el repo. No se prueba; se recomienda eliminarlo. | — |
| `_configuration_error` | Detecta si faltan `META_ACCESS_TOKEN` o `WHATSAPP_BUSINESS_ACCOUNT_ID`. | `MetaTemplateServiceTests` (config faltante). |
| `_graph_url` / `_headers` | URL base y encabezados de Graph API. | `MetaTemplateServiceTests` (URL y headers en list/get/create). |
| `_error_detail` | Extrae el mensaje de error de Meta sin exponer secretos. | `MetaTemplateServiceTests`, `MetaTemplateServiceErrorTests`. |
| `_variable_order` / `_body_example` | Orden de variables y ejemplos para Meta. | `MetaTemplateServiceTests` (creación con variables). |
| `_meta_buttons` | Normaliza botones URL y los limita a 3. | `MetaTemplateComponentTests`. |
| `slugify_meta_name` | Convierte un nombre libre al slug `[a-z0-9_]` de Meta. | `MetaTemplateServiceTests::test_slugify_meta_name_strips_accents_and_symbols`. |
| `build_components` | Traduce el borrador a `components` de Meta (header, cuerpo, botones). | `MetaTemplateComponentTests` (header vacío/>60, botones >3). |
| `build_payload` | Arma el payload de creación (nombre, idioma, categoría). | `MetaTemplateServiceTests` (creación). |
| `is_sample_template` | Detecta las plantillas de muestra (`hello_world`). | `MetaTemplateServiceTests::test_is_sample_template_matches_hello_world_only`. |
| `verify_campaign_template` | Verifica que la plantilla aprobada en Meta coincide con el snapshot. | `MetaTemplateServiceTests` + `MetaTemplateVerificationEdgeTests` (`meta_id` vacío/espacios, snapshot no-dict, id distinto, no aprobada, muestra). |
| `selectable_templates` | Oculta las muestras si hay plantillas propias aprobadas. | `MetaTemplateServiceTests` + `SampleTemplateLabelTests` (`test_meta_console.py`). |
| `normalize_meta_template` | Normaliza la respuesta cruda de Meta (componentes, botones, rechazo). | `MetaTemplateServiceTests` + `MetaTemplateNormalizeEdgeTests` (headers multimedia, `QUICK_REPLY`, `rejected_reason`, `indexes`/`param_count`). |
| `to_template_ref` | Construye un `TemplateRef` enviable. | `CampaignTestSendAPITests` (`test_test_send.py`), `MetaTemplateServiceTests`. |
| `list_templates` | Lista las plantillas de la WABA. | `MetaTemplateServiceTests` + `MetaTemplateServiceErrorTests` (red, JSON inválido, error Meta). |
| `get_template` | Consulta una plantilla por id. | `MetaTemplateServiceTests` + `MetaTemplateServiceErrorTests`. |
| `create_from_draft` | Crea en Meta desde un borrador local. | `MetaTemplateServiceTests` + `MetaTemplateServiceErrorTests`. |
| `edit_template` | Edita componentes de una plantilla existente. | `MetaTemplateServiceTests` + `MetaTemplateServiceErrorTests` (error de build, red, Meta). |
| `delete_template` | Elimina una plantilla por `hsm_id`. | `MetaTemplateServiceTests` + `MetaTemplateServiceErrorTests`. |

### 3.2 `communications/services/meta_config.py`

Estado de la configuración (solo lectura de `settings`). No tiene archivo de pruebas
propio: se ejercita a través de `communications/tests/test_meta_console.py`
(`MetaConfigStatusTests`, `CheckMetaCommandTests`) y del endpoint de salud.

| Método | Qué hace | Prueba(s) |
| --- | --- | --- |
| `SettingStatus.state` | Etiqueta de estado de una variable. | `MetaConfigStatusTests`. |
| `_masked` | Enmascara parcialmente un valor no secreto. | `MetaConfigStatusTests` (secretos nunca expuestos). |
| `is_fully_configured` | `META_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID`. | `MetaConfigStatusTests::test_ready_environment_enables_capabilities`. |
| `can_receive_webhooks` | `META_APP_SECRET` presente. | `MetaConfigStatusTests`. |
| `can_verify_subscription` | `META_VERIFY_TOKEN` presente. | `MetaConfigStatusTests`. |
| `can_manage_templates` | Token + WABA. | `MetaConfigStatusTests`. |
| `setting_statuses` | Lista el estado de cada variable. | `MetaConfigStatusTests` (ambiente vacío y completo). |
| `capability_status` | Resumen `can_send`/`can_receive`/`missing`. | `MetaConfigStatusTests`, `MetaHealthEndpointTests`. |
| `readiness_lines` | Filas para el comando de diagnóstico. | `CheckMetaCommandTests`. |

### 3.3 `communications/services/meta_diagnostics.py`

Validaciones en vivo contra Graph API. Pruebas en
`communications/tests/test_meta_diagnostics.py` (`MetaDiagnosticsErrorTests`,
`MetaDiagnosticsCoverageTests`).

| Método | Qué hace | Prueba(s) |
| --- | --- | --- |
| `_safe_error_code` / `_safe_meta_identifier` | Deja solo códigos/identificadores seguros, sin secretos. | `MetaDiagnosticsErrorTests`. |
| `_graph_error` | Traduce un error de Meta sin exponer el mensaje del proveedor. | `MetaDiagnosticsErrorTests`. |
| `_request_error` | Clasifica `Timeout`, `ConnectionError`, `HTTPError` y otros. | `MetaDiagnosticsErrorTests` + `MetaDiagnosticsCoverageTests::test_request_error_classifies_http_error`. |
| `_invalid_response_error` | Mensaje para respuestas JSON inválidas. | `MetaDiagnosticsErrorTests`. |
| `check_access_token` | Valida el token con `debug_token`. | `MetaDiagnosticsErrorTests` + `MetaDiagnosticsCoverageTests` (token vacío, payload no-dict). |
| `check_phone_number` | Consulta el número emisor. | `MetaDiagnosticsErrorTests` + `MetaDiagnosticsCoverageTests` (phone/token vacío, payload no-dict). |
| `run_all` | Ejecuta las validaciones en orden. | `MetaDiagnosticsCoverageTests::test_run_all_returns_token_and_phone_results_in_order`. |
| `webhook_reachable` | Comprueba que el callback responde al challenge. | `MetaDiagnosticsErrorTests` + `MetaDiagnosticsCoverageTests` (HTTP no-200). |
| `is_ready` | Configuración completa y sin pendientes. | `MetaDiagnosticsCoverageTests::test_is_ready_requires_both_config_and_webhook`. |

### 3.4 `communications/services/ads_service.py`

Cliente de la Meta Marketing API para anuncios en WhatsApp Status. Pruebas en
`communications/tests/test_ads_service.py` (`AdsServiceHelpersTests`,
`AdsServiceApiTests`, `AdsServiceConfigurationTests`, `AdsServiceTargetingTests`,
`AdsServiceSegmentPhonesTests`, `AdsServiceTransportTests`, `AdsServiceDebugTokenTests`,
`AdsServiceObjectTests`, `AdsServiceAudienceBatchTests`, `AdsServiceAdSetValidationTests`,
`AdsServiceUploadImageTests`, `AdsServiceCreateStatusAdFlowTests`).

| Método | Qué hace | Prueba(s) |
| --- | --- | --- |
| `configuration_errors` | Lista las variables de anuncios que faltan. | `AdsServiceConfigurationTests` (las 4 variables, whitespace, todo configurado). |
| `ad_account_id` | Añade el prefijo `act_` si falta. | `AdsServiceConfigurationTests`. |
| `access_token` / `page_id` / `whatsapp_phone` | Lectura de configuración. | `AdsServiceConfigurationTests`. |
| `normalize_phone` / `hash_phone` | Normaliza y hashea teléfonos (SHA-256). | `AdsServiceHelpersTests`. |
| `build_targeting` | Placement de Status + geografía + audiencia. | `AdsServiceTargetingTests` (edad, géneros, valores por defecto). |
| `phones_from_segment` | Teléfonos de un segmento (suscritos o todos). | `AdsServiceSegmentPhonesTests`. |
| `_exception_category` | Clasifica excepciones de red. | `AdsServiceTransportTests` (`HTTPError`, `ValueError`). |
| `_call` | Transporte de la Marketing API. | `AdsServiceTransportTests` (sin token), `AdsServiceApiTests`. |
| `debug_token` | Valida el token de anuncios con `app_id|app_secret`. | `AdsServiceDebugTokenTests`, `AdsServiceApiTests`. |
| `get_ad_account` / `get_page` / `get_business` | Consulta de objetos de Meta. | `AdsServiceObjectTests`, `AdsServiceApiTests`. |
| `delete_object` | Elimina un objeto por id. | `AdsServiceObjectTests`. |
| `create_custom_audience` | Crea una audiencia personalizada. | `AdsServiceObjectTests`. |
| `add_phones_to_audience` | Carga teléfonos hasheados por lotes de 5000. | `AdsServiceAudienceBatchTests` (sin teléfonos, lote >5000, fallo de batch). |
| `create_campaign` | Crea la campaña (PAUSED por defecto). | `AdsServiceApiTests`. |
| `create_status_ad_set` | Crea el ad set con el placement de Status. | `AdsServiceAdSetValidationTests` (falta página/teléfono, orden de validación). |
| `upload_ad_image` | Sube una imagen y devuelve su hash. | `AdsServiceUploadImageTests` (`OSError`, sin hash, `content_type`). |
| `create_status_ad_creative` | Crea el creativo con `object_story_spec`. | `AdsServiceObjectTests`. |
| `create_ad` | Crea el anuncio. | `AdsServiceObjectTests`. |
| `create_status_ad` | Flujo completo: campaña + ad set + creativo + anuncio. | `AdsServiceCreateStatusAdFlowTests` (flujo completo, reutilizar ids, subir imagen, fallo a mitad). |

### 3.5 `communications/services/test_send_registry.py`

| Método | Qué hace | Prueba(s) |
| --- | --- | --- |
| `record_test_send` | Guarda el `wamid` de un envío de prueba para correlacionar webhooks. | `RecordTestSendRegistryTests` (`test_test_send.py`): `wamid` vacío → `None`, creación, duplicado con `get_or_create`. |

---

## 4. Modelos (`communications/models.py`)

Pruebas en `communications/tests/test_models.py`. Documentan el comportamiento de los
modelos que persisten los eventos y el estado de la integración.

| Modelo | Pruebas | Qué verifican |
| --- | --- | --- |
| `WhatsAppWebhookEvent` | `WhatsAppWebhookEventTests` | Unicidad de `event_key`, `processed_at`, tipos `inbound`/`status`, payload por defecto, orden. |
| `BroadcastRecipient` | `BroadcastRecipientTests` | Progresión de estados, `provider_message_id`, `opted_out`/`failed`, unicidad por campaña/contacto. |
| `ContactEvent` | `ContactEventTests` | Tipos de evento, relación con `Contact`, `CASCADE`/`SET_NULL`. |
| `MessageTemplate` | `MessageTemplateTests` | Categorías, tipos de header, `param_count`, y que el borrador ya no replica el estado de Meta. |
| `Campaign` | `CampaignMetaTests` | Estados, snapshot de plantilla, métricas de destinatarios, protección del segmento. |
| `AudienceSegment` / `SegmentMembership` | `AudienceSegmentTests` | Origen, `contact_count`, unicidad de miembros, borrado. |

---

## 5. Cobertura y huecos conocidos

- La lista completa de pruebas y lo que espera cada una está en
  `docs/informe-pruebas-meta.md`.
- **`meta_templates.is_configured()` es código muerto**: no tiene referencias en el
  repo. No tiene prueba; se recomienda eliminarlo en un cambio aparte.
- **Borde no cubierto en `_request_error` del adapter**: si `response.json()` devuelve
  `None` o un no-dict, el `except (TypeError, ValueError)` no captura el `AttributeError`
  posterior. Es un borde del código, no un caso real de `requests`; no se prueba a
  propósito. Si se quiere, se puede endurecer el código en un cambio aparte.
- **`meta_config` no tiene tests unitarios propios**: se ejercita a través de
  `test_meta_console.py` y del endpoint de salud. Si se prefiere, se pueden añadir tests
  directos en un archivo nuevo.
- Los modelos `MessageTemplate.meta_template_name` y `MessageTemplate.status` ya no
  existen (migración `0006`): las pruebas documentan que el estado vive en Meta.
