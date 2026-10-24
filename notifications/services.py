from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

from notifications.models import Notification

GROUP = "notifications"


def _payload(notification: Notification, *, unread: bool = True) -> dict:
    created = timezone.localtime(notification.created_at)
    return {
        "id": notification.id,
        "module": notification.module,
        "module_label": notification.get_module_display(),
        "event": notification.event,
        "title": notification.title,
        "body": notification.body,
        "url": notification.url,
        "level": notification.level,
        "actor_id": notification.actor_id,
        "unread": unread,
        "time": created.strftime("%H:%M"),
        "created_at": created.isoformat(),
    }


def notify(
    *,
    module: str,
    event: str,
    title: str,
    body: str = "",
    url: str = "",
    level: str = Notification.Level.INFO,
    actor=None,
    payload: dict | None = None,
) -> Notification:
    notification = Notification.objects.create(
        module=module,
        event=event,
        title=title,
        body=body or "",
        url=url or "",
        level=level,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        payload=payload or {},
    )
    channel_layer = get_channel_layer()
    if channel_layer is not None:
        async_to_sync(channel_layer.group_send)(
            GROUP,
            {
                "type": "notification.event",
                "event": "notification.new",
                "notification": _payload(notification),
            },
        )
    return notification
