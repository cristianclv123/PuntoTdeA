from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .models import FAQ, KnowledgeArticle
from .services.indexing_service import index_academic_calendar
from .services.rag_service import answer_query, search_knowledge


@login_required
def index(request):
    articles = KnowledgeArticle.objects.filter(published=True, status="published")[:10]
    faqs = FAQ.objects.filter(is_active=True)[:5]
    return render(
        request,
        "knowledge/index.html",
        {"articles": articles, "faqs": faqs, "active_nav": "knowledge"},
    )


@login_required
def faq_list(request):
    return index(request)


@login_required
def search(request):
    query = request.GET.get("q", "").strip()
    results = search_knowledge(query) if query else []
    return JsonResponse({"results": results, "query": query})


@login_required
def ask(request):
    query = request.GET.get("q", "").strip()
    response = answer_query(query)
    return JsonResponse(response)


@login_required
def reindex_academic_calendar(_request):
    payload = index_academic_calendar()
    return JsonResponse({"status": "ok", "payload": payload})
