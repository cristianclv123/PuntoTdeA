from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render

from communications.models import AudienceSegment

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


def _retry_status(request: HttpRequest, announcement: Announcement) -> None:
    """Reintenta la publicacion en Status reutilizando el ultimo intento."""
    if not announcement.image:
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


@login_required
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
            announcement.delete()
            messages.success(request, "Aviso eliminado.")
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

        announcement = Announcement.objects.create(
            title=title,
            content=body_text,
            image=image_file,
            is_urgent=notice_type == "urgente",
        )
        messages.success(request, "Aviso creado.")

        if publish_status:
            if not announcement.image:
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
        "segments": AudienceSegment.objects.all().order_by("name"),
        "active_nav": "announcements",
    }
    return render(request, "announcements/avisos.html", context)
