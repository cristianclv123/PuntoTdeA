# AGENTS.md — PuntoTdeA

Instrucciones para sesiones de OpenCode en este repositorio.
**Responde siempre en español**: el código, la UI y la documentación están en español.

## Qué es este proyecto

Sistema Django 5.1 + DRF + Channels (ASGI/Daphne) para Punto TdeA: bandeja de
casos, base de conocimiento con chatbot RAG, campañas, avisos, notificaciones e
integración con Meta WhatsApp Cloud API. Front-end con templates Django +
`static/css/styles.css` (sin framework JS). Un solo proyecto Django (no
monorepo). Apps: `cases`, `knowledge`, `communications`, `announcements`,
`notifications`, `dashboard` y la suite `tests`.
Entrada de arquitectura: `docs/arquitectura.md` y `docs/modulos/*.md`.

## Comandos verificados

- Todo corre en Docker: `docker compose up -d --build` y luego
  `docker compose exec -T web python manage.py migrate`.
- Pruebas completas: `docker compose exec -T web python manage.py test` (~400
  métodos en ~47 archivos). En Docker usan la Postgres del compose salvo que
  fuerces SQLite; sin `DB_*`/`DATABASE_URL` caen a SQLite (CI/local).
- Para forzar SQLite dentro de Docker (evita tocar la Postgres del compose y
  dejar una base huérfana):
  `docker compose exec -T -e DB_HOST= -e DATABASE_URL= -e REDIS_URL= web python manage.py test ...`
- Subconjuntos: `python manage.py test communications knowledge`; un módulo
  `python manage.py test tests.cases` o `communications.tests.test_meta_console`;
  un archivo `python manage.py test tests.cases.test_e2e`.
- Diagnósticos Meta: `check_meta_whatsapp [--validate] [--callback-url URL]` y
  `check_meta_ads`.
- **No** hay linter, formateador ni typecheck. No inventes esos comandos.
- **Sí** hay CI: `.github/workflows/ci.yml` corre
  `check --deploy --fail-level ERROR`, `collectstatic` y los tests con
  `DJANGO_DEBUG=false` (Python 3.12). `.github/workflows/cd.yml` solo dispara el
  deploy hook de Render (opcional). Ver `docs/despliegue-render.md`.

## Gotchas del entorno (fáciles de errar)

- **No hay Python local usable**: el `python` del PATH es el stub de Microsoft
  Store y no existe `.venv/`. Trabaja con Docker (daemon de Docker Desktop
  encendido); el contenedor usa Python 3.12.
- **`.env` NO lo lee Python.** No hay `python-dotenv`; solo `docker compose`
  sustituye esas variables. Un `python manage.py ...` fuera de Docker no ve
  `.env`: exporta las variables a mano.
- Tras cambiar `.env`: `docker compose up -d --force-recreate web`. Un `restart`
  conserva las variables viejas y parece que "no funcionó". `configurar_meta.ps1`
  escribe `.env` (secretos ocultos) y recrea `web` por ti.
- `.env`, `media/` y `staticfiles/` están en `.gitignore`. `*.md`, `docs/` y
  `CloudFared/` no viajan en la imagen (`.dockerignore`).
- Base de datos: `DATABASE_URL` (Render) gana sobre las `DB_*` (Compose/CI); sin
  ninguna de las dos cae a SQLite local (`db.sqlite3`). Sin `REDIS_URL` el layer
  de canales es `InMemoryChannelLayer`.
- `DJANGO_SECRET_KEY` es obligatorio con `DJANGO_DEBUG=false` (si falta lanza
  `ImproperlyConfigured`); con `DEBUG=true` hay una clave de desarrollo.
- `SILENCED_SYSTEM_CHECKS = ["fields.E210"]` sigue activo aunque **Pillow ya está
  en `requirements.txt`**; no lo quites sin revisar los `ImageField`.
- Imágenes: avisos (`Announcement.image_data`) y FAQ (`FAQ.image_data`) se
  guardan como **bytes en la BD** y se sirven por vista propia. Los adjuntos de
  casos (`MessageAttachment`) van a `MEDIA_ROOT`, que en Render es efímero.
  `MEDIA_UPLOADS_ENABLED` existe en settings pero **hoy no se consulta**: no
  asumas que bloquea subidas.
- Las páginas de `/bandeja/` y `/casos/` envían CSP con `script-src 'self'`: no
  agregues `<script>` inline ni `onclick=`; el JS va en `cases/static/cases/js/`.
  El login también tiene CSP propia y `Cache-Control: no-store`.
