"""ViewSets CRUD para el contenido de la base de conocimiento."""
from rest_framework import mixins, permissions, viewsets

from knowledge.models import Category, ChatConversation, FAQ, Intent, KnowledgeArticle

from .serializers import (
    CategorySerializer,
    ChatConversationSerializer,
    FAQSerializer,
    IntentSerializer,
    KnowledgeArticleSerializer,
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
