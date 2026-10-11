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
    whatsapp.py            # handle_message, send_text, crea tickets
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
| `waiting_confirmation` | ¿Te ayudo en algo más? sí/no |
| `help_options` | Nueva pregunta |
| `waiting_advisor_question` | Texto para el asesor (después de pedir humano) |
| `pending` | Ticket en bandeja; inbound se anexa al caso, sin respuesta del bot |
| `ended` | Conversación cerrada |

Acciones UI JSON (`GET/POST /base-de-conocimiento/chatbot/`): `question`, `confirm`, `escalate`, `advisor_question`.

Palabras que piden humano en WhatsApp: asesor, humano, persona.

## WhatsApp (`chatbot/whatsapp.py`)

Meta **no** llama este archivo directo. El webhook único (`communications`) invoca `handle_message(sender, text)` y envía cada reply con `send_text` → `send_text_message`.

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
