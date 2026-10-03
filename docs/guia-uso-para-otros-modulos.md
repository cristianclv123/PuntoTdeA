# Manual: cómo usar la integración de WhatsApp desde los otros módulos

**Audiencia:** equipos de campañas, chatbot/bot, plantillas y segmentos, y despliegue.

Este manual es el punto de entrada para **consumir la integración con Meta
WhatsApp Cloud API** desde el resto del sistema. Explica qué llamar, qué
esperar, cómo probar y qué no tocar. Para el detalle del webhook y de la
configuración en Meta, ver
[`guia-consumo-webhook.md`](guia-consumo-webhook.md) y
[`whatsapp-meta.md`](whatsapp-meta.md).

> Regla general: la integración ya está conectada de punta a punta. **Ningún
> módulo debe crear un segundo webhook, re-validar la firma, ni llamar a Graph
> API directamente.** Todo pasa por la capa de la integración.

```
                        ┌──────────────────────┐
  Módulo de campañas ──▶│  send_campaign()     │──▶ Graph API ──▶ WhatsApp
                        └──────────────────────┘
                                                                       │
                          ┌──────────────────────┐                    │
  Meta ──POST /webhook──▶│  meta_webhook        │◀── estados ─────────┘
                          └──────────┬───────────┘
                     ┌───────────────┴──────────────┐
                     ▼                              ▼
        estados → BroadcastRecipient      mensaje → chatbot.handle_message
                                                  │
        Campañas ←── leen estados ────────────────┘
```

---

## 1. Qué aporta la integración a cada módulo

| Módulo | Lo que recibe de la integración |
| --- | --- |
| Campañas | Envío de plantillas aprobadas (`MetaAdapter`), `provider_message_id` guardado y estados de entrega (`sent`/`delivered`/`read`/`failed`) aplicados automáticamente vía webhook. |
| Bot | Mensajes de texto entrantes ya filtrados y des-duplicados, entregados a `handle_message(sender, text)`; respuestas enviadas con `send_text`. |
| Plantillas / Segmentos | El envío depende de que sus registros cumplan ciertas condiciones (plantilla `approved`, parámetros completos, `opt_in` respetado). |
| Despliegue | Variables en `.env`, asistente de configuración, comando de diagnóstico y páginas de consola. |

---

## 2. Mapa de componentes

| Archivo | Qué hace | Quién lo usa |
| --- | --- | --- |
| `communications/adapters/meta_adapter.py` | Cliente de Graph API: `send_text_message()` y `MetaAdapter.send_template_message()`. | Bot (`send_text`) y campañas (`send_campaign`). |
| `communications/adapters/base.py` | Contratos `ChannelAdapter` y `SendResult`. | La capa de envío. |
| `communications/webhooks/meta_webhook.py` | Webhook único: firma, idempotencia, ruteo entrantes/estados. | Meta (lo llama desde afuera). |
| `communications/services/campaign_service.py` | `send_campaign()`, pausa/reanuda/cancela. | Módulo de campañas. |
| `communications/services/meta_config.py` | Capacidad (`can_send`/`can_receive`) y estado de configuración. | Consola y comandos. |
| `communications/services/meta_diagnostics.py` | Diagnóstico en JSON. | Comando `check_meta_whatsapp`. |
| `communications/models.py` | `BroadcastRecipient`, `WhatsAppWebhookEvent`, `ContactEvent`. | Persistencia de envíos, estados y auditoría. |
| `communications/meta_console_views.py` | Páginas Prueba de integración y Configuración. | Operación / pruebas manuales. |
| `communications/management/commands/` | `check_meta_whatsapp`, `seed_demo_whatsapp`, `cleanup_whatsapp_events`. | Diagnóstico, datos demo, retención. |
| `configurar_meta.ps1` / `limpiar_retencion.ps1` | Asistente de configuración y limpieza de retención. | Despliegue. |
| `knowledge/chatbot/whatsapp.py` | Seam del bot: `handle_message()` y `send_text()`. | Módulo del bot. |

---

## 3. Configuración

### 3.1 Variables de entorno (`.env`)

Las credenciales de Meta **las pone el dueño del proyecto** en `.env`; el
repositorio no trae valores reales. Después de editarlas, hay que recrear el
contenedor: `docker compose up -d --force-recreate web` (un simple `restart`
conserva las variables viejas y parece que el cambio nunca se aplicó).

