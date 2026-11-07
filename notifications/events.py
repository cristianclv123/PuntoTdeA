"""Textos y disparos de negocio para el dock de notificaciones."""

from notifications.models import Notification
from notifications.services import notify


def _contact_name(conversation) -> str:
    contact = getattr(conversation, "contact", None)
    return getattr(contact, "full_name", None) or "un estudiante"


def notify_new_chat(conversation) -> None:
    name = _contact_name(conversation)
    notify(
        module=Notification.Module.CASES,
        event="chat.new",
        title="Llegó un nuevo chat",
        body=f"{name} escribió y espera un asesor.",
        url=f"/bandeja/{conversation.id}/",
        level=Notification.Level.INFO,
    )


def notify_customer_reply(conversation, preview: str = "") -> None:
    name = _contact_name(conversation)
    snippet = (preview or "").strip().replace("\n", " ")
    if len(snippet) > 90:
        snippet = snippet[:87] + "…"
    notify(
        module=Notification.Module.CASES,
        event="chat.reply",
        title=f"{name} respondió",
        body=snippet or "Hay un mensaje nuevo en la bandeja.",
        url=f"/bandeja/{conversation.id}/",
        level=Notification.Level.INFO,
    )


def notify_advisor_reply(conversation, user=None) -> None:
    name = _contact_name(conversation)
    from cases.services.case_events import advisor_label

    notify(
        module=Notification.Module.CASES,
        event="chat.outbound",
        title="Se respondió un chat",
        body=f"{advisor_label(user)} respondió a {name}.",
        url=f"/bandeja/{conversation.id}/",
        level=Notification.Level.SUCCESS,
        actor=user,
    )


def notify_chat_claimed(conversation, user=None) -> None:
    name = _contact_name(conversation)
    from cases.services.case_events import advisor_label

    notify(
        module=Notification.Module.CASES,
        event="chat.claimed",
        title="Un asesor tomó un chat",
        body=f"{advisor_label(user)} está atendiendo a {name}.",
        url=f"/bandeja/{conversation.id}/",
        level=Notification.Level.SUCCESS,
        actor=user,
    )


def notify_chat_closed(conversation, user=None) -> None:
    ticket = conversation.ticket_number or f"TDEA-{conversation.id:06d}"
    notify(
        module=Notification.Module.CASES,
        event="chat.closed",
        title="Se cerró un caso",
        body=f"{ticket} · {_contact_name(conversation)}",
        url=f"/bandeja/{conversation.id}/?closed=1",
        level=Notification.Level.INFO,
        actor=user,
    )


def notify_template_status(name: str, event: str, *, url: str = "/campanas/") -> None:
    event_key = (event or "").upper()
    labels = {
        "APPROVED": ("Se aprobó una plantilla en Meta", Notification.Level.SUCCESS),
        "REJECTED": ("Meta rechazó una plantilla", Notification.Level.DANGER),
        "PENDING": ("Plantilla en revisión de Meta", Notification.Level.INFO),
        "PAUSED": ("Meta pausó una plantilla", Notification.Level.WARNING),
        "DISABLED": ("Meta deshabilitó una plantilla", Notification.Level.DANGER),
        "FLAGGED": ("Meta marcó una plantilla", Notification.Level.WARNING),
    }
    title, level = labels.get(
        event_key,
        (f"Meta actualizó una plantilla ({event_key or 'estado'})", Notification.Level.INFO),
    )
    notify(
        module=Notification.Module.COMMUNICATIONS,
        event=f"template.{event_key.lower() or 'update'}",
        title=title,
        body=name or "Plantilla de WhatsApp",
        url=url,
        level=level,
    )


def notify_campaign(title: str, body: str, *, event: str, level: str, campaign_id=None) -> None:
    url = "/campanas/"
    if campaign_id:
        url = f"/campanas/?campaign={campaign_id}"
    notify(
        module=Notification.Module.COMMUNICATIONS,
        event=event,
        title=title,
        body=body,
        url=url,
        level=level,
    )


def notify_announcement(title: str, body: str, *, event: str, level: str = Notification.Level.INFO) -> None:
    notify(
        module=Notification.Module.ANNOUNCEMENTS,
        event=event,
        title=title,
        body=body,
        url="/avisos/",
        level=level,
    )


def notify_knowledge(title: str, body: str, *, event: str, level: str = Notification.Level.INFO) -> None:
    notify(
        module=Notification.Module.KNOWLEDGE,
        event=event,
        title=title,
        body=body,
        url="/base-de-conocimiento/gestion/",
        level=level,
    )
