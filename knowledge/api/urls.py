from django.urls import include, path
from rest_framework.routers import DefaultRouter

from knowledge.api import views, viewsets

router = DefaultRouter()
router.register("categories", viewsets.CategoryViewSet, basename="category")
router.register("intents", viewsets.IntentViewSet, basename="intent")
router.register("articles", viewsets.KnowledgeArticleViewSet, basename="article")
router.register("faqs", viewsets.FAQViewSet, basename="faq")
router.register("conversations", viewsets.ChatConversationViewSet, basename="chat-conversation")

urlpatterns = [
    path("search/", views.search, name="knowledge-search"),
    path("ask/", views.ask, name="knowledge-ask"),
    path(
        "reindex-academic-calendar/",
        views.reindex_academic_calendar,
        name="knowledge-reindex-academic-calendar",
    ),
    path("", include(router.urls)),
]