| Variable | Necesaria para | Notas |
| --- | --- | --- |
| `META_ACCESS_TOKEN` | Enviar mensajes | Es el token permanente de la app en Meta. |
| `WHATSAPP_PHONE_NUMBER_ID` | Enviar y recibir del número correcto | Los mensajes de otro número se descartan. |
| `META_APP_SECRET` | Recibir eventos | Firma `X-Hub-Signature-256`. Sin ella todo `POST` al webhook responde `403`. |
| `META_VERIFY_TOKEN` | Verificación del webhook | Debe coincidir con el que se registra en Meta. |
| `META_APP_ID` | Nada (opcional) | No la usa el código; no bloquea la integración. |
| `WHATSAPP_API_VERSION` | — | Default `v21.0`. |
| `META_GRAPH_API_URL` | — | Default `https://graph.facebook.com`. |
| `META_REQUEST_TIMEOUT` | — | Timeout por llamada, default `10` (segundos). |
| `ALLOW_WEBHOOK_SIMULATOR` | Simulador de webhooks de `cases/api/views.py` | Por defecto sigue a `DEBUG`. |

El asistente `configurar_meta.ps1` guía el llenado y la validación. El comando
`check_meta_whatsapp` (con `--validate` para probar contra Graph API) verifica
todo en una salida legible.

### 3.2 Túnel HTTPS para pruebas reales

Meta solo alcanza una URL pública con HTTPS. En desarrollo, `localhost:8000`
no sirve: hacé un túnel (`ngrok`, Cloudflare) y registrá en Meta Developers un
solo callback:

```
POST https://{DOMINIO-PUNTO-TdeA}/api/whatsapp/webhook/
```

junto con el `META_VERIFY_TOKEN` y el `META_APP_SECRET`. El alias
`/base-de-conocimiento/chatbot/whatsapp/` llama a la misma función, pero **no**
se registra en Meta.

---

## 4. Módulo de campañas

### 4.1 Enviar una campaña

```python
from communications.services.campaign_service import send_campaign

send_campaign(campaign)            # usa MetaAdapter
send_campaign(campaign, adapter)   # solo para tests
```

Puntos de entrada actuales: `POST /api/campaigns/{id}/send/` (solo desde
`draft` o `scheduled`) y la acción de envío en
`/admin/communications/campaign/`.

Por cada destinatario en estado `pending`:

| Situación | Resultado |
| --- | --- |
| Contacto con `whatsapp_opt_in = baja` | Estado `opted_out`, sin llamar a Meta. |
| Meta acepta | Estado `sent`, `provider='meta'`, `provider_message_id` = `wamid`, `sent_at`, evento `message_sent`. |
| Meta rechaza / falla la llamada | Estado `failed`, `error_message` con el mensaje de Meta, evento `message_failed`. |

Los teléfonos se normalizan a solo dígitos (`+57 300 123 4567` →
`573001234567`).

### 4.2 Requisitos para que un mensaje salga

La plantilla debe cumplir todo esto, o `send_template_message` devuelve
`success=False` antes de tocar la red:

1. `status = approved` (la bandera local de `MessageTemplate`).
2. `meta_template_name` existe **y está aprobada en la cuenta de Meta**, con el
   mismo nombre. La aprobación local no basta.
3. `language` coincide con el registrado en Meta (default `es_CO`).
4. Cada `{{n}}` del `body_text` tiene valor en `params` (se envían en orden
   ascendente de índice).
5. Si `header_type != none`, `header_media_url` está configurada.

### 4.3 `provider_message_id`: no se toca a mano

La capa guarda el `wamid` devuelto por Meta en `BroadcastRecipient` en el
momento del envío, exactamente para que los estados lleguen después por
webhook y se emparejen con `provider_message_id == wamid`. **Nunca escribir
ese campo a mano**: se rompe el emparejamiento y los estados dejan de
aplicarse.

### 4.4 Estados de entrega gratis

El mismo webhook que alimenta al bot aplica los estados a `BroadcastRecipient`.
No hay que consumir el webhook desde campañas:

| Estado de Meta | Efecto en `BroadcastRecipient` | Además |
| --- | --- | --- |
| `sent` | `sent` | `sent_at` |
| `delivered` | `delivered` | `delivered_at` |
| `read` | `read` | `read_at` |
| `failed` | `failed` + `error_message` | — |

Garantías:

- **Sin regresiones:** la progresión es `pending(0) < queued(1) < sent(2) <
  delivered(3) < read(4)`; un `delivered` que llega después de un `read` no lo
  revierte.
