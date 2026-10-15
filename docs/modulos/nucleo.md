# Módulo Núcleo (`PuntoTdeA/`)

Proyecto Django: configuración, URLs raíz, autenticación y landing pública.

## Árbol

```
PuntoTdeA/
  settings.py      # Django, DRF, Channels, seguridad, Meta
  urls.py          # incluye todas las apps
  views.py         # home, login, logout, perfil
  asgi.py          # HTTP + WebSocket
  wsgi.py          # no usado en Docker (Daphne)
```

También en la raíz del repo (no son una app):

| Ruta | Rol |
| --- | --- |
| `manage.py` | CLI Django |
| `templates/` | `base.html`, `index.html` (landing), `login.html`, `dashboard.html` vía apps |
| `static/css/` | `styles.css`, `landing.css` |
| `docker-compose.yml`, `Dockerfile`, `entrypoint.sh` | Runtime |
| `requirements.txt` | Dependencias |

## `settings.py` (puntos que importan)

- `INSTALLED_APPS`: `cases`, `knowledge`, `communications`, `announcements`, `dashboard`, DRF, spectacular, channels, cors.
- `AUTH`: `User` de Django (`django.contrib.auth`).
- `REST_FRAMEWORK`: autenticación por sesión; permiso por defecto `AllowAny` (cada vista declara el suyo).
- `CHANNEL_LAYERS`: Redis si hay `REDIS_URL`.
- Meta: `META_*`, `WHATSAPP_*` leídos de `os.environ`.
- Producción: WhiteNoise, `SECURE_PROXY_SSL_HEADER` para CSRF detrás de Render.

## Vistas (`views.py`)

| Vista | Ruta | Auth | Qué hace |
| --- | --- | --- | --- |
| `home` | `/` | pública | Landing; métricas WhatsApp abiertos / cerrados hoy |
| `login_view` | `/login/` | pública | Usuario o email + password; `remember` = 14 días |
| `logout_view` | `/logout/` | sesión | Cierra sesión |
| `profile_view` | `/perfil/` | login | Nombre, email, cambio de contraseña |

Tras login exitoso: `dashboard:index`, o `next` si es path relativo seguro.

## URLs montadas desde aquí

Ver tabla en [arquitectura.md](../arquitectura.md). El webhook Meta **solo** se registra como `/api/whatsapp/webhook/`. El alias `/base-de-conocimiento/chatbot/whatsapp/` llama la misma función y **no** se configura en Meta Developers.

## Arranque

- Docker: `daphne -b 0.0.0.0 -p 8000 PuntoTdeA.asgi:application`
- Migraciones y superusuario: `entrypoint.sh` en Render
- Comandos: `python manage.py migrate`, `collectstatic`, `test`

## Qué no vive aquí

Lógica de negocio de tickets, campañas o FAQ: va en su app. El núcleo solo orquesta includes y auth.
