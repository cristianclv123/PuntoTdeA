# Integración con Meta WhatsApp Cloud API

PuntoTdeA usa exclusivamente **Meta WhatsApp Cloud API**. Un solo webhook
recibe tanto los mensajes dirigidos al chatbot como los estados de entrega de
las campañas.

## Configuración local o de servidor

1. Copia `.env.example` como `.env` en la raíz del proyecto.
2. Completa los valores entregados en Meta Developers:

   ```dotenv
   META_VERIFY_TOKEN=un-secreto-largo-para-la-verificacion
   META_APP_ID=ID_DE_LA_APP
   META_APP_SECRET=APP_SECRET_DE_META
   META_ACCESS_TOKEN=TOKEN_PERMANENTE_O_DE_SISTEMA
   WHATSAPP_PHONE_NUMBER_ID=ID_DEL_NUMERO_EMISOR
   WHATSAPP_API_VERSION=v21.0
   ```

   `META_ACCESS_TOKEN`, `META_APP_SECRET` y `META_VERIFY_TOKEN` son secretos:
   no deben compartirse ni versionarse. El archivo `.env` está ignorado por Git
   y Docker no lo incorpora a la imagen.

3. Aplica la migración y recrea el servicio para que lea las variables:

   ```powershell
   docker compose up -d --build --force-recreate web
   docker compose exec -T web python manage.py migrate
   ```

## Configuración en Meta Developers

En **WhatsApp > Configuration** de la aplicación de Meta, registra:

- **Callback URL:** `https://TU-DOMINIO/api/whatsapp/webhook/`
- **Verify token:** el mismo valor de `META_VERIFY_TOKEN`.
- Suscripción del objeto WhatsApp al campo **`messages`**.

El callback debe estar expuesto por HTTPS. Para pruebas locales se puede usar
Cloudflare Tunnel o ngrok hacia `http://localhost:8000`.

El endpoint responde al desafío `GET` de Meta y en `POST` exige la firma
`X-Hub-Signature-256` construida con `META_APP_SECRET`.

> La antigua URL `/base-de-conocimiento/chatbot/whatsapp/` continúa como alias
> temporal, pero la URL que debe configurarse en Meta es la canónica anterior.

## Campañas

- Las campañas usan `MetaAdapter` directamente; no existe selector de
  proveedor.
- Solo se envían plantillas con estado local **Aprobada** y con el nombre e
  idioma exactamente iguales a los aprobados en Meta.
- Los parámetros del cuerpo se toman de `Campaign.default_params` y respetan
  su orden numérico. Ejemplo:

  ```json
  {
    "1": "contact.full_name",
    "2": "10 de octubre"
  }
  ```

- Los encabezados de imagen, video o documento requieren una URL pública en
  `header_media_url`.
- Meta devuelve un `wamid`; PuntoTdeA lo guarda en el destinatario de campaña.
  Los webhooks `sent`, `delivered`, `read` y `failed` actualizan sus estados y
  eventos de contacto sin duplicarlos ante reintentos de Meta.

La programación de campañas no es parte de esta integración: el programador o
worker del equipo de campañas debe invocar el envío en la fecha prevista y
respetar los límites de Meta.

## Chatbot

Cada mensaje de texto entrante del número configurado se entrega al flujo
existente de `knowledge.chatbot`; su respuesta se envía por Graph API. Los
mensajes no textuales se aceptan pero se ignoran hasta que el equipo del bot
defina su tratamiento.

Los identificadores de los mensajes entrantes y de los cambios de estado se
guardan en `WhatsAppWebhookEvent`. Esto evita responder dos veces cuando Meta
reintenta un webhook.

## Diagnóstico

Hay dos herramientas para saber en qué punto falla la cadena, sin tener que
inspeccionar logs a mano.

### Comando de diagnóstico

```powershell
docker compose exec -T web python manage.py check_meta_whatsapp
```

Solo lee la configuración y **no hace peticiones de red**, así que es seguro
ejecutarlo en cuanto se arranca el contenedor. Informa qué variables faltan y si
el flujo de envío, el de recepción de webhooks y el de verificación de la
suscripción están disponibles. Termina con código de salida `1` si algo falta,
de modo que sirve como sonda en un monitor.

Para confirmar contra Meta que el token sirve y que el número emisor existe:

```powershell
docker compose exec -T web python manage.py check_meta_whatsapp --validate
```

Esto consulta `debug_token` y `<PHONE_NUMBER_ID>` en Graph API y reporta los
permisos (`scopes`) del token, el nombre verificado y la calificación de
calidad del número.

Si ya tienes el callback público expuesto por HTTPS, añade `--callback-url`:

```powershell
docker compose exec -T web python manage.py check_meta_whatsapp `
  --callback-url https://TU-DOMINIO/api/whatsapp/webhook/
```

### Página de prueba

En `http://localhost:8000/whatsapp-prueba/` hay una página de verificación con
cuatro secciones: estado de la configuración, envío de un mensaje de prueba,
simulador del webhook y últimos eventos recibidos. No aparece en la navegación
del producto: se accede solo por URL y exige una sesión de personal `staff`.

El simulador firma un payload con la misma forma que envía Meta y lo entrega al
webhook real usando el cliente interno de Django, de modo que ejercita el
routing, la validación de firma y el procesamiento sin salir del contenedor. Los
escenarios son: mensaje entrante al chatbot, estado `delivered` y estado
`failed` de campaña.

> El simulador depende de `ALLOW_WEBHOOK_SIMULATOR`, que se apaga solo cuando
> `DEBUG` es `false`. No debe habilitarse en producción: un payload firmado con el
> App Secret es indistinguible de uno real de Meta.

### Resumen en JSON

`GET /api/whatsapp/health/` devuelve el mismo estado en JSON, sin exponer ningún
secreto. **Exige la misma sesión `staff` que la página de prueba**, así que no
sirve como sonda anónima: para automatizar el chequeo usa
`python manage.py check_meta_whatsapp`, que sí es apto para un script de
monitoring porque no necesita credenciales de la aplicación.

## Validación

Ejecuta las pruebas de la integración dentro de Docker:

```powershell
docker compose exec -T web python manage.py test communications.tests.test_meta_integration knowledge.chatbot.tests
```

La página de prueba tiene su propia suite:

```powershell
docker compose exec -T web python manage.py test communications.tests.test_meta_test_page
```

Antes de producción, valida con un número de prueba de Meta este recorrido:

1. Enviar una campaña con una plantilla aprobada.
2. Confirmar que se almacena el `wamid`.
3. Confirmar los eventos de entrega y lectura en el destinatario.
4. Enviar un texto desde WhatsApp al número configurado y recibir la respuesta
   del chatbot.
