from django.shortcuts import render

from .mock_data import CAMPAIGNS

CHANNEL_META = {
    "whatsapp": ("message-circle", "channel-whatsapp"),
    "facebook": ("facebook", "channel-facebook"),
    "instagram": ("instagram", "channel-instagram"),
}


def index(request):
    return render(request, "communications/index.html", {"nav_section": "dashboard"})


def campaigns(request):
    enriched = []
    for c in CAMPAIGNS:
        icon_name, css_class = CHANNEL_META[c["channel"]]
        enriched.append({**c, "channel_icon": icon_name, "channel_class": css_class})
    context = {
        "active_nav": "campaigns",
        "campaigns": enriched,
    }
    return render(request, "communications/campanas.html", context)


def campaign_new(request):
    return render(request, "communications/campaign_new.html", {"nav_section": "campaigns"})


def campaign_detail(request):
    return render(request, "communications/campaign_detail.html", {"nav_section": "campaigns"})


def segments(request):
    return render(request, "communications/segments.html", {"nav_section": "segments"})


def interactions(request):
    return render(request, "communications/interactions.html", {"nav_section": "interactions"})