# Suite de pruebas (`tests/`)

Pruebas **por módulo**: unitarias, de **estados** y **E2E**. Django las descubre porque la app `tests` está en `INSTALLED_APPS`.

Las pruebas históricas dentro de cada app (`cases/tests.py`, `knowledge/tests.py`, `communications/tests/`, …) **siguen vigentes**. Esta carpeta suma el mapa completo y cubre huecos (estados, flujos de punta a punta).

## Cómo correr

```bash
# Todo el proyecto (CI y local)
python manage.py test --noinput

# Solo esta carpeta
python manage.py test tests --noinput

# Un módulo
python manage.py test tests.cases
python manage.py test tests.knowledge
python manage.py test tests.communications
python manage.py test tests.announcements
python manage.py test tests.dashboard
python manage.py test tests.nucleo

# Un archivo
python manage.py test tests.cases.test_e2e
```

Docker:

```bash
docker compose exec -T web python manage.py test tests --noinput
```

CI (`.github/workflows/ci.yml`) ya ejecuta `python manage.py test` con `DJANGO_DEBUG=false` y `collectstatic`.

## Qué hay en cada carpeta

| Carpeta | Unitarias | Estados | E2E |
| --- | --- | --- | --- |
| `cases/` | permisos, Meta outbound, saludo al claim | pendiente → asignado → escalado → cerrado | simulate webhook → claim → reply → close |
| `knowledge/` | RAG publicado vs borrador | workflow del chatbot | WhatsApp → ticket en cases |
| `communications/` | campaña + opt-out + MockAdapter | draft → sent; recipient pending/sent | webhook Meta verify + inbound idempotente |
| `announcements/` | login, StatusAd | — | listado de avisos |
| `dashboard/` | login, métricas WhatsApp | — | — |
| `nucleo/` | login usuario/email | — | landing → login → bandeja (contexto) |

## Convenciones

- **No** llamar Graph API real: `SendResult` mock o `MockAdapter`.
- WhatsApp de cases: parchear `cases.services.ingestion.send_text_message`.
- Webhook Meta: `@override_settings` con secretos falsos + HMAC.
- No renderizar `/bandeja/` en Python 3.14 (bug de copy del `RequestContext`); usar `_bandeja_list_context`.
- Fábricas: `tests/helpers.py`.

## Pirámide

1. Unitarias: un servicio, un permiso, un adaptador.
2. Estados: transiciones que el negocio no puede saltarse.
3. E2E: HTTP o `handle_message` de punta a punta, con Meta mockeada.
