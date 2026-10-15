# AGENTS.md — PuntoTdeA

Instrucciones para sesiones de OpenCode en este repositorio.
**Responde siempre en español**: el código, la UI y la documentación están en español.

## Qué es este proyecto

Sistema Django 5.1 + DRF + Channels (ASGI/Daphne) para Punto TdeA: bandeja de
casos, base de conocimiento con chatbot RAG, campañas/avisos e integración con
Meta WhatsApp Cloud API. Front-end con templates Django + `static/css/styles.css`
(sin framework JS). Un solo proyecto Django (no monorepo). Apps: `cases`,
`knowledge`, `communications`, `announcements`, `dashboard` y la suite `tests`.
Entrada de arquitectura: `docs/arquitectura.md` y `docs/modulos/*.md`.

## Comandos verificados

- Todo corre en Docker (ver "Gotchas"): `docker compose up -d --build` y luego
  `docker compose exec -T web python manage.py migrate`.
- Pruebas completas: `docker compose exec -T web python manage.py test` (hoy
  ~250 casos, unos minutos, con SQLite y sin servicios externos). Local:
  `python manage.py test`.
- Subconjuntos: `python manage.py test communications knowledge`; un módulo
  `python manage.py test communications.tests.test_meta_console`; un archivo
  `python manage.py test tests.cases.test_e2e`.
- Diagnósticos Meta: `check_meta_whatsapp [--validate] [--callback-url URL]` y
  `check_meta_ads`.
- **No** hay linter, formateador ni typecheck. No inventes esos comandos.
- **Sí** hay CI desde octubre de 2026: `.github/workflows/ci.yml` corre
  `check --deploy --fail-level ERROR`, `collectstatic` y los tests con
  `DJANGO_DEBUG=false` (Python 3.12). `.github/workflows/cd.yml` solo dispara el
  deploy hook de Render (opcional). Ver `docs/despliegue-render.md`.

## Gotchas del entorno (fáciles de errar)

- **No hay Python local usable**: el `python` del PATH es el stub de Microsoft
  Store y no existe `.venv/`. Trabaja con Docker
  (`docker compose exec -T web python manage.py ...`); el contenedor trae todas
  las dependencias (Python 3.12). El CI también usa 3.12.
- **`.env` NO lo lee Python.** No hay `python-dotenv`; solo `docker compose`
  sustituye esas variables. Un `python manage.py ...` fuera de Docker no ve
  `.env`: exporta las variables a mano.
- Tras cambiar `.env`: `docker compose up -d --force-recreate web`. Un `restart`
  conserva las variables viejas y parece que "no funcionó". `configurar_meta.ps1`
  escribe `.env` (secretos ocultos) y recrea `web` por ti.
- `.env` está en `.gitignore` y `.dockerignore`: los secretos no se versionan ni
  viajan en la imagen.
- Base de datos: `DATABASE_URL` (Render) gana sobre las `DB_*` (Compose/CI);
  sin ninguna de las dos cae a SQLite local (`db.sqlite3`). Sin `REDIS_URL` el
  layer de canales es `InMemoryChannelLayer`.
- `DJANGO_SECRET_KEY` es obligatorio con `DJANGO_DEBUG=false` (si falta lanza
  `ImproperlyConfigured` al arrancar); con `DEBUG=true` hay una clave de desarrollo.
- `SILENCED_SYSTEM_CHECKS = ["fields.E210"]`: hay `ImageField` sin Pillow; no
  instales Pillow por eso. `MEDIA_UPLOADS_ENABLED=false` desactiva subidas
  (contenedor sin disco persistente).
- `main.py` es boilerplate de PyCharm sin uso.

## Suite de pruebas (`tests/` + apps)

- La app `tests/` (label `punto_tests`, registrada en `INSTALLED_APPS`) organiza
  pruebas **por módulo y nivel**: `test_unit.py`, `test_estados.py` y `test_e2e.py`.
  Fábricas compartidas en `tests/helpers.py`. Ver `tests/README.md`.
- Las pruebas históricas de cada app siguen vigentes: `cases/tests.py`,
  `knowledge/tests.py`, `knowledge/chatbot/tests.py`, `announcements/tests.py` y
  `communications/tests/{test_meta_console,test_meta_integration,test_meta_templates,
  test_cleanup_whatsapp_events,test_seed_demo,test_ads_service,test_campaign_wizard,
  test_internal_api,test_segments_contacts,test_templates_page,test_test_send}.py`.
- Stubs vacíos (0 bytes): `communications/tests/{test_adapters,test_campaign_service,
  test_models,test_webhooks}.py`.
- Convenciones: **no** llamar Graph API real (mockear `SendResult`/`MockAdapter`);
  para WhatsApp de cases parchear `cases.services.ingestion.send_text_message`;
  el webhook Meta usa `@override_settings` con secretos falsos + HMAC; **no**
  renderizar `/bandeja/` en Python 3.14 (usar `_bandeja_list_context`).
- La migración `cases/0002` siembra `Channel`/`Department`/`ReplyTemplate`: las
  pruebas dependen de esos datos de migración, no de fixtures.

## Integración Meta WhatsApp (regla dura)

- **Un único webhook**: `/api/whatsapp/webhook/`
  (`communications/webhooks/meta_webhook.py`), que recibe estados de campañas y
  mensajes entrantes del chatbot.
- Ningún otro módulo debe crear un webhook, revalidar la firma ni llamar a
  Graph API directamente. Usa `send_campaign()` o los adapters. Ver
  `docs/guia-uso-para-otros-modulos.md`.
- El alias `/base-de-conocimiento/chatbot/whatsapp/` reenvía a la misma vista y
  **no** se registra en Meta. `knowledge/README.md` está desactualizado al
  respecto.
