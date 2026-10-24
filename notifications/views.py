from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from notifications.models import Notification, NotificationRead
from notifications.services import _payload


def _unread_qs(user):
    reads = NotificationRead.objects.filter(notification_id=OuterRef("pk"), user=user)
    return Notification.objects.annotate(is_read=Exists(reads))


@login_required
@require_GET
def list_notifications(request):
    try:
        limit = min(int(request.GET.get("limit") or 40), 80)
    except (TypeError, ValueError):
        limit = 40
    qs = _unread_qs(request.user)[:limit]
    items = [_payload(item, unread=not item.is_read) for item in qs]
    unread = _unread_qs(request.user).filter(is_read=False).count()
    return JsonResponse({"results": items, "unread": unread})


@login_required
@require_POST
def mark_read(request, notification_id):
    notification = Notification.objects.filter(pk=notification_id).first()
    if notification is None:
        return JsonResponse({"ok": False}, status=404)
    NotificationRead.objects.get_or_create(notification=notification, user=request.user)
    unread = _unread_qs(request.user).filter(is_read=False).count()
    return JsonResponse({"ok": True, "unread": unread})


@login_required
@require_POST
def mark_all_read(request):
    now = timezone.now()
    unread_ids = list(
        _unread_qs(request.user).filter(is_read=False).values_list("id", flat=True)[:500]
    )
    NotificationRead.objects.bulk_create(
        [
            NotificationRead(notification_id=pk, user=request.user, read_at=now)
            for pk in unread_ids
        ],
        ignore_conflicts=True,
    )
    return JsonResponse({"ok": True, "unread": 0})
