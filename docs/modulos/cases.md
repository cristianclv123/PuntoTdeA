# Módulo Cases / Bandeja (`cases/`)

Cola de atención humana: tickets, chat estilo WhatsApp, claim, respuesta por Meta, cierre.

UI: `/bandeja/`. API: `/api/cases/`.

## Árbol

```
cases/
  models.py
  views.py                 # bandeja HTML + POST claim/reply/close
  urls.py
  routing.py / consumers.py
  constants.py
  admin.py
  api/
    urls.py
    viewsets.py            # ConversationViewSet (tickets)
    views.py               # webhooks simulate / advisor_reply legado
    serializers.py
  services/
    assignment.py          # claim, close, permisos Staff/Owner, saludo
    ingestion.py           # inbound + outbound (Meta)
    case_events.py         # mensajes de sistema toma/cierre
    realtime.py
    attachments.py
  templates/cases/         # bandeja, detalle, parciales lista/chat/perfil
  static/cases/js/         # bandeja.js, conversation.js, composer.js
  management/commands/     # seed_demo_chats, ensure_demo_advisor
  tests.py
  test_unit_assignment_outbound.py
  test_advisor_e2e.py
```

## Modelos

| Modelo | Rol |
| --- | --- |
| `Channel` | `whatsapp`, `facebook`, `instagram`, `web` (seed migración 0002) |
| `Department` | Clasificación / escalado (registro, admisiones, …) |
| `Contact` | Estudiante del ticket (documento único) |
| `Conversation` | Caso. Ticket `TDEA-000123`. Estados: pendiente, completado, rechazado, escalado, **cerrado** |
| `Message` | inbound / outbound / system. `external_id` = wamid Meta (único por conversación si no vacío) |
| `MessageAttachment` | imagen, video, ofimática (máx. 25 MB) |
| `CaseComment` | Notas internas |
| `ReplyTemplate` | Texto rápido de bandeja (no es plantilla Meta) |

`Conversation` relevante: `assigned_to`, `claimed_at`/`claimed_by`, `closed_at`/`closed_by`, `department`, `escalated_to`, `theme`, `priority`, `external_thread_id` (en WhatsApp suele ser el número del sender).

## UI (`/bandeja/`)

Filtros (solo canal WhatsApp en la lista): Mis chats, Sin respuesta, Sin asesor, Todos, Cerrados.

| Acción POST | Efecto |
| --- | --- |
| Tomar (`claim`) | `claim_conversation` |
| Responder | `create_outbound_message` |
| Guardar gestión | estado, prioridad, dependencia, escalado |
| Cerrar | `close_conversation` → `CERRADO` |
| Comentario / plantilla local | `CaseComment` / `ReplyTemplate` |

Layout: lista + chat + perfil (`partials/_list_pane.html`, `_chat_panel.html`, `_profile_panel.html`).

## Permisos Staff o Propietario

Centralizados en `services/assignment.py`:

- `user_can_act_on_conversation`: autenticado y (`is_staff` o `assigned_to == user`)
- **Claim**
  - Cerrado → error `closed`
  - Sin asignar → cualquier autenticado toma
  - Mismo asesor → no-op (no reenvía saludo)
  - Otro asesor: staff puede reasignar; si no, 409 `already_assigned`
- **Reply**: Staff o dueño, y no cerrado
- **Close**: Staff o dueño + asesor + dependencia. PATCH **no** puede poner `CERRADO`

## Saludo al tomar

Al asignar de verdad (primera toma o reclaim de staff) se envía:

> Hola, soy {nombre}, del equipo de soporte al cliente de Punto TdeA. ¿En qué te podemos ayudar?

Va por `create_outbound_message` (Meta si el canal es WhatsApp). Si Meta falla, el reclamo **sí** queda y el saludo no se persiste. Texto en `claim_greeting_body`.

## Salida a WhatsApp (`ingestion.create_outbound_message`)

1. Valida texto o adjuntos.
2. Si hay `MessageTemplate` de communications → `MetaAdapter.send_template_message`.
3. Si canal `whatsapp` y hay texto → `send_text_message(contact.phone, body)`.
4. Éxito: guarda `Message` con `external_id = wamid`.
5. Fallo Meta: `ValidationError`, **no** crea el mensaje.
6. Canal no WhatsApp: solo persiste local.
7. Solo adjuntos: local, sin media a Graph.

Teléfono: dígitos E.164 (`57300…`).

## Entrada (`ingest_inbound_message`)

Idempotente por `external_message_id`. Crea o reutiliza `Conversation` por `(channel, external_thread_id)`.

Orígenes:

- Escalación del chatbot (`knowledge/chatbot/whatsapp.py` → `_create_case_ticket`)
- `POST /api/cases/webhooks/web/` y `/web/messages/`
- `POST /api/cases/webhooks/simulate/` si `ALLOW_WEBHOOK_SIMULATOR`

Con el ticket ya en `pending`, cada mensaje nuevo del mismo sender se anexa al caso (bandeja + WebSocket). El bot deja de responder; el cliente espera al asesor. Al tomar el chat se envía el saludo automático.

## API REST (`/api/cases/`)

Prefijo sin namespace. Router `ticket` → `/api/cases/tickets/`.

| Método | Ruta | Notas |
| --- | --- | --- |
| CRUD | `/tickets/` | list filtra `status`, `channel`, `unassigned`, `assigned_to=me`, `closed=1` |
| POST | `/tickets/{id}/claim/` | mismos códigos que el servicio |
| POST | `/tickets/{id}/reply/` | JSON o multipart; opcional `template_id` + `template_params` (plantilla Meta) |
| POST | `/tickets/{id}/close/` | `department_id`, `assigned_to_id`, `priority` |
| GET | `/tickets/{id}/messages/` | |
| GET/POST | `/tickets/{id}/comments/` | |
| CRUD | `/departments/`, `/reply-templates/`, `/contacts/`, `/comments/` | |
| GET | `/messages/?conversation=` | |
| POST | `/conversations/{id}/reply/` | legado `advisor_reply` |
| POST | `/webhooks/simulate/` | desarrollo |

El widget público inicia en `POST /web/contacts/`, que crea un contacto nuevo y
devuelve una credencial firmada. `POST /web/messages/` requiere esa credencial
en `X-Widget-Credential` y devuelve una credencial vinculada a la conversación;
`GET /web/conversations/{id}/messages/` requiere esta última. No se recuperan
credenciales para contactos existentes sin una verificación de identidad. El
endpoint separado `POST /webhooks/web/` es para integraciones servidor a servidor
y requiere `X-Integration-Token` configurado mediante `CASES_WEB_WEBHOOK_TOKEN`.

Auth: `HasCasesAccess` en los ViewSets de gestión; requiere `cases.access_cases`
directo o por grupo, con acceso global para superusuarios activos.

## WebSocket

`cases/routing.py`: `ws/bandeja/`, `ws/conversations/<id>/`.

## Comandos

```bash
python manage.py seed_demo_chats
python manage.py ensure_demo_advisor
```

Migración `0002` siembra channels, departments y plantillas de respuesta locales. Los tests dependen de ese seed.

## Pruebas

- `cases/tests.py` — modelos, HTML, adjuntos, cola
- `cases/test_unit_assignment_outbound.py` — claim/close/Meta unitario
- `cases/test_advisor_e2e.py` — inbound, claim, reply, close (Meta mockeada)

```bash
python manage.py test cases
```
