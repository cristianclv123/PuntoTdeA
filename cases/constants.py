CHANNEL_META = {
    "whatsapp": ("message-circle", "channel-whatsapp", "WhatsApp"),
    "facebook": ("facebook", "channel-facebook", "Facebook"),
    "instagram": ("instagram", "channel-instagram", "Instagram"),
    "web": ("globe", "channel-web", "Web"),
}

# Clases CSS para pills de estado en la bandeja (wa-status-tag--*).
STATUS_TAG_CLASS = {
    "pendiente": "pendiente",
    "completado": "completado",
    "rechazado": "rechazado",
    "escalado": "escalado",
    "cerrado": "cerrado",
}


def channel_ui(code: str) -> dict:
    icon_name, css_class, label = CHANNEL_META.get(
        code,
        ("globe", "channel-web", code.title()),
    )
    return {
        "channel": code,
        "channel_icon": icon_name,
        "channel_class": css_class,
        "channel_label": label,
    }


def status_tag_class(*, status: str, unassigned: bool = False) -> str:
    if unassigned:
        return "waiting"
    return STATUS_TAG_CLASS.get(status, "pendiente")
