# Integración con Meta WhatsApp Cloud API

PuntoTdeA usa exclusivamente **Meta WhatsApp Cloud API**. Un solo webhook
recibe tanto los mensajes dirigidos al chatbot como los estados de entrega de
las campañas.

> Este documento es la referencia de la integración. Los equipos de campañas y
> del bot tienen un documento propio para su parte:
> [`guia-consumo-webhook.md`](guia-consumo-webhook.md). Para saber **cómo usar
> la integración desde cada módulo** (qué llamar, cómo probar, qué no tocar):
> [`guia-uso-para-otros-modulos.md`](guia-uso-para-otros-modulos.md).

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

- **Callback URL:** `https://{DOMINIO-PUNTO-TdeA}/api/whatsapp/webhook/`
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
  --callback-url https://{DOMINIO-PUNTO-TdeA}/api/whatsapp/webhook/
```

### Páginas de la consola

Ambas están en el menú lateral, dentro del grupo **WhatsApp (Meta)**, y exigen
sesión de personal `staff`. El grupo no se renderiza para usuarios sin `is_staff`.

| Página | URL | Para qué |
| --- | --- | --- |
| Configuración | `/whatsapp-configuracion/` | Estado de las variables, capacidades, callback a registrar en Meta y los comandos para aplicar los cambios. **Solo lectura.** |
| Prueba de integración | `/whatsapp-prueba/` | Envío de mensajes y plantillas reales, y todo lo que Meta reporta de vuelta. Ver [`pagina-pruebas-whatsapp.md`](pagina-pruebas-whatsapp.md). |

La página de configuración es deliberadamente de solo lectura: no hay ningún
campo que escriba credenciales. Los secretos no travels por el navegador ni por
una sesión web, y siguen la vía que sí funciona: editar `.env` y recrear el
servicio. Un formulario que guardara el `.env` además surtiría efecto pendiente
de un `docker compose up --force-recreate` que el navegador no puede lanzar.

Ambas páginas comparten `communications/templates/communications/whatsapp_base.html`,
que concentra los estilos, para que las dos se vean igual.

La página de prueba **no simula nada**: todo lo que aparece en sus tablas viene de
Meta de verdad, para que un problema real no se confunda con uno de demostración.
La referencia completa de esa página está en
[`pagina-pruebas-whatsapp.md`](pagina-pruebas-whatsapp.md).

Para probarla a mano, el recorrido es:

1. Escribile **un saludo** al número de negocio desde un WhatsApp.
2. Esperá unos segundos y recargá: tiene que aparecer un evento `inbound` y una
   conversación del bot.
3. Dentro de las 24 horas siguientes, mandá un texto libre desde la página.

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

### Resumen en JSON

`GET /api/whatsapp/health/` devuelve el mismo estado en JSON, sin exponer ningún
secreto. **Exige la misma sesión `staff` que la consola**, así que no
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
  `opted_out`) con su `wamid`. Sirve para ver cómo se aplica un estado y cómo se
  respeta la no regresión de `read` en el admin, no para probar el webhook: sus
  `wamid` son sintéticos y Meta nunca mandará un estado con ese identificador.
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

La página de prueba (`/whatsapp-prueba/`) es el lugar donde se comprueba la
cadena completa. Antes de nada, revisá los dos puntos que más veces hacen creer
que todo está bien cuando no llega nada, porque **no se pueden comprobar por
API** y hay que mirarlos en el App Dashboard:

- **que la app esté en modo Live.** En modo Development Meta no manda webhooks
  reales. No es que fallen: es que no llegan. La verificación del `GET` sí
  funciona en Development, que es justo lo que hace pasar la casilla de
  "callback verificado" sin que después ocurra nada.
- **que estés suscrito al campo `messages`** del callback. Sin esa casilla el
  GET de verificación pasa, pero nunca llega un POST.

El resto de la configuración sí la comprueba la propia página; la referencia
completa está en [`pagina-pruebas-whatsapp.md`](pagina-pruebas-whatsapp.md).

El recorrido que reproduce un envío de verdad:

1. Pedile a alguien que escriba **un saludo** al número de negocio. El primer
   mensaje siempre se descarta y solo devuelve el saludo del bot, así que una
   conversación completa arranca con un saludo.
2. Recargá la página: el evento `inbound` aparece en *Eventos del webhook* y el
   hilo del bot en *Conversaciones del bot*.
3. Mandá un texto libre desde el primer formulario. Dentro de las 24 horas
   debería llegar al celular. El indicador de ventana te dice si esas 24 horas
   siguen abiertas antes de mandarlo.
4. Pasadas 24 horas, el texto libre se rechaza con el error `131047`. Usá el
   segundo formulario, que envía una plantilla aprobada.
5. Cada envío queda registrado con su `wamid` real en *Envíos de prueba*. Los
   estados que Meta reporte después aparecen agrupados por `wamid` en *Estados
   por mensaje*, como `sent` → `delivered` → `read`.

Un `POST /messages` puede devolver HTTP 200 con `wamid` y aun así no entregar:
el fallo llega después como un estado `failed` con su `errors[]`. Por eso la
página guarda el `wamid` de cada envío y muestra el motivo del fallo, en lugar
de informar solo que Meta aceptó el envío.

Los `wamid` de la semilla `seed_demo_whatsapp` son sintéticos y la página de
prueba no los usa: para ver estados reales hay que mandar algo y usar el
`wamid` que devuelve Meta. Para dejar la consola en cero:

```powershell
docker compose exec -T web python manage.py reset_whatsapp_test_data --ejecutar
```

Para correr la integración dentro de Docker:

```powershell
docker compose exec -T web python manage.py test communications knowledge
```

La consola tiene su propia suite, que incluye las guardas de las dos páginas y
del menú lateral:

```powershell
docker compose exec -T web python manage.py test communications.tests.test_meta_console
```
