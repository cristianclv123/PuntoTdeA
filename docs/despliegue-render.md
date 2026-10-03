# Despliegue en Render

## Resumen

| Pieza | Dónde vive | Plan |
|---|---|---|
| `render.yaml` | Blueprint declarativo (web + Key Value + Postgres) | free |
| `Dockerfile` | Imagen con whitenoise, collectstatic, migraciones y Daphne | — |
| `.github/workflows/ci.yml` | 90 pruebas + `check --deploy` + `collectstatic` | — |
| `.github/workflows/cd.yml` | Dispara el deploy cuando CI pasa en `main` | — |
| `PuntoTdeA/settings.py` | Ajustes de producción ( whitenoise, proxy, `DATABASE_URL`) | — |

Todo lo que hay en `render.yaml` se crea desde el Dashboard. **No hace falta
configurar nada a mano** salvo los valores marcados `sync: false`.

## Primer despliegue

1. **Sube el código a la rama que Render despliega.** Ahora mismo
   `render.yaml` apunta a `feature/JCFS/IntegracionAPIWA` (entorno de pruebas
   con la integración de WhatsApp):

   ```bash
   git add -A
   git commit -m "Despliegue en Render + anuncios de WhatsApp Status"
   git push origin feature/JCFS/IntegracionAPIWA
   ```

   Cuando la feature se fusione a `main`, vuelve a poner `branch: main` en
   `render.yaml` y Render cambia de rama en el siguiente sync.

2. **Crea el Blueprint** en <https://dashboard.render.com> → *New* → *Blueprint* →
   apunta a `cristianclv123/PuntoTdeA` y elige la rama
   `feature/JCFS/IntegracionAPIWA`.

3. **Completa las variables que Render te pida** (`sync: false`). Son las de
   credenciales de Meta y `WIDGET_ALLOWED_ORIGINS`. Copia los valores de tu `.env`
   local. `DJANGO_SECRET_KEY` e `INTERNAL_API_TOKEN` los genera Render solo.

4. **Registra el webhook en Meta Developers:**

   ```
   https://<TU-SERVICIO>.onrender.com/api/whatsapp/webhook/
   ```

   Es el único callback: recibe estados de campañas y mensajes del chatbot.
   El verify token es el mismo `META_VERIFY_TOKEN`.

5. **Crea el primer usuario staff** (el registro es manual en plan free):

   ```bash
   render shell puntotdea   # o la pestaña Shell del servicio en el Dashboard
   python manage.py createsuperuser
   ```

## Cómo funciona CI/CD

```
push a la rama  ->  CI corre  ->  checks en verde  ->  Render despliega
```

- El job de CI replica el entorno de Render: `DJANGO_DEBUG=false`,
  `SECURE_SSL_REDIRECT=false` (el test client habla `http://`) y un
  `collectstatic` previo (whitenoise exige el manifest).
- `render.yaml` usa `autoDeployTrigger: checksPass`: **Render espera a que los
  checks de GitHub Actions estén en verde**. Si CI falla, no hay despliegue.
- **La rama que Render despliega tiene que estar listada en `ci.yml`.** Si el CI
  no corre en ella no hay check verde, y Render no despliega nunca. Es el fallo
  más silencioso: el servicio simplemente nunca se actualiza.
- `cd.yml` es opcional. Si no creas el secreto `RENDER_DEPLOY_HOOK_URL`, avisa
  por `::notice::` y no rompe nada: el despliegue ya lo hace Render.

### Nota sobre el health check

`healthCheckPath` apunta a `/api/whatsapp/health/`, que exige sesión staff y
responde **302** al login. Render acepta cualquier 2xx o 3xx como sano, así que
funciona, pero solo por esa coincidencia. Si algún día un deploy se queda
colgado en "verificando salud", este es el primer sospechoso.

## De free a pagado

El plan gratuito funciona para validar, con estas tres limitaciones:

| Limitación | Efecto | Cómo se resuelve |
|---|---|---|
| El servicio duerme tras 15 min sin tráfico | La primera visita tarda ~1 min; Meta recibe error si hace webhook en ese momento | `plan: starter` en el servicio web |
| Postgres free expira a los 30 días | Tras 14 días de gracia, Render **borra la base** | `plan: basic-256mb` en `databases` |
| Sin disco persistente | Cada despliegue pierde imágenes y adjuntos subidos | Ver abajo |

Para pasar a pago, cambia tres líneas de `render.yaml`:

