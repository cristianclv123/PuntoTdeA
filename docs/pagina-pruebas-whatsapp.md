# La página de pruebas de WhatsApp (`/whatsapp-prueba/`)

Documento de referencia de la consola interna que verifica la integración con
Meta WhatsApp Cloud API. Explica qué hace cada sección, qué ocurre en cada lado
—nuestro servidor y el de Meta— y qué hay que tener configurado en el App
Dashboard para que todo funcione.

**No es parte del producto.** No la ven los estudiantes ni los coordinadores.
Solo entra el personal con `is_staff`, mediante el decorador `_staff_required`.

---

## 1. Qué es y qué no es

Es una página de diagnóstico, no un panel de negocio. Existe para responder una
pregunta concreta: *¿está bien conectada la integración, y si no, en qué punto
se rompe?*

Por diseño **no simula nada**. Todo lo que aparece en las tablas viene de Meta de
verdad. La regla es simple:

> Si algo aparece en las tablas de esta página, ocurrió en la cuenta real.

Cuando algo falla, la página muestra el motivo exacto que devolvió Meta, no una
interpretación genérica. Eso obliga a que cada paso sea verificable por fuera.

---

## 2. Anatomía de la página

La página tiene dos columnas: a la izquierda, las acciones de envío y las tablas
de lo que se recibió; a la derecha, el estado de la configuración y el recorrido
esperado.

### 2.1 Enviar mensaje de texto

Formulario que hace un `POST` real a `/{PHONE_NUMBER_ID}/messages` con
`type: text`. Es el envío más simple, y también el que más confunde, porque
**no siempre funciona**.

La regla de Meta es la siguiente:

- Meta solo entrega texto libre dentro de una **ventana de servicio de 24 horas**.
- Esa ventana **solo la abre el usuario**, y únicamente cuando **él** escribe
  primero. Nosotros no podemos abrirla.
- Pasadas las 24 horas, el envío falla con el error **131047**
  (*"Message failed to send because more than 24 hours have passed"*).

Es decir: si nunca te escribieron, no hay forma de que un texto libre llegue.
Por eso la página lleva un campo de teléfono que consulta la ventana antes de
enviar (ver §3.1).

### 2.2 Enviar plantilla aprobada

La **única** vía que funciona fuera de la ventana de 24 horas.

Envía `type: template` con el nombre exacto de la plantilla aprobada en la
cuenta de Meta. El selector offers una opción por cada plantilla **aprobada** en
la base de datos, y al elegir una aparecen los campos de parámetros que
corresponden a sus marcadores `{{1}}`, `{{2}}`, etc.

Los índices de los marcadores se extraen del cuerpo de la plantilla, no de
`param_count`: el formulario necesita saber *qué* marcadores hay, no cuántos.

Si la plantilla tiene encabezado multimedia, la página avisa que hace falta
configurar `header_media_url`, porque Meta rechaza la plantilla sin ella.

Si no hay ninguna plantilla aprobada, la tarjeta lo dice explícitamente. Es un
bloqueo real: sin plantilla aprobada no hay forma de iniciar una conversación,
porque el texto libre está condicionado a la ventana de 24 horas.

### 2.3 Estados por mensaje

Agrupa los eventos de estado de un mismo `wamid` en el orden en que los reportó
Meta, formando una línea de tiempo: `sent` → `delivered` → `read`, o
`failed` con su motivo.

Un envío hecho desde esta página queda registrado con su `wamid` real, así que
esta tabla se llena sola. Si un estado llega `failed`, se muestra el código y el
texto de error de Meta traducidos a algo accionable (ver §4).

### 2.4 Envíos de prueba con wamid

Cada envío hecho desde la página, con el `wamid` que devolvió Meta y un botón
para copiarlo. Sirve para correlacionar: copiá un `wamid` y buscá esa misma
cadena en "Estados por mensaje" para ver cómo avanzó.