- `main.py` es boilerplate de PyCharm sin uso.

## Permisos modulares (fácil de romper)

- Cada módulo exige un permiso explícito `{app}.access_{app}`:
  `cases.access_cases`, `knowledge.access_knowledge`,
  `communications.access_communications`, `announcements.access_announcements`.
- UI: `module_access_required(...)` (`PuntoTdeA/access.py`); API DRF:
  `HasModulePermission`; Admin: `ModuleAccessModelAdmin`. El superusuario activo
  siempre pasa.
- `PuntoTdeA/context_processors.py` expone `can_access_*` al sidebar. Una vista
  nueva sin decorador queda abierta a cualquier autenticado: es el error más
  probable.
- Consola Meta (`/whatsapp-prueba/`, `/resultados/`, `/whatsapp-configuracion/`,
  `/api/whatsapp/health/`): `communications_staff_required` = `is_staff` +
  permiso de Communications.
- API interna `/campanas/api/`: `IsInternalService` acepta sesión con permiso o
  `X-Internal-Token` = `INTERNAL_API_TOKEN`. `DEBUG=True` **no** omite el control.
- Announcements tiene una excepción de solo lectura sobre segmentos:
  `IsAnnouncementsSegmentReader` (solo `list`/`contacts`).

## Suite de pruebas (`tests/` + apps)

- La app `tests/` (label `punto_tests`, en `INSTALLED_APPS`) organiza pruebas
  **por módulo y nivel**: `test_unit.py`, `test_estados.py` y `test_e2e.py`.
  Fábricas compartidas en `tests/helpers.py`. Ver `tests/README.md`.
- Las pruebas históricas de cada app siguen vigentes: `cases/tests.py`,
  `knowledge/tests.py`, `knowledge/chatbot/tests.py`, `announcements/tests.py`,
  `notifications/tests.py` y `communications/tests/`.
- Stubs vacíos (0 bytes): `communications/tests/{test_adapters,test_models,test_webhooks}.py`.
- Convenciones: **no** llamar Graph API real (mockear `SendResult`/`MockAdapter`);
  para WhatsApp de cases parchear `cases.services.ingestion.send_text_message`;
  el webhook Meta usa `@override_settings` con secretos falsos + HMAC; **no**
  renderizar `/bandeja/` en Python 3.14 (usar `_bandeja_list_context`).
- La migración `cases/0002` siembra `Channel`/`Department`/`ReplyTemplate`: las
  pruebas dependen de esos datos de migración, no de fixtures.
- En PowerShell un `docker compose exec` puede devolver exit 1 por warnings en
  stderr; revisa la salida antes de asumir que los tests fallaron.

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
- `ALLOW_WEBHOOK_SIMULATOR` (por defecto `true` con `DEBUG`) habilita
  `POST /api/cases/webhooks/simulate/`.
- Plantillas de muestra (`hello_world`): `selectable_templates()` las oculta si
  hay plantillas propias aprobadas y solo las ofrece si son la única opción
  (consola de prueba). En campañas el wizard las filtra siempre y
  `verify_campaign_template()` las rechaza: no las habilites ahí sin tocar
  backend y tests.
- Status Ads usa **otro token** (`META_ADS_ACCESS_TOKEN` con `ads_management`),
  no el de Cloud API. La app de Meta debe estar en modo **Live**: en Desarrollo
  el creativo falla con `code 100, subcode 1885183`.

## Notificaciones

- `notifications/services.py` tiene `notify()`; `notifications/events.py`
  centraliza los textos de negocio (chats, campañas, plantillas, avisos,
  conocimiento). Crea avisos con esas funciones, no con `Notification.objects`
  a mano: así se emite el WebSocket y el payload queda uniforme.
- Dock en `templates/base.html` (`notifications/_dock.html`), API en
  `/notificaciones/api/` y WebSocket `ws/notificaciones/` (solo autenticados).
- Se disparan desde `cases.services` (ingesta, claim, cierre),
  `communications` (campaña y estados de plantilla) y `announcements`.

## Comandos de datos (dry-run por defecto)

- `cleanup_whatsapp_events [--days N] [--ejecutar]`,
  `reset_whatsapp_test_data [--ejecutar]` y
  `cleanup_campaign_personalizations [--ejecutar]`: **sin `--ejecutar` solo
  informan**. `limpiar_retencion.ps1` envuelve los dos primeros.
- Seeds idempotentes: `seed_knowledge`, `seed_demo_whatsapp`, `seed_demo_chats`,
  `ensure_demo_advisor`.
