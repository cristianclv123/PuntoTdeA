# Módulo Knowledge / Chatbot (`knowledge/`)

Base de conocimiento (categorías, FAQ, artículos) y el asistente conversacional que atiende WhatsApp y el chat interno.

UI: `/base-de-conocimiento/`. API: `/api/knowledge/`. Flujo detallado del bot: [`knowledge/README.md`](../../knowledge/README.md).

## Árbol

```
knowledge/
  models.py
  views.py                 # index, FAQ, gestión, chatbot JSON, alias webhook
  urls.py
  signals.py
  api/                     # viewsets + search/ask/reindex
  services/
    rag_service.py         # similitud por tokens (no LLM)
    indexing_service.py
    import_service.py      # Excel de FAQ/artículos
  chatbot/
    workflow.py            # estados de la conversación
    responder.py           # conecta RAG
    validation.py
    schedule.py            # horario hábil
    whatsapp.py            # handle_message, send_replies, crea tickets
    tests.py
  templates/knowledge/
  management/commands/seed_knowledge.py
```

## Modelos

| Modelo | Rol |
| --- | --- |
| `Category` | Agrupa FAQ y artículos |
| `Intent` | Intención + umbral de confianza (default 0.75) |
| `KnowledgeArticle` | Contenido largo; `status` draft/published/archived; `embedding` JSON |
| `FAQ` | Pregunta/respuesta; vigencia `valid_from`/`valid_until`; imagen opcional |
| `ChatConversation` | Sesión del bot (UUID). `flow_state`, `messages` JSON, FK a `communications.Contact` y `cases.Conversation` |

Solo artículos **publicados** (`published` o `status=published`) entran al RAG.

## RAG

`rag_service.py`: cosine-like por tokens en Python. No hay embeddings de proveedor ni LLM en producción. `responder.generate_response` usa ese índice. Si la confianza es baja, el WhatsApp adapter crea un ticket (`needs_human_attention`).

Reindex calendario: `POST /api/knowledge/reindex-academic-calendar/`.

## Chatbot — estados (`ChatbotWorkflow`)

| `flow_state` | Qué espera |
| --- | --- |
| `waiting_question` | Pregunta del usuario |
| `waiting_confirmation` | ¿Otra consulta, hablar con asesor o finalizar? (botones; el texto `sí`/`no` sigue funcionando) |
| `waiting_low_confidence_choice` | ¿Asesor o nueva pregunta? (botones). Al elegir asesor, pide mensaje y documento antes de crear el ticket |
| `help_options` | Nueva pregunta o asesor (botones) |
| `waiting_advisor_question` | Texto para el asesor (después de pedir humano) |
| `pending` | Ticket en bandeja; inbound se anexa al caso, sin respuesta del bot |
| `ended` | Conversación cerrada |

Acciones UI JSON (`GET/POST /base-de-conocimiento/chatbot/`): `question`, `confirm`, `escalate`, `advisor_question`.

Palabras que piden humano en WhatsApp: asesor, humano, persona.

Las preguntas de decisión de WhatsApp incluyen **botones de respuesta rápida**
(hasta 3) con `id` estable (`chat_more`, `chat_advisor`, `chat_finish`,
`lowconf_advisor`, `lowconf_question`, `help_question`, `help_advisor`). El
webhook reenvía el `id`; si el usuario responde por texto, se aceptan los
títulos y las palabras clave. Una selección vieja (de otro estado) recibe un
recordatorio y **no** avanza el flujo.

## Inactividad (5 + 2 minutos)

`chatbot/inactivity.py` implementa el ciclo y `ChatConversation` guarda
`last_user_activity_at` e `inactivity_warned_at`:

1. A los 5 minutos sin mensajes del usuario se envía **un** aviso.
2. Dos minutos después del aviso (7 en total) se cierra y se informa al usuario.
3. Cualquier mensaje entrante reinicia el contador y cancela el cierre.
4. Las conversaciones con un caso abierto o esperando asesor no se cierran.
5. Los `UPDATE` condicionales evitan avisos/cierres duplicados entre procesos.

El ciclo puede correr **incrustado en el proceso web** con
`ENABLE_INACTIVITY_SCHEDULER=true` (asi funciona igual en Docker y Render) o
como comando independiente con `--interval 60` para systemd/supervisor/cron.
Sin opciones hace una sola pasada. En Render free el contenedor se duerme sin
tráfico, por lo que el aviso puede retrasarse. No depende de un scheduler de la
plataforma de despliegue.

## WhatsApp (`chatbot/whatsapp.py`)

Meta **no** llama este archivo directo. El webhook único (`communications`) invoca
`handle_message(sender, text, external_message_id, interactive_id)` y envía cada
reply con `send_text` → `send_text_message` (o con los envíos interactivos de
`communications/adapters/meta_adapter.py`).

Al escalar o al no alcanzar confianza:

1. `ingest_inbound_message` crea `cases.Conversation` canal `whatsapp`, thread = número.
2. Guarda `ChatConversation.case_conversation`.
3. Confirma al usuario el `ticket_number` (`TDEA-…`).
4. Estado del bot: `pending`. Los mensajes siguientes se anexan al mismo caso; el bot ya no responde.

Alias HTTP `/base-de-conocimiento/chatbot/whatsapp/` = misma vista del webhook; no registrar en Meta.

## UI HTML

| Ruta | Vista |
| --- | --- |
| `/base-de-conocimiento/` | Índice |
| `/list/` | Listado FAQ |
| `/gestion/` | Alta/edición (import Excel) |
| `/chatbot/` | Consola JSON del flujo |

## API `/api/knowledge/`

ViewSets: `categories`, `intents`, `articles`, `faqs`, `conversations`.

| Extra | Uso |
| --- | --- |
| `GET/POST search/` | Búsqueda |
| `POST ask/` | Pregunta al RAG |
| `POST reindex-academic-calendar/` | Reindexa calendario |

## Comandos y pruebas

```bash
python manage.py seed_knowledge
python manage.py test knowledge
```

`seed_knowledge` es idempotente por nombre/pregunta.