Estos registros se guardan en la misma tabla que los eventos del webhook, con
una clave que los distingue. Por eso los mensajes de `error 131047` y compañía
quedan guardados aunque el webhook nunca los reporte.

### 2.5 Eventos del webhook

Todo lo que Meta ha enviado por POST al callback, con su marca de procesamiento.

El campo "Procesado" distingue dos cosas:

- una hora → el webhook lo procesó;
- `pendiente` → Meta lo entregó pero el procesamiento no terminó.

También sirve para verificar **idempotencia**: cada evento tiene una
`event_key` única, así que si Meta reintenta un POST, el segundo intento se
registra como duplicado y no se procesa dos veces.

### 2.6 Conversaciones del bot

Las conversaciones originadas por WhatsApp, con el último mensaje de la persona
y la última respuesta del bot.

**Advertencia importante que la página 강조:** el primer mensaje entrante
**siempre se descarta** y solo devuelve el saludo, sin importar qué haya escrito
la persona. Es el comportamiento del chatbot (`knowledge/chatbot/whatsapp.py`),
no un error. Para una conversación completa, el primer mensaje tiene que ser un
saludo.

### 2.7 Destinatarios de campaña con wamid

Aparece solo si hay destinatarios. Son los registros contra los que Meta aplica
los estados de las campañas: cuando llega un `status`, se busca el destinatario
por su `provider_message_id` y se actualiza su estado y su `read_at`.

### 2.8 Estado de configuración (columna derecha)

Un punto de luz por cada variable del entorno, con el detalle en el tooltip:

- verde → configurada;
- rojo → falta y es obligatoria;
- amarillo → falta y es opcional.

**Estos puntos solo miran el `.env`.** Dicen que la variable existe, no que el
token siga vivo. Por eso está, justo debajo, el botón **"Validar credenciales con
Graph API"**, que sí hace la consulta real:

1. `GET /debug_token` → si el token es válido, qué app es y qué permisos tiene;
2. `GET /{PHONE_NUMBER_ID}` → el número, su nombre verificado, su nivel de
   calidad y si está en modo Cloud API.

La diferencia es importante: una variable puede estar perfectamente escrita y el
token llevar meses revocado. Solo la segunda consulta lo detecta.

### 2.9 Recorrido completo (columna derecha)

Los cuatro pasos, en orden, de la prueba completa. Es el guion de qué hacer:

1. Alguien escribe **un saludo** al número de negocio.
2. Meta hace POST al callback; se ve el evento `inbound` y arranca el hilo del bot.
3. Dentro de 24 horas, se manda un texto libre desde la página.
4. Pasadas 24 horas, se usa la plantilla, porque el texto libre ya no llega.

---

## 3. Los tres flujos, paso a paso

### 3.1 Entrada: alguien escribe al número

**Qué hace la persona.** Abre WhatsApp, busca el número de negocio y escribe
`Hola`.

**Qué hace Meta.**

1. Entrega el mensaje al número de la cuenta de Cloud API.
2. Arma un POST al callback configurado en el App Dashboard.
3. Firma el cuerpo con el **App Secret** y manda la cabecera
   `X-Hub-Signature-256: sha256=...`.
4. Espera un **200**. Cualquier otra cosa y lo reintenta.

**Qué hace nuestra aplicación.**

1. `webhooks/meta_webhook.py` valida la firma con el App Secret. Si no cuadra,
   responde `403` y descarta: es lo que impide que cualquiera pueda inyectar
   mensajes falsos.
2. Guarda el evento en `WhatsAppWebhookEvent` con una `event_key` única. Si ya
   existía, es un reintento de Meta: lo cuenta como duplicado y no lo reprocesa.
3. Lo pasa al chatbot.
4. El chatbot descarta el primer mensaje y responde con el saludo. Esa respuesta
   la mandamos nosotros a Meta con la API.
5. Devuelve `200`.

**Qué se ve en la página.** Un evento `inbound` en "Eventos del webhook" y una
conversación nueva en "Conversaciones del bot". Si no aparece nada, Meta no está
llegando: el problema está en la configuración del App Dashboard (§5), no en el
código.

