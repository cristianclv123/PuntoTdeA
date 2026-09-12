CHANNEL_META = {
    "whatsapp": ("message-circle", "channel-whatsapp", "WhatsApp"),
    "facebook": ("facebook", "channel-facebook", "Facebook"),
    "instagram": ("instagram", "channel-instagram", "Instagram"),
    "web": ("globe", "channel-web", "Web"),
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
