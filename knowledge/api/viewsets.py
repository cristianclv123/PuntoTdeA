"""ViewSets CRUD para el contenido de la base de conocimiento."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from knowledge.models import Category, ChatConversation, FAQ, Intent, KnowledgeArticle
from knowledge.services.import_service import import_articles_from_excel, import_faqs_from_excel

from .serializers import (
    ArticleImportSerializer,
    CategorySerializer,
    ChatConversationSerializer,
    FAQImportSerializer,
    FAQSerializer,
    IntentSerializer,
    KnowledgeArticleSerializer,
)


_import_result_serializer = inline_serializer(
    name="KnowledgeImportResult",
    fields={
        "created": serializers.IntegerField(),
        "updated": serializers.IntegerField(),
        "skipped": serializers.IntegerField(),
        "errors": serializers.ListField(child=serializers.CharField()),
    },
)


def _import_result_response(result):
    return Response(
        {
            "created": result.created,
            "updated": result.updated,
            "skipped": result.skipped,
            "errors": result.errors,
        },
        status=status.HTTP_201_CREATED,
    )


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class IntentViewSet(viewsets.ModelViewSet):
    queryset = Intent.objects.all()
    serializer_class = IntentSerializer
    permission_classes = [permissions.IsAuthenticated]


class KnowledgeArticleViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeArticle.objects.select_related("category", "intent").all()
    serializer_class = KnowledgeArticleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if category_id := params.get("category"):
            qs = qs.filter(category_id=category_id)
        if status_filter := params.get("status"):
            qs = qs.filter(status=status_filter)
        if (published := params.get("published")) is not None:
            qs = qs.filter(published=published.lower() in {"1", "true"})
        return qs

    @extend_schema(request=ArticleImportSerializer, responses=_import_result_serializer)
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def import_excel(self, request):
        """POST /api/knowledge/articles/import_excel/ (multipart: file)

        Columnas del Excel: titulo, contenido, categoria (obligatorias);
        resumen, etiquetas, estado (opcionales).
        """
        payload = ArticleImportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        result = import_articles_from_excel(payload.validated_data["file"])
        return _import_result_response(result)


class FAQViewSet(viewsets.ModelViewSet):
    queryset = FAQ.objects.select_related("category", "intent").all()
    serializer_class = FAQSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if category_id := params.get("category"):
            qs = qs.filter(category_id=category_id)
        if (is_active := params.get("is_active")) is not None:
            qs = qs.filter(is_active=is_active.lower() in {"1", "true"})
        return qs

    @extend_schema(request=FAQImportSerializer, responses=_import_result_serializer)
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def import_excel(self, request):
        """POST /api/knowledge/faqs/import_excel/ (multipart: file)

        Columnas del Excel: pregunta, respuesta, categoria (obligatorias);
        activo (opcional).
        """
        payload = FAQImportSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        result = import_faqs_from_excel(payload.validated_data["file"])
        return _import_result_response(result)


class ChatConversationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Solo lectura: el estado lo muta ChatbotWorkflow (workflow.py) y el
    webhook de WhatsApp, no un CRUD genérico."""

    queryset = ChatConversation.objects.all()
    serializer_class = ChatConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if status_filter := params.get("status"):
            qs = qs.filter(status=status_filter)
        if channel := params.get("channel"):
            qs = qs.filter(channel=channel)
        return qs
