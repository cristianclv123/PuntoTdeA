from django.urls import re_path

from cases import consumers

websocket_urlpatterns = [
    re_path(r"ws/bandeja/$", consumers.BandejaConsumer.as_asgi()),
    re_path(
        r"ws/conversations/(?P<conversation_id>\d+)/$",
        consumers.ConversationConsumer.as_asgi(),
    ),
]
