# Chatbot de conocimiento

## Ejecución

### Cargar base inicial

Después de migrar, ejecuta:

```powershell
python manage.py seed_knowledge
```

El comando es seguro de repetir: actualiza los registros iniciales por nombre o
pregunta y no elimina la información que agregues después. Para introducir tus
propios datos, entra al administrador de Django y crea categorías, FAQ y artículos
con estado `Publicado` y `published` activado; solo esa información será utilizada
por el bot.

En Windows puedes abrir `iniciar_chatbot.vbs` con doble clic. Inicia Django sin
mostrar una consola negra y abre automáticamente el endpoint local. Para detener
el servidor, ejecuta `detener_chatbot.vbs`.

Desde la raíz del proyecto:

```powershell
python manage.py migrate
python manage.py test knowledge.chatbot knowledge.tests.ChatbotWorkflowTests
```

El endpoint JSON está disponible en `GET /base-de-conocimiento/chatbot/` para iniciar
una conversación y en `POST /base-de-conocimiento/chatbot/` para enviar acciones.
El cuerpo POST usa una de estas acciones: `question`, `confirm`, `escalate` o
`advisor_question`. La sesión guarda el identificador de la conversación; también
puede enviarse `conversation_id` explícitamente.

## Relación con el diagrama

- `ChatbotWorkflow.start`: saludo e ingreso de pregunta.
- `validation.py`: pregunta válida o solicitud nuevamente.
- `responder.py`: generación desacoplada, actualmente conectada al RAG.
- `confirm_more_help`: continuar o finalizar.
- `escalate` y `submit_advisor_question`: transferencia con contexto.
- `schedule.py`: horario centralizado y decisión dentro/fuera de horario.
- `ChatConversation`: historial, respuestas, fecha de escalamiento, motivo y estado.

El proveedor LLM queda pendiente: basta inyectar otro `responder` en
`ChatbotWorkflow`; no se requiere cambiar la validación ni la persistencia.

## WhatsApp Cloud API

El webhook público es:

```text
https://TU_DOMINIO/base-de-conocimiento/chatbot/whatsapp/
```

Configura estas variables de entorno en el servidor:

```text
META_VERIFY_TOKEN=un-token-secreto-para-verificacion
META_APP_SECRET=app-secret-de-meta
META_ACCESS_TOKEN=token-de-acceso-de-whatsapp
WHATSAPP_PHONE_NUMBER_ID=id-del-numero-de-whatsapp
WHATSAPP_API_VERSION=v21.0
```

En Meta Developers, dentro de WhatsApp > Configuration, registra la URL anterior,
usa el mismo `META_VERIFY_TOKEN` y suscribe el campo `messages`. El servidor debe
ser accesible por HTTPS. En desarrollo se puede exponer Django con un túnel HTTPS
como ngrok o Cloudflare Tunnel.

El primer mensaje de cada número inicia el saludo. Los siguientes recorren pregunta,
respuesta, confirmación, escalamiento y horario; el identificador de WhatsApp se
guarda en `ChatConversation.external_user_id`, por lo que el asesor conserva el
historial completo.