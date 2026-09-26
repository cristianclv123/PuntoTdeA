from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cases.api import views, viewsets

router = DefaultRouter()
router.register("tickets", viewsets.ConversationViewSet, basename="ticket")
router.register("departments", viewsets.DepartmentViewSet, basename="department")
router.register("reply-templates", viewsets.ReplyTemplateViewSet, basename="reply-template")
router.register("comments", viewsets.CaseCommentViewSet, basename="case-comment")
router.register("messages", viewsets.MessageViewSet, basename="case-message")
router.register("contacts", viewsets.ContactViewSet, basename="contact")

urlpatterns = [
    # Webhooks e ingesta (públicos / integraciones externas)
    path("webhooks/web/", views.web_webhook, name="web-webhook"),
    path("webhooks/simulate/", views.simulate_webhook, name="simulate-webhook"),
    path("web/contacts/", views.web_create_contact, name="web-contacts"),
    path("web/messages/", views.web_webhook, name="web-messages"),
    path(
        "web/conversations/<int:conversation_id>/messages/",
        views.web_list_messages,
        name="web-messages-list",
    ),
    path(
        "conversations/<int:conversation_id>/reply/",
        views.advisor_reply,
        name="advisor-reply",
    ),

    # Gestión completa del caso / creación de tickets (uso interno)
    path("", include(router.urls)),
]
