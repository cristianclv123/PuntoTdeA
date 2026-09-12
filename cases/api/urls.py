from django.urls import path

from cases.api import views

urlpatterns = [
    path("webhooks/meta/", views.meta_webhook, name="meta-webhook"),
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
]
