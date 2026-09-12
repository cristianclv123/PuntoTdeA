import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from cases.models import Channel, Contact, Conversation, Message
from cases.services.ingestion import (
    InboundPayload,
    create_outbound_message,
    ingest_inbound_message,
)
from cases.services.meta import parse_meta_webhook, validate_meta_signature, verify_meta_token
from cases.api.serializers import (
    ContactSerializer,
    ConversationSerializer,
    MessageSerializer,
    SimulateWebhookSerializer,
    WebContactCreateSerializer,
    WebMessageCreateSerializer,
)


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def meta_webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode", "")
        token = request.GET.get("hub.verify_token", "")
        challenge = request.GET.get("hub.challenge", "")
        verified = verify_meta_token(mode, token, challenge)
        if verified is None:
            return HttpResponseForbidden("Verification failed")
        return HttpResponse(verified, content_type="text/plain")

    raw_body = request.body
    signature = request.META.get("HTTP_X_HUB_SIGNATURE_256")
    if not validate_meta_signature(raw_body, signature):
        return HttpResponseForbidden("Invalid signature")

    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return Response({"detail": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

    created = 0
    for inbound in parse_meta_webhook(payload):
        _, _, was_created = ingest_inbound_message(inbound)
        if was_created:
            created += 1
    return Response({"ok": True, "created": created})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def web_webhook(request):
    serializer = WebMessageCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if data.get("contact_id"):
        contact = get_object_or_404(Contact, pk=data["contact_id"])
    else:
        contact = get_object_or_404(Contact, document_number=data["document_number"])

    inbound = InboundPayload(
        channel_code=Channel.Code.WEB,
        external_thread_id=f"web-{contact.document_number}",
        body=data["body"],
        external_message_id=f"web-{get_random_string(16)}",
        contact_full_name=contact.full_name,
        contact_document_number=contact.document_number,
        contact_email=contact.email,
        contact_phone=contact.phone,
        contact_academic_program=contact.academic_program,
        contact_semester=contact.semester,
        theme=data.get("theme") or "",
    )
    conversation, message, created = ingest_inbound_message(inbound)
    return Response(
        {
            "created": created,
            "conversation": ConversationSerializer(conversation).data,
            "message": MessageSerializer(message).data,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def simulate_webhook(request):
    if not settings.ALLOW_WEBHOOK_SIMULATOR:
        return Response({"detail": "Only available in DEBUG"}, status=status.HTTP_403_FORBIDDEN)

    serializer = SimulateWebhookSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    channel = data["channel"]
    thread = data.get("external_thread_id") or f"sim-{channel}-{get_random_string(8)}"
    phone = data.get("phone") or "3000000000"
    document = data.get("document_number") or f"SIM-{phone}"

    inbound = InboundPayload(
        channel_code=channel,
        external_thread_id=thread,
        body=data["body"],
        external_message_id=data.get("external_message_id") or f"sim-{get_random_string(12)}",
        contact_full_name=data.get("full_name") or "Usuario simulado",
        contact_document_number=document,
        contact_email=data.get("email") or f"{document.lower()}@sim.local",
        contact_phone=phone,
        contact_academic_program=data.get("academic_program") or "Sin definir",
        contact_semester=data.get("semester") or 1,
        theme=data.get("theme") or "",
    )
    conversation, message, created = ingest_inbound_message(inbound)
    return Response(
        {
            "created": created,
            "conversation_id": conversation.id,
            "message_id": message.id,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def web_create_contact(request):
    serializer = WebContactCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    contact, created = Contact.objects.update_or_create(
        document_number=serializer.validated_data["document_number"],
        defaults=serializer.validated_data,
    )
    return Response(
        ContactSerializer(contact).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def web_list_messages(request, conversation_id: int):
    conversation = get_object_or_404(Conversation, pk=conversation_id, channel__code=Channel.Code.WEB)
    after_id = request.GET.get("after_id")
    qs = conversation.messages.order_by("sent_at", "id")
    if after_id:
        qs = qs.filter(id__gt=after_id)
    return Response(
        {
            "conversation_id": conversation.id,
            "messages": MessageSerializer(qs, many=True).data,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def advisor_reply(request, conversation_id: int):
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    body = (request.data.get("body") or "").strip()
    if not body:
        return Response({"detail": "body requerido"}, status=status.HTTP_400_BAD_REQUEST)
    message = create_outbound_message(conversation, body, user=request.user if request.user.is_authenticated else None)
    # Stub Meta send: real delivery requires META_ACCESS_TOKEN + Graph API call.
    return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
