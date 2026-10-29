# Arquitectura de Punto TdeA

Sistema de atención y comunicaciones de la Institución Universitaria Pascual Bravo / Punto TdeA: bandeja de casos WhatsApp, chatbot de conocimiento, campañas masivas y avisos.

## Stack

| Capa | Tecnología |
| --- | --- |
| Backend | Django 5.1, DRF, Django Channels |
| Servidor | Daphne (ASGI), Docker Compose |
| Datos | PostgreSQL (Docker/producción), SQLite si no hay `DB_HOST` |
| Tiempo real | Redis + Channels (`ws/bandeja/`, `ws/conversations/<id>/`) |
| UI | Templates Django, CSS en `static/css/`, JS vanilla por módulo |
| WhatsApp | Meta Cloud API vía `communications/adapters/meta_adapter.py` |
| Docs API | drf-spectacular: `/api/docs/`, `/api/schema/` |

Idioma `es-co`, zona `America/Bogota`, `USE_TZ=True`.

## Apps Django

```
PuntoTdeA/          # proyecto: settings, urls, auth, landing
cases/              # bandeja de asesores y tickets
knowledge/          # FAQ, artículos, chatbot, RAG
communications/     # campañas, plantillas, webhook Meta, contactos CDP
announcements/      # avisos institucionales + Status Ads
dashboard/          # home interno con métricas
```

No es un monorepo de varios Git: un solo proyecto Django.

## Mapa de URLs

| Ruta | Módulo |
| --- | --- |
| `/`, `/login/`, `/logout/`, `/perfil/` | Núcleo |
| `/dashboard/` | Dashboard |
| `/bandeja/` | Cases (UI) |
| `/base-de-conocimiento/` | Knowledge (UI) |
| `/campanas/` | Communications (UI + API interna `/campanas/api/`) |
| `/avisos/` | Announcements |
| `/api/cases/` | Cases REST |
| `/api/knowledge/` | Knowledge REST |
| `/api/whatsapp/webhook/` | **Único** webhook Meta |
| `/admin/` | Django Admin |

Alias de compatibilidad: `/casos/` → bandeja, `/knowledge/` → knowledge, etc.

## Flujo WhatsApp de punta a punta

```
Estudiante WhatsApp
        │
        ▼
Meta Cloud API
        │
        ▼
POST /api/whatsapp/webhook/     (communications.webhooks.meta_webhook)
        │
        ├─ estados de entrega ──► BroadcastRecipient (campañas)
        └─ texto inbound ──────► knowledge.chatbot.whatsapp.handle_message
                                      │
                                      ├─ RAG / FAQ
                                      └─ si escala ──► cases.ingest_inbound_message
                                                            │
                                                            ▼
                                                     Bandeja /bandeja/
                                                            │
                                                     Asesora toma el chat
                                                            │
                                                     send_text_message (Meta)
                                                            │
                                                            ▼
                                                     Teléfono del contacto
```

Regla dura: ningún módulo llama a Graph API directo. Texto libre: `send_text_message`. Plantillas: `MetaAdapter.send_template_message` o `send_campaign()`.

## Dos modelos Contact (no confundir)

| Modelo | App | Uso |
| --- | --- | --- |
| `cases.Contact` | cases | Estudiante del ticket (documento único, semestre entero) |
| `communications.Contact` | communications | CDP de campañas (UUID, opt-in WhatsApp) |

El chatbot busca el contacto de comunicaciones por teléfono y copia datos al crear el ticket de cases.

## Auth

- UI: sesión Django (`login_required`). Login por username o email.
- `/api/cases/` y `/api/knowledge/`: permiso modular explícito en vistas y ViewSets; widget y webhooks conservan controles públicos propios.
- `/campanas/api/`: `IsInternalService` exige permiso explícito de Communications en sesión o `X-Internal-Token` válido para integraciones de servicio. `DEBUG=True` no omite la autorización. Usuarios con permiso de Announcements pueden listar segmentos y ver la vista previa acotada de contactos, sin permisos de escritura ni acceso general a Communications.
- Consola `/whatsapp-prueba/`, `/whatsapp-prueba/resultados/` y `/whatsapp-configuracion/`: requiere `is_staff` y acceso explícito a Communications; el superusuario activo pasa el control modular.

## Tiempo real

ASGI en `PuntoTdeA/asgi.py`. Consumers en `cases/consumers.py`:

- `ws/bandeja/` — lista de conversaciones
- `ws/conversations/<id>/` — mensajes de un chat

`cases.services.realtime` emite al tomar, responder o cerrar.

## Variables de entorno relevantes

Compose inyecta `.env` al contenedor `web`. Python **no** carga `.env` solo: sin Docker hay que exportar.

| Variable | Para |
| --- | --- |
| `DB_*` / `DATABASE_URL` | PostgreSQL |
| `REDIS_URL` | Channels |
| `META_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | Enviar |
| `META_APP_SECRET`, `META_VERIFY_TOKEN` | Recibir webhook |
| `INTERNAL_API_TOKEN` | API interna de campañas |
| `ALLOW_WEBHOOK_SIMULATOR` | `POST /api/cases/webhooks/simulate/` |

Tras editar `.env`: `docker compose up -d --force-recreate web` (un `restart` no refresca env).

## Hueco conocido (inbound de casos)

El ticket se crea cuando el bot **escala** (pide asesor o baja confianza). Los mensajes posteriores del estudiante se anexan al mismo caso y aparecen en la bandeja. Al tomar el chat, el asesor envía un saludo automático por WhatsApp.
