# AGENTS.md — PuntoTdeA

Instrucciones para sesiones de OpenCode en este repositorio.
**Responde siempre en español**: el código, la UI y la documentación están en español.

## Qué es este proyecto

Sistema Django 5.1 + DRF + Channels (ASGI/Daphne) para Punto TdeA: bandeja de
casos, base de conocimiento con chatbot RAG, campañas/avisos e integración con
Meta WhatsApp Cloud API. Front-end con templates Django + `static/css/styles.css`
(sin framework JS).

## Comandos verificados

- Ruta documentada con Docker: `docker compose up -d --build` y luego
  `docker compose exec -T web python manage.py migrate`.
- Pruebas completas: `docker compose exec -T web python manage.py test`
  (local: `python manage.py test`; hoy son 80 pruebas, ~2,5 min, con SQLite y sin
  servicios externos).
- Subconjunto usado en docs: `python manage.py test communications knowledge`
- Un módulo: `python manage.py test communications.tests.test_meta_console`
- Diagnóstico de Meta: `python manage.py check_meta_whatsapp [--validate]`
- **No** hay linter, formateador, typecheck ni CI. No inventes esos comandos.

## Gotchas del entorno (fáciles de errar)

- **`.env` NO lo lee Python.** No hay `python-dotenv`; solo `docker compose`
  sustituye esas variables. `python manage.py ...` local no ve `.env`: exporta
  las variables a mano.
- Tras cambiar `.env`: `docker compose up -d --force-recreate web`. Un `restart`
  conserva las variables viejas y parece que "no funcionó".
- `.venv/` está roto/vacío (solo pip/setuptools, sin `python.exe`). Usa el
  `python` del PATH (3.11) o crea un venv nuevo. Docker usa Python 3.12.
- `drf-spectacular` falta en el Python global de esta máquina: `manage.py` falla
  con `ModuleNotFoundError: No module named 'drf_spectacular'` hasta correr
  `pip install -r requirements.txt`.
- Sin `DB_HOST` la base es SQLite local; en Docker es PostgreSQL.

## Integración Meta WhatsApp (regla dura)

- **Un único webhook**: `/api/whatsapp/webhook/`
  (`communications/webhooks/meta_webhook.py`), que recibe estados de campañas y
  mensajes entrantes del chatbot.
- Ningún otro módulo debe crear un webhook, revalidar la firma ni llamar a
  Graph API directamente. Usa `send_campaign()` o los adapters. Ver
  `docs/guia-uso-para-otros-modulos.md`.
- El alias `/base-de-conocimiento/chatbot/whatsapp/` apunta a la misma vista y
  **no** se registra en Meta. `knowledge/README.md` está desactualizado al
  respecto.
- `BroadcastRecipient.provider_message_id` (wamid) solo lo escribe la ruta de
  envío; el webhook empareja los estados por ese campo. No editarlo a mano.
- `DEFAULT_ADAPTER = MetaAdapter()` en `campaign_service.py`; `MockAdapter` y
  `twilio_adapter.py` son legado.
- Las páginas `/whatsapp-prueba/` y `/whatsapp-configuracion/` son solo `is_staff`.

## Comandos de datos (dry-run por defecto)

- `cleanup_whatsapp_events [--days N] [--ejecutar]` y
  `reset_whatsapp_test_data [--ejecutar]`: **sin `--ejecutar` solo informan**.
- Seeds idempotentes: `seed_knowledge`, `seed_demo_whatsapp`, `seed_demo_chats`.
- La migración `cases/0002` siembra `Channel`/`Department`/`ReplyTemplate`; las
  pruebas dependen de esos datos de migración, no de fixtures.

## Pruebas

- Con contenido real: `cases/tests.py`, `knowledge/tests.py`,
  `knowledge/chatbot/tests.py` y `communications/tests/{test_meta_console,
  test_meta_integration,test_cleanup_whatsapp_events,test_seed_demo}.py`.
- Stubs vacíos (0 bytes): `communications/tests/{test_adapters,
  test_campaign_service,test_models,test_webhooks}.py`. `announcements/tests.py`
  y `dashboard/tests.py` son la plantilla por defecto.
- Los tests de webhook usan `@override_settings` con credenciales Meta falsas.

## Mapa rápido

- UI: `/dashboard/`, `/bandeja/`, `/base-de-conocimiento/`, `/campanas/`,
  `/avisos/`.
- API: `/api/cases/`, `/api/knowledge/`, `/api/schema|docs|redoc/`.
  API interna (BFF): `/campanas/api/`.
- WebSocket: `ws/bandeja/`, `ws/conversations/<id>/` (`cases/routing.py`).
- Idioma `es-co`, zona `America/Bogota`, `USE_TZ=True`.
- El RAG (`knowledge/services/rag_service.py`) es similitud coseno por tokens en
  Python puro (no embeddings ni LLM); el proveedor LLM es un punto de extensión
  pendiente.
- `ENUM_NAME_OVERRIDES` de drf-spectacular apunta a enums de modelos:
  renombrarlos rompe `/api/schema/`.
- `INTERNAL_API_TOKEN` se referencia en `communications/permissions.py` pero no
  existe en settings: con `DEBUG=False` la API interna (`/campanas/api/`) queda
  inaccesible.
