from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from knowledge.services.indexing_service import index_academic_calendar
from knowledge.services.rag_service import answer_query, search_knowledge

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
