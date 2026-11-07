# Diagramas de arquitectura — Punto TdeA

Diagramas generados con [Mermaid](https://mermaid.js.org) a partir de las fuentes `.mmd` de esta carpeta. GitHub renderiza los bloques directamente; para exportar SVG/PNG ver [`README.md`](README.md).

## 1. Capas y componentes

Vista lógica del sistema: cliente, acceso (Daphne/HTTP/WS/webhook), módulos de negocio, integración externa y persistencia.

```mermaid
flowchart TB
    subgraph Cliente["Capa de cliente"]
        Browser["Navegador web"]
        WA["Estudiante en WhatsApp"]
    end

    subgraph Acceso["Capa de acceso - Daphne ASGI"]
        HTTP["HTTP: vistas Django + DRF"]
        WS["WebSocket: Channels"]
        Hook["Webhook Meta"]
    end

    subgraph Modulos["Capa de aplicación - módulos Django"]
        Cases["cases<br/>bandeja y tickets"]
        Knowledge["knowledge<br/>FAQ, RAG, chatbot"]
        Comm["communications<br/>campañas y plantillas"]
        Ann["announcements<br/>avisos y Status Ads"]
        Notif["notifications<br/>dock y WS"]
        Dash["dashboard<br/>métricas"]
    end

    subgraph Integracion["Capa de integración externa"]
        Cloud["Meta Cloud API"]
        Ads["Meta Marketing API"]
    end

    subgraph Datos["Capa de persistencia"]
        DB[("PostgreSQL / SQLite")]
        Media[("Media / adjuntos")]
        Redis[("Redis / channel layer")]
    end

    Browser --> HTTP
    Browser --> WS
    WA --> Hook
    Hook --> Comm
    Hook --> Knowledge
    HTTP --> Cases
    HTTP --> Knowledge
    HTTP --> Comm
    HTTP --> Ann
    HTTP --> Notif
    HTTP --> Dash
    WS --> Cases
    WS --> Notif
    Knowledge --> Cases
    Cases --> Comm
    Ann --> Comm
    Comm --> Cloud
    Ann --> Ads
    Cases --> DB
    Knowledge --> DB
    Comm --> DB
    Ann --> DB
    Notif --> DB
    Cases --> Media
    WS --> Redis
```

## 2. Flujo WhatsApp de punta a punta

Desde el mensaje del estudiante hasta la atención humana: webhook → chatbot/RAG → escalación a cases → bandeja → respuesta Meta.

```mermaid
sequenceDiagram
    participant E as Estudiante
    participant M as Meta Cloud API
    participant W as Webhook communications
    participant B as Chatbot knowledge
    participant R as RAG / FAQ
    participant C as Cases
    participant A as Asesora /bandeja/

    E->>M: texto o botón
    M->>W: POST /api/whatsapp/webhook/ (HMAC)
    W->>W: valida firma y registra evento (idempotente)
    W->>B: handle_message(sender, text, id)
    B->>R: busca respuesta
    alt confianza alta
        R-->>B: respuesta
        B-->>W: replies
        W->>M: send_text_message
        M->>E: respuesta del bot
    else baja confianza o pide asesor
        B->>C: ingest_inbound_message
        C-->>B: Conversation TDEA-000123
        B-->>W: confirmación de ticket
        W->>M: send_text_message
        M->>E: ticket creado
        C->>A: notificación + WebSocket /bandeja/
        A->>C: claim + saludo automático
        C->>M: send_text_message
        M->>E: saludo del asesor
    end
```

## 3. Modelo de datos

Entidades y relaciones entre apps. Ojo: `CASES_CONTACT` y `COMM_CONTACT` son modelos distintos.

```mermaid
erDiagram
    CHANNEL ||--o{ CONVERSATION : "tiene"
    DEPARTMENT ||--o{ CONVERSATION : "clasifica"
    CASES_CONTACT ||--o{ CONVERSATION : "posee"
    CONVERSATION ||--o{ MESSAGE : "incluye"
    MESSAGE ||--o{ MESSAGE_ATTACHMENT : "adjunta"
    CONVERSATION ||--o{ CASE_COMMENT : "anota"

    CATEGORY ||--o{ KNOWLEDGE_ARTICLE : "agrupa"
    CATEGORY ||--o{ FAQ : "agrupa"
    INTENT ||--o{ KNOWLEDGE_ARTICLE : "orienta"
    INTENT ||--o{ FAQ : "orienta"

    COMM_CONTACT ||--o{ CONTACT_EVENT : "registra"
    COMM_CONTACT ||--o{ SEGMENT_MEMBERSHIP : "pertenece"
    AUDIENCE_SEGMENT ||--o{ SEGMENT_MEMBERSHIP : "contiene"
    AUDIENCE_SEGMENT ||--o{ CAMPAIGN : "segmenta"
    CAMPAIGN ||--o{ BROADCAST_RECIPIENT : "envía"
    COMM_CONTACT ||--o{ BROADCAST_RECIPIENT : "recibe"
    CAMPAIGN ||--o| CAMPAIGN_PERSONALIZATION : "autoriza"

    ANNOUNCEMENT ||--o{ STATUS_AD : "publica"

    CHAT_CONVERSATION }o--o| COMM_CONTACT : "contacto CDP"
    CHAT_CONVERSATION }o--o| CONVERSATION : "ticket cases"
```

## 4. Despliegue en Render

Blueprint (`render.yaml`): web Docker + Key Value + PostgreSQL, con `entrypoint.sh` y schedulers incrustados.

```mermaid
flowchart LR
    subgraph Usuario["Usuario final"]
        Navegador["Navegador"]
    end

    subgraph Render["Render - Blueprint"]
        subgraph Web["Servicio web (Docker)"]
            Entry["entrypoint.sh<br/>migrate + createsuperuser"]
            Daphne["Daphne ASGI"]
            Django["Django 5.1 + DRF + Channels"]
            Sched["Schedulers<br/>inactividad y campañas"]
        end
        KV[("Key Value / Redis")]
        PG[("PostgreSQL")]
    end

    subgraph Meta["Meta"]
        Cloud["WhatsApp Cloud API"]
        Ads["Marketing API"]
    end

    Navegador --> Daphne
    Entry --> Daphne
    Daphne --> Django
    Cloud --> Django
    Ads --> Django
    Django --> KV
    Django --> PG
    Sched --> Django
```

## 5. Ciclo de vida de una campaña

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> scheduled
    draft --> cancelled
    scheduled --> sending
    sending --> sent
    sending --> paused
    sending --> cancelled
    sending --> failed
    paused --> scheduled
    paused --> cancelled
    sent --> [*]
    failed --> [*]
    cancelled --> [*]
```