- `close_inactive_chats [--once] [--interval N]`: avisa a los 5 min de
  inactividad y cierra 2 min después (7 en total) si el usuario no responde.
  El ciclo puede correr **incrustado en el proceso web** con
  `ENABLE_INACTIVITY_SCHEDULER=true` (asi funciona en Docker y Render, sin
  servicios aparte) o como comando independiente con `--interval 60` para
  systemd/supervisor/cron. Sin `--interval` hace **una sola pasada**. No cierra
  conversaciones con ticket abierto. El estado vive en `ChatConversation` y los
  `UPDATE` condicionales evitan duplicados entre procesos.
- `run_scheduled_campaigns [--once] [--interval N]`: procesa campañas
  `scheduled` vencidas. El ciclo puede correr **incrustado en el proceso web**
  con `ENABLE_CAMPAIGN_SCHEDULER=true` (asi funciona en Docker y Render, sin
  servicios aparte) o como comando independiente con `--interval 30`.
- `create_whatsapp_status_ad --texto ...` crea un aviso de WhatsApp Status
  **PAUSED** por defecto (`--activar` lo publica).

## Mapa rápido

- UI: `/dashboard/`, `/bandeja/`, `/base-de-conocimiento/`, `/campanas/`,
  `/avisos/`, `/audiencias/`, `/plantillas/`.
- API: `/api/cases/`, `/api/knowledge/`, `/api/schema|docs|redoc/`.
  API interna (BFF): `/campanas/api/`.
- WebSocket: `ws/bandeja/`, `ws/conversations/<id>/` (`cases/routing.py`) y
  `ws/notificaciones/` (`notifications/routing.py`).
- Idioma `es-co`, zona `America/Bogota`, `USE_TZ=True`.
- El RAG (`knowledge/services/rag_service.py`) es similitud coseno por tokens en
  Python puro (no embeddings ni LLM); el proveedor LLM es un punto de extensión
  pendiente.
- `ENUM_NAME_OVERRIDES` de drf-spectacular apunta a enums de modelos: renombrarlos
  rompe `/api/schema/`.
- La UI de `/campanas/` usa la API interna desde el navegador; `IsInternalService`
  acepta sesión autenticada o el header `X-Internal-Token`.
- Los `Conversation`/`Message` de `cases` y los `Contact` de `communications` son
  modelos distintos: no los mezcles (ver `docs/arquitectura.md`).

## Documentación (no duplicar)

- Entrada de arquitectura: `docs/arquitectura.md`; fichas por app en
  `docs/modulos/*.md`.
- Contrato de WhatsApp para otros módulos: `docs/guia-uso-para-otros-modulos.md`.
- Despliegue: `docs/despliegue-render.md`. Pruebas: `tests/README.md`.
- Si la documentación y el código discrepan, **manda el código**. Deriva
  conocida: `docs/modulos/announcements.md` describe una vista previa que se
  revela al clic (ya no existe) y `tests/README.md` no menciona `notifications`.

## Producción y despliegue (Render)

- **Render despliega la rama configurada en `render.yaml`** con
  `autoDeployTrigger: checksPass`. Ahora mismo es
  `feature/JCFS/ChatbotFlujoInactivoDesciones`, para validar antes de integrar a
  `dev`. `.github/workflows/ci.yml` corre en `main`, `dev` y esa rama: **si mueves
  la rama en `render.yaml`, actualiza `branches` en `ci.yml`**, o Render nunca
  verá un check verde y no desplegará, sin avisar.
- Para pasar a `main` hay que tocar **las dos** ramas: la línea `branch:` del
  `render.yaml` y (panel) *Blueprints → Settings → Branch*.
- `render.yaml` es el Blueprint: web (Docker) + Key Value + Postgres. El panel
  pide los `sync: false`; los secretos nunca van en el repo.
- Plan **gratis**: el servicio duerme a los 15 min, Postgres **expira a los 30
  días** y no hay disco persistente (se pierden las subidas de media). No hay
  workers ni Cron Jobs; los ciclos de inactividad y campañas programadas pueden
  correr **incrustados en el web** con `ENABLE_INACTIVITY_SCHEDULER=true` y
  `ENABLE_CAMPAIGN_SCHEDULER=true`, pero solo mientras el contenedor está
  despierto. Ver `docs/despliegue-render.md` para pasar a pago.
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
- `healthCheckPath` es `/api/whatsapp/health/`, que exige sesión staff y responde
  302 al login. Render acepta 2xx/3xx como sano; si un deploy se queda en
  "verificando salud", este es el primer sospechoso.
