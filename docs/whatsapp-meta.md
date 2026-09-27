# Integración con Meta WhatsApp Cloud API

PuntoTdeA usa exclusivamente **Meta WhatsApp Cloud API**. Un solo webhook
recibe tanto los mensajes dirigidos al chatbot como los estados de entrega de
las campañas.

## Configuración local o de servidor

Hay dos caminos. El script es una comodidad, no una dependencia: si prefieres
editar el archivo a mano, el resultado es idéntico.

### Con el asistente

```powershell
powershell -ExecutionPolicy Bypass -File .\configurar_meta.ps1
```

Pide el App secret, el Access token y el Phone Number ID con entrada oculta, y
**genera el `META_VERIFY_TOKEN` por ti** porque ese valor no lo entrega Meta: lo
eliges tú al registrar el callback. Después escribe el `.env`, recrea el
servicio y ejecuta el diagnóstico. Usa `-SinRecrear` si solo quieres escribir el
archivo.

De nuevo: solo tres valores vienen de Meta. `META_APP_ID` es opcional y la API
no lo necesita.

### A mano

1. Copia `.env.example` como `.env` en la raíz del proyecto.
2. Completa los valores:

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

> Las credenciales llegan al contenedor como variables de entorno, así que
> hace falta **recrear** (`up -d --force-recreate`), no reiniciar
> (`restart`). Un `restart` deja las variables viejas.

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
escenarios son:

- **Guion completo del bot:** reproduce los cinco turnos de la conversación
  (saludo → pregunta → confirmación → escalado al asesor → cierre) como cinco
  webhooks independientes y firmados, para que la máquina de estados avance de
  verdad y no se salte pasos.
- **Un solo mensaje entrante**, con el texto que quieras o el de ejemplo.
- **Estado `delivered`** y **estado `failed`** de campaña, indicando el `wamid`
  que devolvió Meta al enviar.

> El bot ignora el texto del primer mensaje y solo devuelve el saludo, así que
> al probar a mano por WhatsApp el primer mensaje debe ser un saludo: la
> pregunta solo se procesa a partir del segundo.

Las respuestas del bot quedan en `/admin/knowledge/chatconversation/`, donde se
ven el `flow_state` y el `status` de cada conversación. Ten en cuenta que el bot
intenta responder por WhatsApp al número que escribes: con un número falso la
lógica se ejecuta y se guarda, pero la respuesta no te llega al celular.

Dos detalles del entorno que confunden al probar:

- La respuesta a la pregunta sale de la base de conocimiento. Si está vacía el
  bot contesta «No encontré información suficiente…» y eso **es el
  comportamiento correcto**. Carga contenido con
  `docker compose exec -T web python manage.py seed_knowledge`.
- El cierre por escalado cambia según el horario de atención configurado: fuera
  de horario el bot dice que la solicitud queda pendiente.

> El simulador depende de `ALLOW_WEBHOOK_SIMULATOR`, que se apaga solo cuando
> `DEBUG` es `false`. No debe habilitarse en producción: un payload firmado con el
> App Secret es indistinguible de uno real de Meta.

### Resumen en JSON

`GET /api/whatsapp/health/` devuelve el mismo estado en JSON, sin exponer ningún
secreto. **Exige la misma sesión `staff` que la página de prueba**, así que no
sirve como sonda anónima: para automatizar el chequeo usa
`python manage.py check_meta_whatsapp`, que sí es apto para un script de
monitoring porque no necesita credenciales de la aplicación.

## Datos de demostración

Para probar sin esperar a tener contactos reales:

```powershell
docker compose exec -T web python manage.py seed_demo_whatsapp
```

Crea 8 contactos, 2 segmentos, 2 plantillas y 2 campañas:

- **«Demo: recordatorio de matrícula (enviada)»** tiene un destinatario en cada
  estado posible (`pending`, `queued`, `sent`, `delivered`, `read`, `failed`,
  `opted_out`) con su `wamid`. Es lo que permite probar el webhook de estados:
  pega un `wamid` de la lista en el simulador y observa cómo avanza el
  destinatario y cómo se respeta la no regresión de `read`.
- **«Demo: bienvenida a admitidos (borrador)»** queda con todos sus
  destinatarios en `pending`, que es lo que el envío real procesa. Úsala cuando
  tengas credenciales para probar un envío de verdad.

Notas:

- Los `wamid` son **sintéticos** (`wamid.SEED0001`…), no provienen de Meta. El
  prefijo existe para que no se confundan con los reales.
- La plantilla aprobada se llama `recordatorio_matricula_2026`. Para que un
  envío real funcione, ese nombre debe coincidir con una plantilla aprobada en
  tu cuenta de Meta; si no, Meta la rechaza.
- No se envía nada a Meta al ejecutar el comando.
- Es idempotente: repetirlo no duplica nada.
- Se niega a correr si `DEBUG` está apagado, salvo que le pases `--force`: una
  semilla de contactos y campañas ficticias en producción crearía campañas con
  aspecto real. Para borrar lo sembrado:

  ```powershell
  docker compose exec -T web python manage.py seed_demo_whatsapp --limpiar
  ```

  Solo borra lo marcado como demostración; los contactos que ya tuvieras se
  conservan.

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
