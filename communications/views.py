from django.shortcuts import render

from .mock_data import CAMPAIGNS

CHANNEL_META = {
    "whatsapp": ("message-circle", "channel-whatsapp"),
    "facebook": ("facebook", "channel-facebook"),
    "instagram": ("instagram", "channel-instagram"),
}


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
