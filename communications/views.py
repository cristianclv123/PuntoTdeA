from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def campaigns(request):
    context = {
        "active_nav": "campaigns",
        "nav_section": "campaigns",
    }
    return render(request, "communications/campanas.html", context)


@login_required
def campaign_new(request):
    return render(
        request,
        "communications/campaign_new.html",
        {"nav_section": "campaigns", "active_nav": "campaigns"},
    )


@login_required
def campaign_detail(request):
    return render(
        request,
        "communications/campaign_detail.html",
        {"nav_section": "campaigns", "active_nav": "campaigns"},
    )


@login_required
def segments(request):
    return render(
        request,
        "communications/segments.html",
        {"nav_section": "segments", "active_nav": "campaigns"},
    )


@login_required
def interactions(request):
    return render(
        request,
        "communications/interactions.html",
        {"nav_section": "interactions", "active_nav": "campaigns"},
    )