> La función `service_window()` busca los mensajes entrantes por
> `payload__from`, así que solo ve los registrados a partir de la migración
> `0004`. Los anteriores no se retrospectan.

### 3.2 Salida: texto libre dentro de las 24 horas

**Qué hace nuestra aplicación.** `POST /{PHONE_NUMBER_ID}/messages` con
`type: text` y el número destino.

**Qué hace Meta.**

1. Valida el token, el `Phone Number ID` y que el número exista.
2. Comprueba que el mensaje entre dentro de la ventana de 24 horas.
3. Si la comprobación falla, responde con **HTTP 400** y `error.code = 131047`.
4. Si todo está bien, responde con **HTTP 200** y un `wamid`.

**Qué hace nuestra aplicación con la respuesta.** Registra el `wamid` en la
tabla de envíos de prueba y muestra el resultado. Si vino un error, busca el
código en la tabla de errores conocidos y lo traduce.

### 3.3 Los estados: el paso que casi nadie mira

Este es el punto clave de la integración y el que más confunde.

**Un `200` en el envío no significa entregado.** El `200` con su `wamid` solo
confirma que **Meta aceptó el mensaje**. La entrega ocurre después, de forma
asíncrona.

**Qué hace Meta.** Minutos después (o el mismo día) manda un POST al callback
por cada cambio de estado:

```json
{"statuses": [{"id": "wamid.XXX", "status": "delivered"}]}
```

La secuencia normal es `sent` → `delivered` → `read`. Si algo sale mal, llega
`failed` con un arreglo `errors[]` que trae el código y el texto del motivo.

**Qué hace nuestra aplicación.**

1. Valida la firma y registra el evento.
2. Busca el `wamid` en `BroadcastRecipient.provider_message_id` y actualiza el
   estado del destinatario. Si no lo encuentra, deja el evento marcado como
   `unmatched` en el `payload` para que el motivo quede a la vista.
3. El fragmento crudo del evento se guarda en `payload`, precisamente para no
   perder el `errors[]` de un `failed` que no corresponde a ningún destinatario.

**Por qué importa.** Si solo mirás la respuesta del envío, creés que todo salió
bien. El fallo de entrega aparece **después**, y es el único lugar donde se ve.

---

## 4. Los errores que vas a ver

`communications/services/meta_errors.py` traduce los códigos más frecuentes a un
texto accionable. Si el código no está en la tabla, se muestra el texto crudo de
Meta, para no inventar un diagnóstico.

| Código | Qué pasó | Qué hacer |
| --- | --- | --- |
| `131047` | Pasaron más de 24 h desde que ese número te escribió | Usar una plantilla aprobada, o pedirle que te escriba |
| `131026` | Meta no pudo entregar el mensaje | Suele ser que no tenga WhatsApp, no aceptó los Términos, o tenga la app antigua |
| `131050` | Ese destinatario pidió no recibir marketing | No reintentar; dejar de enviarle plantillas de categoría marketing |
| `131049` | Meta decidió no entregar este mensaje | Límite de frecuencia por usuario: esperar al menos 24 h |
| `131048` | Tiene restringidos cuántos mensajes puede recibir | Revisar la calidad del número en WhatsApp Manager |
| `130429` | Límite de mensajes de la API de Meta | Esperar unos minutos o bajar la frecuencia de envío |
| `132001` | Meta no conoce esa plantilla en ese idioma | El nombre tiene que coincidir exactamente; revisar también el idioma, por ejemplo `es_CO` |
| `132000` | La cantidad de parámetros no coincide | Revisar cuántos marcadores `{{1}}`, `{{2}}`... tiene el cuerpo en Meta |

La página muestra siempre la explicación **junto al texto crudo de Meta**, para
poder contrastar los dos.

---

## 5. Qué hay que configurar en Meta Developers

