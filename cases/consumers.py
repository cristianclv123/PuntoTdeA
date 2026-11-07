import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model

from cases.models import Conversation
from cases.permissions import CASES_PERMISSION
from PuntoTdeA.access import user_has_explicit_permission


@database_sync_to_async
def _user_has_cases_access(user):
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "pk", None)
    ):
        return False

    refreshed_user = get_user_model()._default_manager.filter(
        pk=user.pk
    ).first()
    return user_has_explicit_permission(refreshed_user, CASES_PERMISSION)


@database_sync_to_async
def _conversation_exists(conversation_id):
    return Conversation.objects.filter(pk=conversation_id).exists()


class BandejaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        if (
            user is None
            or not getattr(user, "is_authenticated", False)
            or not getattr(user, "is_active", False)
        ):
            await self.close(code=4401)
            return

        if not await _user_has_cases_access(user):
            await self.close(code=4403)
            return

        self.group_name = "bandeja"
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)

        if group_name:
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name,
            )

    async def bandeja_event(self, event):
        if not await _user_has_cases_access(self.scope.get("user")):
            await self.close(code=4403)
            return
        await self.send(text_data=json.dumps(event))


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        if (
            user is None
            or not getattr(user, "is_authenticated", False)
            or not getattr(user, "is_active", False)
        ):
            await self.close(code=4401)
            return

        if not await _user_has_cases_access(user):
            await self.close(code=4403)
            return

        conversation_id = self.scope["url_route"]["kwargs"].get(
            "conversation_id"
        )

        try:
            self.conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            await self.close(code=4404)
            return

        if not await _conversation_exists(self.conversation_id):
            await self.close(code=4404)
            return

        self.group_name = f"conversation_{self.conversation_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)

        if group_name:
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name,
            )

    async def conversation_event(self, event):
        if not await _user_has_cases_access(self.scope.get("user")):
            await self.close(code=4403)
            return
        await self.send(text_data=json.dumps(event))