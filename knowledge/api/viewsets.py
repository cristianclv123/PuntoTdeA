"""ViewSets CRUD para el contenido de la base de conocimiento."""
from typing import TypeVar, cast

from django.db import models
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from knowledge.chatbot.case_status import CaseStatusAPIError, get_case_status
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


_ModelT = TypeVar("_ModelT", bound=models.Model)


def _model_manager(model: type[_ModelT]) -> models.Manager[_ModelT]:
    """Devuelve el manager de Django con su tipo concreto para Pylance."""
    return cast(models.Manager[_ModelT], getattr(model, "objects"))


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
    queryset = _model_manager(Category).all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class IntentViewSet(viewsets.ModelViewSet):
    queryset = _model_manager(Intent).all()
    serializer_class = IntentSerializer
    permission_classes = [permissions.IsAuthenticated]


class KnowledgeArticleViewSet(viewsets.ModelViewSet):
    queryset = _model_manager(KnowledgeArticle).select_related("category", "intent").all()
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
    queryset = _model_manager(FAQ).select_related("category", "intent").all()
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

    queryset = _model_manager(ChatConversation).all()
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

    @extend_schema(
        responses=inline_serializer(
            name="ChatConversationTicketStatus",
            fields={
                "conversation_id": serializers.UUIDField(),
                "ticket_id": serializers.IntegerField(),
                "status": serializers.CharField(),
            },
        ),
    )
    @action(detail=True, methods=["get"], url_path="ticket-status")
    def ticket_status(self, request, pk=None):
        """Consulta en cases el estado del ticket asociado a esta conversación."""
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        conversation = get_object_or_404(queryset, **{lookup_url_kwarg: pk})
        self.check_object_permissions(request, conversation)
        ticket_id = conversation.case_conversation_id
        if ticket_id is None:
            return Response(
                {"detail": "Esta conversación no tiene un ticket de asesor asociado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            remote_status = get_case_status(ticket_id)
        except CaseStatusAPIError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            "conversation_id": conversation.pk,
            "ticket_id": ticket_id,
            "status": remote_status,
        })
