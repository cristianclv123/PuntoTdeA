from django.shortcuts import render

from .mock_data import CATEGORIES, FAQS


def faq_list(request):
    context = {
        "active_nav": "knowledge",
        "categories": CATEGORIES,
        "faqs": FAQS,
    }
    return render(request, "knowledge/base_conocimiento.html", context)