```yaml
services:
  - type: web
    plan: starter          # antes: free
  - type: keyvalue
    plan: 256mb            # antes: free
databases:
  - name: puntotdea-db
    plan: basic-256mb      # antes: free
```

Sube el cambio a `main` y Render aplica el plan nuevo.

## Sobre archivos subidos (media)

**Ahora mismo no hay media persistente.** Es una decisión consciente: en plan
gratuito Render no monta disco, así que las imágenes de avisos, los adjuntos de
casos y las imágenes del chatbot se guardan en el sistema de archivos efímero
del contenedor y **se pierden en el siguiente despliegue**.

Mientras tanto:

- `MEDIA_UPLOADS_ENABLED=true` deja subir los archivos (funcionan hasta el
  siguiente deploy).
- Si necesitas conservatism, ponlo en `false` en `render.yaml` y las vistas
  deberían avisar en vez de fallar con un error 500.

Cuando haya usuarios reales subiendo archivos, las dos salidas son:

1. **Disco persistente de Render** (lo más simple, requiere plan pago):
   añade al servicio web en `render.yaml` y monta en `/app/media`:

   ```yaml
   disk:
     name: media
     mountPath: /app/media
     sizeGB: 5
   ```

   Ojo: añadir un disco **desactiva los despliegues sin downtime**.

2. **S3 o Cloudflare R2** (escala mejor y sale más barato con muchos archivos):
   requiere `django-storages` + `boto3` y migrar los archivos existentes.

## Restricciones conocidas del plan gratuito

- El despliegue usa `migrate` dentro del comando de arranque, no
  `preDeployCommand`: **ese campo no existe en planes gratuitos**. Por eso el
  `CMD` del Dockerfile y el `dockerCommand` de `render.yaml` corren
  `python manage.py migrate --noinput` antes de levantar Daphne.
  Al migrar a plan pago, mueve las migraciones a `preDeployCommand`.
- `SECURE_HSTS_SECONDS` está en `0`. Actívalo cuando confirmes que el dominio
  final responde bien por HTTPS durante unos días, y solo si usas dominio
  propio: activar HSTS en `*.onrender.com` no es posible desde tu app.
- El Key Value no tiene persistencia en plan free. No importa: el channel layer
  es reconstruible y solo guarda mensajes en vuelo.

## Variables de entorno

Las define `render.yaml`; esta es la referencia de qué hace cada una.

| Variable | Origen | Para qué |
|---|---|---|
| `DJANGO_DEBUG` | `false` fijo | Apaga el modo debug. |
| `DJANGO_SECRET_KEY` | `generateValue` | Firma sesiones y CSRF. |
| `DATABASE_URL` | `fromDatabase` | Render entrega la cadena de Postgres; `settings.py` la parsea. |
| `REDIS_URL` | `fromService` | Canal layer de Channels. |
| `INTERNAL_API_TOKEN` | `generateValue` | **Sin esto la UI de `/campanas/` queda sin datos** en producción. |
| `META_*`, `WHATSAPP_*` | `sync: false` | Credenciales de la Cloud API. |
| `WIDGET_ALLOWED_ORIGINS` | `sync: false` | Orígenes CORS. Deja solo el dominio real. |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` | Súbelo a `31536000` cuando use dominio propio. |
| `MEDIA_UPLOADS_ENABLED` | `true` | Poner `false` desactiva la subida de archivos. |

`settings.py` toma `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` de
`RENDER_EXTERNAL_HOSTNAME`, que Render publica solo. No hace falta escribir el
dominio a mano en ningún sitio.

## Diagnóstico

```bash
# Estado de la integración de Meta (sin login en la URL, hay que estar staff)
curl https://<TU-SERVICIO>.onrender.com/api/whatsapp/health/

# Comprobaciones de Django
python manage.py check --deploy
python manage.py check_meta_whatsapp --validate
```

Si el CSS no carga, casi siempre es que `collectstatic` no corrió: revisa el log
de build de Render y confirma que el `Dockerfile` sigue incluyendo el paso de
`collectstatic`.

## Secretos

`.env.example` está **sin valores reales** y no se versiona nada de `.env`. Las
credenciales de Meta viven únicamente en el panel de Render.

Si un token se filtra, revócalo desde
<https://developers.facebook.com/apps> → *App Settings* → *Basic* → *Regenerar*
y actualiza la variable en Render. Nunca lo escribas en un archivo del repo.