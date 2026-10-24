import mimetypes

from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from django.db import models
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from knowledge.services.indexing_service import index_academic_calendar
from knowledge.services.rag_service import answer_query, search_knowledge
from knowledge.models import FAQ

_search_result = inline_serializer(
    name="KnowledgeSearchResult",
    fields={
        "id": serializers.IntegerField(),
        "title": serializers.CharField(),
        "summary": serializers.CharField(),
        "content": serializers.CharField(),
        "category": serializers.CharField(),
        "score": serializers.FloatField(),
        "source_type": serializers.ChoiceField(choices=["article", "faq"]),
        "image_url": serializers.CharField(required=False, allow_null=True),
    },
)


def faq_image(request, faq_id: int):
    now = timezone.now()
    faq = FAQ.objects.filter(pk=faq_id, is_active=True).filter(
        models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now),
    ).filter(
        models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=now),
    ).first()
    if faq is None or not faq.image or not faq.image.storage.exists(faq.image.name):
        raise Http404

    content_type = mimetypes.guess_type(faq.image.name)[0] or 'application/octet-stream'
    response = FileResponse(faq.image.open('rb'), content_type=content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@extend_schema(
    parameters=[OpenApiParameter(name="q", type=str, location=OpenApiParameter.QUERY, required=False)],
    responses=inline_serializer(
        name="KnowledgeSearchResponse",
        fields={"results": _search_result, "query": serializers.CharField()},
    ),
    tags=["knowledge"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search(request):
    query = request.GET.get("q", "").strip()
    results = search_knowledge(query) if query else []
    return Response({"results": results, "query": query})


@extend_schema(
    parameters=[OpenApiParameter(name="q", type=str, location=OpenApiParameter.QUERY, required=False)],
    responses=inline_serializer(
        name="KnowledgeAskResponse",
        fields={
            "answer": serializers.CharField(),
            "confidence": serializers.FloatField(),
            "needs_human_attention": serializers.BooleanField(),
            "sources": _search_result,
        },
    ),
    tags=["knowledge"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ask(request):
    query = request.GET.get("q", "").strip()
    return Response(answer_query(query))


@extend_schema(
    request=None,
    responses=inline_serializer(
        name="ReindexAcademicCalendarResponse",
        fields={
            "status": serializers.CharField(),
            "payload": inline_serializer(
                name="ReindexAcademicCalendarPayload",
                fields={
                    "created": serializers.IntegerField(),
                    "updated": serializers.IntegerField(),
                    "items": serializers.IntegerField(),
                },
            ),
        },
    ),
    tags=["knowledge"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reindex_academic_calendar(request):
    payload = index_academic_calendar()
    return Response({"status": "ok", "payload": payload})
