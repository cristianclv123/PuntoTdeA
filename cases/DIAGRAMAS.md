# Módulo `cases` — Diagrama de clases y entidad-relación

Documento único con el modelo de dominio de la app **cases** (Punto TdeA / HU-01 + acciones de caso).

---

## 1. Diagrama de clases

```mermaid
classDiagram
  direction TB

  class Channel {
    +int id
    +string code
    +string name
    +bool is_active
  }

  class Department {
    +int id
    +string code
    +string name
    +bool is_active
  }

  class Contact {
    +int id
    +string full_name
    +string document_number
    +string email
    +string phone
    +string academic_program
    +int semester
    +datetime created_at
    +datetime updated_at
    +initials() string
  }

  class Conversation {
    +int id
    +string external_thread_id
    +string ticket_number
    +string status
    +string priority
    +string theme
    +datetime last_message_at
    +datetime created_at
    +datetime updated_at
    +save()
  }

  class Message {
    +int id
    +string direction
    +string body
    +string external_id
    +datetime sent_at
    +datetime created_at
  }

  class CaseComment {
    +int id
    +string body
    +datetime created_at
  }

  class MessageAttachment {
    +int id
    +string original_name
    +string content_type
    +string kind
    +int size_bytes
    +datetime created_at
  }

  class ReplyTemplate {
    +int id
    +string title
    +string body
    +bool is_active
    +datetime created_at
    +datetime updated_at
  }

  class User {
    +int id
    +string username
  }

  note for Conversation "status: pendiente | completado | rechazado | escalado | cerrado\npriority: baja | media | alta | urgente\nticket: TDEA-000001"
  note for Channel "code: whatsapp | facebook | instagram | web"
  note for Message "direction: inbound | outbound"
  note for MessageAttachment "kind: image | video | office"

  Channel "1" --> "*" Conversation : channel
  Contact "1" --> "*" Conversation : contact
  Department "0..1" --> "*" Conversation : department
  Department "0..1" --> "*" Conversation : escalated_to
  User "0..1" --> "*" Conversation : assigned_to
  Conversation "1" --> "*" Message : messages
  Conversation "1" --> "*" CaseComment : comments
  Message "1" --> "*" MessageAttachment : attachments
  User "0..1" --> "*" CaseComment : author
  User "0..1" --> "*" ReplyTemplate : created_by
```

---

## 2. Diagrama entidad-relación

```mermaid
erDiagram
  CHANNEL ||--o{ CONVERSATION : "has"
  CONTACT ||--o{ CONVERSATION : "opens"
  DEPARTMENT ||--o{ CONVERSATION : "classifies"
  DEPARTMENT ||--o{ CONVERSATION : "escalated_to"
  USER ||--o{ CONVERSATION : "assigned_to"
  CONVERSATION ||--o{ MESSAGE : "contains"
  CONVERSATION ||--o{ CASE_COMMENT : "has"
  MESSAGE ||--o{ MESSAGE_ATTACHMENT : "has"
  USER ||--o{ CASE_COMMENT : "writes"
  USER ||--o{ REPLY_TEMPLATE : "creates"

  CHANNEL {
    bigint id PK
    string code UK
    string name
    bool is_active
  }

  DEPARTMENT {
    bigint id PK
    string code UK
    string name
    bool is_active
  }

  CONTACT {
    bigint id PK
    string full_name
    string document_number UK
    string email
    string phone
    string academic_program
    int semester
    datetime created_at
    datetime updated_at
  }

  CONVERSATION {
    bigint id PK
    bigint channel_id FK
    bigint contact_id FK
    string external_thread_id
    string ticket_number UK
    string status
    string priority
    bigint department_id FK
    bigint escalated_to_id FK
    string theme
    bigint assigned_to_id FK
    datetime last_message_at
    datetime created_at
    datetime updated_at
  }

  MESSAGE {
    bigint id PK
    bigint conversation_id FK
    string direction
    text body
    string external_id
    datetime sent_at
    datetime created_at
  }

  MESSAGE_ATTACHMENT {
    bigint id PK
    bigint message_id FK
    string file
    string original_name
    string content_type
    string kind
    int size_bytes
    datetime created_at
  }

  CASE_COMMENT {
    bigint id PK
    bigint conversation_id FK
    bigint author_id FK
    text body
    datetime created_at
  }

  REPLY_TEMPLATE {
    bigint id PK
    string title
    text body
    bool is_active
    bigint created_by_id FK
    datetime created_at
    datetime updated_at
  }

  USER {
    bigint id PK
    string username
  }
```

---

## 3. Cardinalidades (resumen)

| Relación | Cardinalidad | Notas |
|----------|--------------|--------|
| Channel → Conversation | 1:N | `PROTECT` |
| Contact → Conversation | 1:N | `PROTECT` |
| Department → Conversation (clasificación) | 0..1:N | `SET_NULL` |
| Department → Conversation (escalado a) | 0..1:N | obligatorio si `status=escalado` |
| User → Conversation (asesor) | 0..1:N | `assigned_to` |
| Conversation → Message | 1:N | chat ciudadano |
| Conversation → CaseComment | 1:N | comentarios internos |
| Message → MessageAttachment | 1:N | imagen / video / ofimática |
| User → CaseComment | 0..1:N | autor del comentario |
| User → ReplyTemplate | 0..1:N | plantillas predefinidas del clip |

---

## 4. Implementación

Código fuente: [`cases/models.py`](models.py)
