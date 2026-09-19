"""Datos de ejemplo para el módulo de Campañas."""

CAMPAIGNS = [
    {
        "id": "c1",
        "name": "Matrícula 2026-1",
        "channel": "whatsapp",
        "meta": "Estudiantes activos · 28 ago, 8:00 a. m.",
        "segments": ["Estudiantes activos"],
        "status": "enviada",
        "sent": 8420,
        "delivered": 8310,
        "read": 7204,
        "clicks": 2104,
        "replies": 980,
    },
    {
        "id": "c2",
        "name": "Citas de admisión",
        "channel": "whatsapp",
        "meta": "Aspirantes 2026-1 · 02 sep, 10:30 a. m.",
        "segments": ["Aspirantes 2026-1"],
        "status": "enviada",
        "sent": 2104,
        "delivered": 2088,
        "read": 1980,
        "clicks": 0,
        "replies": 640,
    },
    {
        "id": "c3",
        "name": "Boletín egresados",
        "channel": "whatsapp",
        "meta": "Egresados · 10 sep, 7:00 a. m.",
        "segments": ["Egresados"],
        "status": "programada",
        "sent": 0,
        "delivered": 0,
        "read": 0,
        "clicks": 0,
        "replies": 0,
    },
    {
        "id": "c4",
        "name": "Feria de facultades",
        "channel": "whatsapp",
        "meta": "Aspirantes y estudiantes · 20 ago, 12:00 p. m.",
        "segments": ["Aspirantes 2026-1", "Estudiantes activos"],
        "status": "enviada",
        "sent": 3200,
        "delivered": 3180,
        "read": 2410,
        "clicks": 870,
        "replies": 122,
    },
]

ACTIVITY_LOGS = [
    {
        "at": "2026-09-04 09:12",
        "person": "Laura Restrepo",
        "channel": "whatsapp",
        "campaign": "Matrícula 2026-1",
        "event": "respuesta",
        "detail": "¿Puedo fraccionar el pago?",
    },
    {
        "at": "2026-09-04 09:08",
        "person": "Andrés Gómez",
        "channel": "whatsapp",
        "campaign": "Matrícula 2026-1",
        "event": "clic",
        "detail": "Ir a matrícula",
    },
    {
        "at": "2026-09-04 08:55",
        "person": "Camila Hoyos",
        "channel": "whatsapp",
        "campaign": "Citas de admisión",
        "event": "respuesta",
        "detail": "SI",
    },
    {
        "at": "2026-09-03 16:40",
        "person": "Julián Pérez",
        "channel": "whatsapp",
        "campaign": "Boletín egresados",
        "event": "programada",
        "detail": "Envío agendado",
    },
]


def campaign_kpis(campaigns=None):
    items = campaigns if campaigns is not None else CAMPAIGNS
    sent = sum(c.get("sent") or 0 for c in items)
    delivered = sum(c.get("delivered") or 0 for c in items)
    read = sum(c.get("read") or 0 for c in items)
    replies = sum(c.get("replies") or 0 for c in items)
    read_rate = f"{round(read / delivered * 100)}%" if delivered else "0%"
    return [
        {"label": "Mensajes enviados", "value": f"{sent:,}".replace(",", "."), "sub": "campañas WhatsApp"},
        {"label": "Entregados", "value": f"{delivered:,}".replace(",", "."), "sub": "confirmados por canal"},
        {"label": "Tasa de lectura", "value": read_rate, "sub": "sobre entregados"},
        {"label": "Respuestas", "value": f"{replies:,}".replace(",", "."), "sub": "interacciones entrantes"},
    ]


def recent_campaigns(limit=4):
    rows = []
    for c in CAMPAIGNS[:limit]:
        delivered = c.get("delivered") or 0
        read = c.get("read") or 0
        read_pct = f"{round(read / delivered * 100)}%" if delivered else "0%"
        rows.append(
            {
                **c,
                "audience": ", ".join(c.get("segments") or []),
                "read_pct": read_pct,
            }
        )
    return rows