- **`failed` no se aplica** si el destinatario ya está en `read`.
- Cada transición escribe un `ContactEvent` (historial en `contact.events`).
- Cada evento llega a `WhatsAppWebhookEvent`, coincida o no con un
  destinatario.

Las métricas del dashboard (`delivered_count`, `read_count`, `failed_count`)
ya leen estos campos y no necesitan cambios.

**Cuando un estado no coincide:** si el `wamid` no es de ningún destinatario,
el evento se guarda, cuenta como `unmatched` y no modifica nada. Es el
diagnóstico de «el `wamid` que guardamos no es el que reporta Meta» — miralo
en la tabla de eventos de la página Prueba de integración o en
`/admin/communications/whatsappwebhookevent/`.

### 4.5 Límite de tasa: un POST por mensaje

Meta **no tiene envío en lote**: cada mensaje es un `POST` individual, con 10 s
de timeout, dentro de la request. Para audiencias grandes esto bloquea; mover
el agendado y la ejecución a un worker (Celery, command) es del equipo de
campañas, y el límite de tasa también lo configura ese equipo. La integración
no paraleliza ni agenda: llama a `send_campaign` desde tu worker y no
reimplementes el bucle por destinatario.

### 4.6 Probar sin gastar

```powershell
docker compose exec -T web python manage.py seed_demo_whatsapp
```

Crea 8 contactos, 2 segmentos y 2 campañas. Una campaña tiene un destinatario
en cada estado de entrega (para ver métricas sin enviar); la otra queda en
`draft` lista para un envío real. Los `wamid` son sintéticos (`wamid.SEED…`);
limpiar con `--limpiar`. Estos destinatarios alimentan la tabla de estados de
campaña de la página de prueba.

### 4.7 Retención y limpieza

```powershell
# Ensayo: qué se borraría (mayores de 30 días por defecto)
docker compose exec -T web python manage.py cleanup_whatsapp_events

# Borrado real de estados de envío mayores de 7 días
docker compose exec -T web python manage.py cleanup_whatsapp_events --days 7 --ejecutar
```

Borra solo eventos de **estado de envío** antiguos y **conserva** los `failed`
(guardan el motivo) y los `inbound` (conversaciones del bot). Borrar un evento
no deshace ningún estado ya aplicado al destinatario.

`limpiar_retencion.ps1` envuelve el comando: hace ensayo, pide confirmación
(salvo `-Si`) y deja un log con marca de tiempo en `logs/`:

```powershell
.\limpiar_retencion.ps1                 # ensayo + confirmación
.\limpiar_retencion.ps1 -Days 7 -Si     # no interactivo (Programador de tareas)
```

---

## 5. Módulo del bot

### 5.1 El seam al que te conectás

```python
from knowledge.chatbot import whatsapp as chatbot_whatsapp

replies = chatbot_whatsapp.handle_message(sender, text)   # -> list[str]
```

Eso es todo el contrato. El webhook ya extrajo `sender` (el `from` de Meta,
solo dígitos) y `text`, ya filtró los mensajes no textuales, y envía cada
string del resultado por `send_text`. El módulo del bot **nunca ve** el
payload, la firma ni la capa HTTP.

### 5.2 Identidad e idempotencia

- `sender` es el número de WhatsApp sin `+`. Es el **único identificador**: no
  hay tabla de mapeo teléfono → `Contact` todavía; si hacés falta, es trabajo
  nuevo.
- La deduplicación es a nivel de evento (por `wamid`), antes de llamar a
  `handle_message`; un reintento de Meta no reprocesa un mensaje ya atendido.

### 5.3 Máquina de estados (resumen)

`flow_state` de la conversación: `waiting_question` → `waiting_confirmation`
→ `help_options` → `waiting_advisor_question`. En `ended`/`pending` responde
«ya cerrado». Con estado desconocido, reinicia y envía el texto como pregunta.

### 5.4 Dos comportamientos que parecen bugs

1. **El primer mensaje se descarta.** En una conversación nueva el bot
   devuelve el saludo y no mira el texto: el primer turno tiene que ser un
   saludo, la pregunta se procesa del segundo en adelante.
2. **En `waiting_confirmation` solo sirve sí/no.** Cualquier otra respuesta
   re-pregunta («Respóndeme sí o no…») y **ese mensaje no se guarda** en el
   historial.

### 5.5 Probar el flujo completo

