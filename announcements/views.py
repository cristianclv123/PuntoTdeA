from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from PuntoTdeA.access import module_access_required

from .permissions import ANNOUNCEMENTS_PERMISSION
from .models import Announcement, StatusAd
from .status_ad_service import publish_announcement


def _flag(request: HttpRequest, name: str) -> bool:
    return (request.POST.get(name) or "").strip().lower() in {"on", "true", "1", "si"}


def _status_options(request: HttpRequest) -> dict:
    """Opciones del anuncio de Status a partir del formulario."""
    return {
        "segment_ids": request.POST.getlist("audience"),
        "advantage_audience": _flag(request, "advantage_audience"),
        "activate": _flag(request, "activate_status"),
    }


def _notify(request: HttpRequest, status_ad: StatusAd) -> None:
    if status_ad.state == StatusAd.State.ERROR:
        messages.error(
            request,
            f"No se pudo publicar en WhatsApp Status: {status_ad.error}",
        )
        return
    estado = "activo" if status_ad.state == StatusAd.State.ACTIVE else "pausado (prueba)"
    messages.success(request, f"Anuncio creado en WhatsApp Status ({estado}).")
    from notifications.events import notify_announcement
    from notifications.models import Notification

    notify_announcement(
        "Aviso publicado en WhatsApp Status",
        status_ad.announcement.title if status_ad.announcement_id else "Status",
        event="announcement.status",
        level=Notification.Level.SUCCESS,
    )


def _retry_status(request: HttpRequest, announcement: Announcement) -> None:
    """Reintenta la publicacion en Status reutilizando el ultimo intento."""
    if not announcement.has_image:
        messages.error(
            request,
            "El aviso no tiene imagen: no se puede publicar en WhatsApp Status.",
        )
        return

    last = announcement.status_ads.first()
    segment_ids = list(last.segment_ids) if last and last.segment_ids else []
    reuse_audience_ids = list(last.audience_ids) if last and last.audience_ids else []
    advantage = last.advantage_audience if last else False

    status_ad = publish_announcement(
        announcement,
        segment_ids=segment_ids,
        reuse_audience_ids=reuse_audience_ids,
        advantage_audience=advantage,
    )
    _notify(request, status_ad)


@module_access_required(
    ANNOUNCEMENTS_PERMISSION,
    module_name="Announcements",
)
def index(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "create").strip()

        if action == "delete":
            notice_id = request.POST.get("notice_id")
            announcement = get_object_or_404(Announcement, pk=notice_id)
            if announcement.is_published_in_status:
                messages.error(
                    request,
                    "No se puede eliminar: el aviso ya esta publicado en el "
                    "estado de WhatsApp.",
                )
                return redirect("announcements:index")
            title = announcement.title
            announcement.delete()
            messages.success(request, "Aviso eliminado.")
            from notifications.events import notify_announcement
            from notifications.models import Notification

            notify_announcement(
                "Se eliminó un aviso",
                title,
                event="announcement.deleted",
                level=Notification.Level.WARNING,
            )
            return redirect("announcements:index")

        if action == "publish_status":
            announcement = get_object_or_404(
                Announcement, pk=request.POST.get("notice_id")
            )
            _retry_status(request, announcement)
            return redirect("announcements:index")

        title = (request.POST.get("title") or "").strip()
        body_text = (request.POST.get("body") or "").strip()
        notice_type = request.POST.get("type")
        image_file = request.FILES.get("image")
        # El formulario tiene dos botones: "Crear aviso" (solo guarda) y
        # "Publicar aviso" (guarda y publica en WhatsApp Status).
        publish_status = action == "publish_status_create"

        if not title or not body_text:
            messages.error(request, "Título y contenido son obligatorios.")
            return redirect("announcements:index")

        if not image_file:
            messages.error(request, "La imagen es obligatoria.")
            return redirect("announcements:index")
        audience = request.POST.get("audience")
        if not audience:
            messages.error(request, "Debe seleccionar una audiencia de destino.")
            return redirect("announcements:index")

        announcement = Announcement(
            title=title,
            content=body_text,
            is_urgent=notice_type == "urgente",
        )
        # La imagen se guarda como bytes en la BD (no en MEDIA_ROOT).
        announcement.set_image(image_file)
        announcement.save()
        try:
            from communications.models import AudienceSegment

            seg = AudienceSegment.objects.get(pk=int(audience))
            announcement.target_audience_segment = seg
            announcement.save(update_fields=["target_audience_segment"])
        except Exception:
            pass
        messages.success(request, "Aviso creado.")
        from notifications.events import notify_announcement
        from notifications.models import Notification

        notify_announcement(
            "Se creó un aviso",
            announcement.title,
            event="announcement.created",
            level=Notification.Level.SUCCESS,
        )

        if publish_status:
            if not announcement.has_image:
                messages.warning(
                    request,
                    "El aviso se guardó, pero no se publicó en Status: falta la imagen.",
                )
            else:
                status_ad = publish_announcement(
                    announcement, **_status_options(request)
                )
                _notify(request, status_ad)

        return redirect("announcements:index")

    announcements = Announcement.objects.all().order_by("-created_at")
    urgent_announcements = Announcement.objects.filter(is_urgent=True).order_by(
        "-created_at"
    )

    context = {
        "announcements": announcements,
        "urgent_announcements": urgent_announcements,
        "active_nav": "announcements",
    }
    return render(request, "announcements/avisos.html", context)


@module_access_required(
    ANNOUNCEMENTS_PERMISSION,
    module_name="Announcements",
)
def announcement_image(request: HttpRequest, pk: int) -> HttpResponse:
    """Sirve el binario de la imagen del aviso guardado en la base de datos."""
    announcement = get_object_or_404(Announcement, pk=pk)
    data = announcement.get_image_bytes()
    if not data:
        return HttpResponse(status=404)
    response = HttpResponse(
        data, content_type=announcement.image_content_type or "application/octet-stream"
    )
    response["Cache-Control"] = "private, max-age=86400"
    if announcement.image_name:
        response["Content-Disposition"] = f'inline; filename="{announcement.image_name}"'
    return response
