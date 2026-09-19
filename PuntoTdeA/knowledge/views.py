from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q

from .models import FAQ, KnowledgeArticle
from .services.indexing_service import index_academic_calendar
from .services.rag_service import answer_query, search_knowledge


def index(request):
    now = timezone.now()
    articles = getattr(KnowledgeArticle, 'objects').filter(published=True, status='published')[:10]
    faqs = getattr(FAQ, 'objects').filter(is_active=True).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now),
        Q(valid_until__isnull=True) | Q(valid_until__gte=now),
    )[:5]
    return render(request, 'knowledge/index.html', {'articles': articles, 'faqs': faqs})


def search(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    query = request.GET.get('q', '').strip()
    results = search_knowledge(query) if query else []
    return JsonResponse({'results': results, 'query': query})


def ask(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Método no permitido.'}, status=405)
    query = request.GET.get('q', '').strip()
    response = answer_query(query)
    return JsonResponse(response)


def reindex_academic_calendar(_request):
    payload = index_academic_calendar()
    return JsonResponse({'status': 'ok', 'payload': payload})