Lo de arriba lo comprueba la página. **Lo de esta sección no**, porque son
pantallas del App Dashboard y no se pueden leer por API. Son, sin embargo, los dos
motivos más habituales por los que una integración bien configurada no recibe
nada.

### 5.1 La app tiene que estar en modo Live

**Dónde:** App Dashboard → tu app → *App settings* → *Basic*, arriba del todo,
el interruptor **App Mode**.

**Por qué importa:** una app en modo **Development** no entrega webhooks reales.
No es que fallen: es que no llegan. Es la causa número uno de "configuré todo y
no me entra nada".

> Lo que sí funciona en modo Development es el desafío de verificación (el `GET`
> con `hub.verify_token`), que es exactamente lo que hace pasar la casilla de
> "callback verificado" sin que después funcione nada. Es la trampa más
> desconcertante de toda la integración.

### 5.2 Suscribirse al campo `messages`

**Dónde:** App Dashboard → *WhatsApp* → *Configuration* → *Webhooks* →
*Edit*, campo **Subscribe to fields**.

**Por qué importa:** la casilla se puede dejar vacía y la verificación del
callback sigue dando el `200` esperado. Pero sin suscribirse a **`messages`**
**no llega ni un solo POST**. Lo que sí llega, si te suscribiste, son los
mensajes de estado de las campañas — y por eso a veces parece funcionar a medias.

### 5.3 El callback tiene que ser público y por HTTPS

**Dónde:** App Dashboard → *WhatsApp* → *Configuration* → *Webhooks* → *Callback
URL* y *Verify token*.

El `Verify token` tiene que coincidir exactamente con `META_VERIFY_TOKEN` en el
`.env`. El callback es la ruta que define `meta_config.WEBHOOK_PATH`, es decir
`/api/whatsapp/webhook/`, sobre el dominio público. Un `localhost` no sirve: Meta
no lo puede alcanzar.

### 5.4 El token tiene que tener el permiso de envío

**Dónde:** App Dashboard → tu app → *WhatsApp* → *API Setup*.

El token del sistema necesita el permiso **`whatsapp_business_messaging`**. Sin
él, la verificación del token pasa (el token es válido) pero el envío se rechaza.

### 5.5 Qué mira la página y qué no

| Comprobación | ¿La ve la página? |
| --- | --- |
| Las variables existen en el `.env` | Sí, los puntos de luz |
| El token sigue válido | Sí, botón "Validar credenciales" |
| El token tiene los permisos correctos | Sí, con el mismo botón |
| El número existe y está verificado | Sí, con el mismo botón |
| El callback es alcanzable | Sí, la URL se muestra en la página |
| **La app está en modo Live** | **No. Hay que mirarlo a mano.** |
| **La app está suscrita a `messages`** | **No. Hay que mirarlo a mano.** |

---

## 6. Empezar de cero

Si la tabla tiene datos viejos mezclados con los nuevos, es imposible saber qué
es real. Para dejarla limpia:

```
python manage.py reset_whatsapp_test_data           # ensayo: solo informa
python manage.py reset_whatsapp_test_data --ejecutar
```

Borra los eventos del webhook, los envíos de prueba, las campañas de
demostración con sus destinatarios, y las conversaciones del bot que llegaron
por WhatsApp.

**No borra** las plantillas de mensajes (hacen falta para probar el envío con
plantilla), los contactos reales ni los usuarios. Y si un contacto de la
semilla de demostración aparece en una campaña real, lo conserva y avisa.

---

## 7. Comandos relacionados

| Comando | Para qué |
| --- | --- |
| `check_meta_whatsapp` | Estado de la integración por línea de comandos. `--validate` consulta la API real. |
| `reset_whatsapp_test_data` | Deja la consola en cero. |
| `cleanup_whatsapp_events` | Baja la retención de eventos antiguos, conservando `failed` e `inbound`. |
| `seed_demo_whatsapp` | Siembra datos de demostración. `--limpiar` los quita. |

Para más detalle del contrato con Meta, ver [`whatsapp-meta.md`](whatsapp-meta.md).
