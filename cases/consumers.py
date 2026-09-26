import json

from channels.generic.websocket import AsyncWebsocketConsumer


class BandejaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.channel_layer.group_add("bandeja", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("bandeja", self.channel_name)

    async def bandeja_event(self, event):
        await self.send(text_data=json.dumps(event))


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.group_name = f"conversation_{self.conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def conversation_event(self, event):
        await self.send(text_data=json.dumps(event))
