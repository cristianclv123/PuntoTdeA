from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from cases.constants import channel_ui


def _conversation_payload(conversation, last_message_body: str = "") -> dict:
    contact = conversation.contact
    channel_code = conversation.channel.code
    ui = channel_ui(channel_code)
    advisor = (
        conversation.assigned_to.get_full_name()
        or conversation.assigned_to.username
        if conversation.assigned_to
        else "Sin asignar"
    )
    body = last_message_body
    if not body:
        last = conversation.messages.order_by("-sent_at", "-id").first()
        body = last.body if last else ""
    return {
        "id": conversation.id,
        "ticket_number": conversation.ticket_number or f"TDEA-{conversation.id:06d}",
        "name": contact.full_name,
        "initials": contact.initials,
        "role": contact.academic_program,
        "last_message": body,
        "theme": conversation.theme or "General",
        "department_name": conversation.department.name if conversation.department_id else "Sin dependencia",
        "priority": conversation.priority,
        "priority_label": conversation.get_priority_display(),
        "time": conversation.last_message_at.strftime("%H:%M"),
        "advisor": advisor,
        "status": conversation.status,
        "detail_url": f"/bandeja/{conversation.id}/",
        **ui,
    }


def _message_payload(message) -> dict:
    attachments = [
        {
            "id": att.id,
            "url": att.file.url,
            "name": att.original_name,
            "kind": att.kind,
        }
        for att in message.attachments.all()
    ]
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "direction": message.direction,
        "body": message.body,
        "from_agent": message.direction == "outbound",
        "text": message.body,
        "time": message.sent_at.strftime("%H:%M"),
        "sent_at": message.sent_at.isoformat(),
        "attachments": attachments,
    }


def broadcast_new_message(message) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    conversation = message.conversation
    conversation_payload = _conversation_payload(conversation, last_message_body=message.body)
    message_payload = _message_payload(message)

    async_to_sync(channel_layer.group_send)(
        "bandeja",
        {
            "type": "bandeja.event",
            "event": "conversation.upsert",
            "conversation": conversation_payload,
        },
    )
    async_to_sync(channel_layer.group_send)(
        f"conversation_{conversation.id}",
        {
            "type": "conversation.event",
            "event": "message.new",
            "message": message_payload,
        },
    )
