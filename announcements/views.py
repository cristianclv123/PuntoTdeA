from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Announcement


@login_required
def index(request):
    if request.method == "POST":
        action = (request.POST.get("action") or "create").strip()

        if action == "delete":
            notice_id = request.POST.get("notice_id")
            announcement = get_object_or_404(Announcement, pk=notice_id)
            announcement.delete()
            messages.success(request, "Aviso eliminado.")
            return redirect("announcements:index")

        title = (request.POST.get("title") or "").strip()
        body_text = (request.POST.get("body") or "").strip()
        notice_type = request.POST.get("type")
        image_file = request.FILES.get("image")

        if not title or not body_text:
            messages.error(request, "Título y contenido son obligatorios.")
            return redirect("announcements:index")

        Announcement.objects.create(
            title=title,
            content=body_text,
            image=image_file,
            is_urgent=notice_type == "urgente",
        )
        messages.success(request, "Aviso publicado.")
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
