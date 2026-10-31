from django.shortcuts import render

from .decorators import communications_required


@communications_required
def campaigns(request):
    context = {
        "active_nav": "campaigns",
        "nav_section": "campaigns",
    }
    return render(request, "communications/campanas.html", context)


@communications_required
def campaign_new(request):
    return render(
        request,
        "communications/campaign_new.html",
        {"nav_section": "campaigns", "active_nav": "campaigns"},
    )


@communications_required
def campaign_detail(request):
    return render(
        request,
        "communications/campaign_detail.html",
        {"nav_section": "campaigns", "active_nav": "campaigns"},
    )

@communications_required
def templates(request):
    return render(
        request,
        "communications/templates.html",
        {"nav_section": "templates", "active_nav": "templates"},
    )

@communications_required
def segments(request):
    return render(
        request,
        "communications/segments.html",
        {"nav_section": "segments", "active_nav": "segments"},
    )