Hace falta un WhatsApp de verdad. Escribile **un saludo** al número de negocio y
recargá la página **WhatsApp (Meta) → Prueba de integración**: el evento
`inbound` aparece en *Eventos del webhook* y el hilo en *Conversaciones del bot*.
Mandá el segundo turno desde un WhatsApp cualquiera (no hace falta el de la
persona) y seguí la conversación. Como el bot responde al número que escribió,
el intercambio se ve en la página pero la otra persona no ve nada: es lo
esperado.

La referencia completa de esa página está en
[`pagina-pruebas-whatsapp.md`](pagina-pruebas-whatsapp.md).

---

## 6. Plantillas y segmentos: lo que el envío exige de ellos

- **Plantillas:** la aprobación local la pone un humano
  (`MessageTemplate.status = approved`); además la plantilla debe existir y
  estar aprobada **en la cuenta de Meta** con el mismo `meta_template_name`.
  Ningún código puede aprobar por Meta.
- **Segmentos:** al resolver destinatarios, los contactos con
  `whatsapp_opt_in = baja` se marcan `opted_out` y **no** se llama a Meta.

---

## 7. Diagnóstico rápido

```powershell
# Configuración y conectividad; sale con código 1 si falta algo
docker compose exec -T web python manage.py check_meta_whatsapp
docker compose exec -T web python manage.py check_meta_whatsapp --validate
```

| Síntoma | Causa |
| --- | --- |
| `403 Invalid signature` en todo evento | `META_APP_SECRET` vacío/erróneo, o el contenedor no se recreó tras editar `.env`. |
| `Verification failed` | `META_VERIFY_TOKEN` de Meta ≠ el de `.env`. |
| Llegan eventos, no cambian estados | `wamid` no coincide con `provider_message_id`; buscar `unmatched` en la tabla de eventos. |
| El bot responde, no llega nada al celular | Escribió un número que no es el de la persona que probó, o `WHATSAPP_PHONE_NUMBER_ID` incorrecto. |
| El bot responde dos veces | Evento reintentado por Meta (límite conocido, sección 8). |
| El envío de campaña falla apenas arranca | Plantilla no `approved` o `meta_template_name` que no existe en la cuenta de Meta. |

Consola disponible en la interfaz: **WhatsApp (Meta) → Prueba de integración**
(envío de texto y de plantilla, ventana de 24 h, validación con Graph API, y las
tablas de estados, eventos, conversaciones y destinatarios) y
**WhatsApp (Meta) → Configuración** (estado de las variables y mantenimiento).
Recordá `docker compose up -d --force-recreate web` tras tocar `.env`.

---

## 8. Mantenimiento y escalabilidad

- **Índices** ya aplicados (migración `0003`): `provider_message_id` en
  `BroadcastRecipient` (emparejamiento de estados) y `created_at` en
  `WhatsAppWebhookEvent` (limpieza por antigüedad).
- **Retención:** Meta reporta un estado por mensaje (~3–4 eventos por mensaje:
  sent → delivered → read). Con campañas grandes la tabla crece rápido; la
  limpieza diaria es recomendable (ver sección 4.7).
- **Límites conocidos:** solo se procesan mensajes entrantes `type: "text"`
  (multimedia e interactivos se registran y descartan); el envío de campaña es
  síncrono (el paso a asíncrono/hilo es del equipo de campañas); las respuestas
  del bot son «al menos una vez» (un reintento de Meta puede reenviar la
  respuesta); los adapters Twilio/mock existen pero no están conectados — no
  construir sobre ellos.

---

## 9. Reglas de oro (qué no hacer)

- No crear un segundo webhook ni una ruta paralela. Hay uno solo.
- No re-validar `X-Hub-Signature-256`: ya se valida y es obligatoria.
- No llamar a Graph API directamente: pasar por `MetaAdapter` o
  `chatbot_whatsapp.send_text`. Una llamada directa se salta
  `provider_message_id` y los estados de entrega dejan de funcionar.
- No escribir `provider_message_id` a mano.
- `sent` solo significa que Meta aceptó el mensaje; la entrega la confirman los
  estados (`delivered`/`read`), y el `read` puede no llegar nunca.

---

## Documentos relacionados

- [`guia-consumo-webhook.md`](guia-consumo-webhook.md) — detalle del endpoint,
  la máquina de estados del bot y troubleshooting del webhook (en inglés).
- [`whatsapp-meta.md`](whatsapp-meta.md) — referencia completa: configuración
  paso a paso y configuración en Meta Developers.