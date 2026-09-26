"""Datos de ejemplo para la Bandeja y el detalle de caso.

Estos datos son temporales: reemplazar por consultas reales una vez existan
los modelos de `cases` (Case, Message, Advisor, etc.).
"""

CONVERSATIONS = [
    {
        "id": 1,
        "name": "Mariana Castro",
        "initials": "MC",
        "role": "Aspirante",
        "channel": "whatsapp",
        "last_message": "Hola, quisiera saber si ya salieron los resultados de admisión para el segundo semestre.",
        "theme": "Inscripciones",
        "time": "09:42 a. m.",
        "advisor": "Laura Gómez",
        "status": "pendiente",
    },
    {
        "id": 2,
        "name": "Andrés Ríos",
        "initials": "AR",
        "role": "Estudiante",
        "channel": "facebook",
        "last_message": "¿Cuándo abren las inscripciones para el próximo semestre académico?",
        "theme": "Calendario académico",
        "time": "09:15 a. m.",
        "advisor": "Karen Ruiz",
        "status": "en_gestion",
    },
    {
        "id": 3,
        "name": "Valentina Soto",
        "initials": "VS",
        "role": "Egresada",
        "channel": "instagram",
        "last_message": "Necesito el certificado de notas para un trámite laboral, es urgente.",
        "theme": "Trámites",
        "time": "08:58 a. m.",
        "advisor": "Laura Gómez",
        "status": "escalado",
    },
    {
        "id": 4,
        "name": "Julián Pérez",
        "initials": "JP",
        "role": "Aspirante",
        "channel": "web",
        "last_message": "¿Qué programas tienen disponibles en la sede de Medellín este año?",
        "theme": "Programas",
        "time": "08:40 a. m.",
        "advisor": "Karen Ruiz",
        "status": "atendido",
    },
    {
        "id": 5,
        "name": "Camila Torres",
        "initials": "CT",
        "role": "Estudiante",
        "channel": "whatsapp",
        "last_message": "No puedo acceder a la plataforma para pagar mi matrícula.",
        "theme": "Matrícula",
        "time": "Ayer, 5:20 p. m.",
        "advisor": "Sin asignar",
        "status": "pendiente",
    },
    {
        "id": 6,
        "name": "Santiago Molina",
        "initials": "SM",
        "role": "Aspirante",
        "channel": "facebook",
        "last_message": "¿Cuál es la fecha límite para entregar documentos de inscripción?",
        "theme": "Inscripciones",
        "time": "Ayer, 4:10 p. m.",
        "advisor": "Laura Gómez",
        "status": "cerrado",
    },
    {
        "id": 7,
        "name": "Isabela Marín",
        "initials": "IM",
        "role": "Egresada",
        "channel": "instagram",
        "last_message": "Quiero actualizar mis datos de contacto en el sistema académico.",
        "theme": "Trámites",
        "time": "Ayer, 3:02 p. m.",
        "advisor": "Karen Ruiz",
        "status": "cerrado",
    },
    {
        "id": 8,
        "name": "Daniel Herrera",
        "initials": "DH",
        "role": "Estudiante",
        "channel": "web",
        "last_message": "¿Hay algún evento de ceremonia de grados programado este mes?",
        "theme": "Grados",
        "time": "Ayer, 1:45 p. m.",
        "advisor": "Sin asignar",
        "status": "pendiente",
    },
]

STATUS_LABELS = {
    "pendiente": ("Pendiente", "pill-warning"),
    "en_gestion": ("En gestión", "pill-info"),
    "escalado": ("Escalado", "pill-danger"),
    "atendido": ("Atendido", "pill-success"),
    "cerrado": ("Cerrado", "pill-neutral"),
}

CHANNEL_META = {
    "whatsapp": ("message-circle", "channel-whatsapp", "WhatsApp"),
    "facebook": ("facebook", "channel-facebook", "Facebook"),
    "instagram": ("instagram", "channel-instagram", "Instagram"),
    "web": ("globe", "channel-web", "Web"),
}

CASE_MESSAGES = [
    {"from_agent": False, "text": "Hola, buenas tardes. Necesito el certificado de notas para un trámite laboral, es urgente.", "time": "08:58 a. m."},
    {"from_agent": True, "text": "Hola Valentina, con gusto te ayudo. Este trámite se solicita directamente en la plataforma de egresados, en la sección \"Certificados\".", "time": "09:02 a. m."},
    {"from_agent": False, "text": "Ya intenté pero me sale un error al generar el PDF.", "time": "09:05 a. m."},
    {"from_agent": True, "text": "Entiendo, voy a escalar tu caso al área de Registro Académico para que revisen el error de la plataforma. Te contactarán en las próximas 24 horas.", "time": "09:07 a. m."},
    {"from_agent": False, "text": "Muchas gracias, quedo atenta.", "time": "09:08 a. m."},
]

CASE_NOTES = [
    {
        "author": "Laura Gómez",
        "time": "09:06 a. m.",
        "text": "Cliente ya intentó descargar el certificado dos veces, error recurrente en plataforma. Escalado a Registro Académico.",
    },
]


def get_conversation(case_id):
    return next((c for c in CONVERSATIONS if c["id"] == case_id), CONVERSATIONS[0])