- `BroadcastRecipient.provider_message_id` (wamid) solo lo escribe la ruta de
  envío; el webhook empareja los estados por ese campo. No editarlo a mano.
- `DEFAULT_ADAPTER = MetaAdapter()` en `campaign_service.py`; `MockAdapter` y
  `twilio_adapter.py` son legado.
- Las páginas `/whatsapp-prueba/` y `/whatsapp-configuracion/` son solo `is_staff`.
- `ALLOW_WEBHOOK_SIMULATOR` (por defecto `true` con `DEBUG`) habilita
  `POST /api/cases/webhooks/simulate/`.

## Comandos de datos (dry-run por defecto)

- `cleanup_whatsapp_events [--days N] [--ejecutar]` y
  `reset_whatsapp_test_data [--ejecutar]`: **sin `--ejecutar` solo informan**.
  `limpiar_retencion.ps1` los envuelve (ensayo + confirmación + log).
- Seeds idempotentes: `seed_knowledge`, `seed_demo_whatsapp`, `seed_demo_chats`,
  `ensure_demo_advisor`.
- `close_inactive_chats`: cierra chats de WhatsApp con más de 5 min inactivos;
  pensado para correr **periódicamente** (p. ej. cada minuto).
- `create_whatsapp_status_ad --texto ...` crea un anuncio de WhatsApp Status
  **PAUSED** por defecto (`--activar` lo publica).

## Mapa rápido

- UI: `/dashboard/`, `/bandeja/`, `/base-de-conocimiento/`, `/campanas/`,
  `/avisos/`, `/audiencias/`, `/plantillas/`.
- API: `/api/cases/`, `/api/knowledge/`, `/api/schema|docs|redoc/`.
  API interna (BFF): `/campanas/api/`.
- WebSocket: `ws/bandeja/`, `ws/conversations/<id>/` (`cases/routing.py`).
- Idioma `es-co`, zona `America/Bogota`, `USE_TZ=True`.
- El RAG (`knowledge/services/rag_service.py`) es similitud coseno por tokens en
  Python puro (no embeddings ni LLM); el proveedor LLM es un punto de extensión
  pendiente.
- `ENUM_NAME_OVERRIDES` de drf-spectacular apunta a enums de modelos:
  renombrarlos rompe `/api/schema/`.
- La API interna (`/campanas/api/`) la usa la propia UI de `/campanas/` desde el
  navegador. `IsInternalService` acepta sesión autenticada **o** el header
  `X-Internal-Token`; `INTERNAL_API_TOKEN` (leído del entorno) cubre a los
  consumidores de servicio (BFF) con `DEBUG=False`.

## Documentación (no duplicar)

- Entrada de arquitectura: `docs/arquitectura.md`; fichas por app en
  `docs/modulos/*.md`.
- Contrato de WhatsApp para otros módulos: `docs/guia-uso-para-otros-modulos.md`.
- Despliegue: `docs/despliegue-render.md`. Pruebas: `tests/README.md`.

## Producción y despliegue (Render)

- **Render despliega `dev`** (`branch:` en `render.yaml`) con
  `autoDeployTrigger: checksPass`. `.github/workflows/ci.yml` solo corre en
  `main` y `dev`: **si mueves la rama en `render.yaml`, actualiza `branches` en
  `ci.yml`**, o Render nunca verá un check verde y no desplegará, sin avisar.
- Para pasar a `main` hay que tocar **las dos** ramas: la línea `branch:` del
  `render.yaml` y (panel) *Blueprints → Settings → Branch*.
- `render.yaml` es el Blueprint: web (Docker) + Key Value + Postgres. El panel
  pide los `sync: false`; los secretos nunca van en el repo.
- Plan **gratis**: el servicio duerme a los 15 min, Postgres **expira a los 30
  días** y no hay disco persistente (se pierden las subidas de media). Ver
  `docs/despliegue-render.md` para pasar a pago.
- Con `DEBUG=False` los estáticos los sirve **whitenoise**: sin el
  `collectstatic` del build, `{% static %}` falla con
  "Missing staticfiles manifest entry".
- En plan gratuito **no existe `preDeployCommand`**: las migraciones corren en el
  **comando de arranque** (`entrypoint.sh`).
- **No pongas `dockerCommand`** ni en `render.yaml` ni en el panel de Render:
  Render lo pasa como una sola cadena, así que anidar `/bin/bash -c "..."` ahí
  rompe el escapado de comillas y el contenedor sale con 127
  (`command not found`). Deja **Docker Command vacío** en el panel para que Render
  use el `CMD` del Dockerfile (`sh /app/entrypoint.sh`).
- **El superusuario se crea en `entrypoint.sh`**, con `createsuperuser --noinput`
  y las variables `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD`. Es la
  única opción: el plan free no tiene Shell y la Postgres free no expone URL
  externa, así que el arranque es el único momento en que corre código. El
  `|| echo` convierte en no-op el "already taken" de cada redeploy y a propósito
  no resetea la contraseña de un usuario existente.
- **Quitar una clave de `render.yaml` no la borra de Render.** El valor guardado
  en el panel sigue mandando; hay que limpiarlo a mano en *Settings*. Solo la
  rama y los `envVars` se administran bien desde el blueprint.
- `SECURE_PROXY_SSL_HEADER` lee `X-Forwarded-Proto`: sin eso, Django cree que la
  petición es `http://` y rechaza el CSRF de los formularios de https.
- Para probar en local como producción hay que poner
  `DJANGO_SECURE_SSL_REDIRECT=false`: el test client usa `http://` y sin eso cada
  prueba que espera 200/302 recibe 301.
