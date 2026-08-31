from django.shortcuts import render

from .mock_data import ANNOUNCEMENTS


def announcement_list(request):
    context = {
        "active_nav": "announcements",
        "announcements": ANNOUNCEMENTS,
    }
    return render(request, "announcements/avisos.html", context)
