import mimetypes
from secrets import compare_digest

from django.conf import settings
from django.core import signing
from django.http import FileResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from cases.models import Channel, Contact, Conversation, Message, MessageAttachment
from cases.permissions import CASES_PERMISSION, HasCasesAccess
from PuntoTdeA.access import module_access_required
from cases.services.ingestion import (
    InboundPayload,
    create_outbound_message,
    ingest_inbound_message,
)
from cases.api.serializers import (
    ContactSerializer,
    ConversationSerializer,
    MessageSerializer,
    SimulateWebhookSerializer,
    WebContactCreateSerializer,
    WebMessageCreateSerializer,
    WidgetMessageCreateSerializer,
)

WIDGET_CREDENTIAL_MAX_AGE = 90 * 24 * 60 * 60
_CONTACT_CREDENTIAL_SALT = "cases.web-widget.contact.v1"
_CONVERSATION_CREDENTIAL_SALT = "cases.web-widget.conversation.v1"


def _signed_credential(request, *, salt):
    token = request.headers.get("X-Widget-Credential", "")
    if not token:
        return None
    try:
        payload = signing.loads(
            token,
            salt=salt,
            max_age=WIDGET_CREDENTIAL_MAX_AGE,
        )
    except signing.BadSignature:
        return None
    return payload if isinstance(payload, dict) else None


def _integration_token_valid(request):
    expected_token = getattr(settings, "CASES_WEB_WEBHOOK_TOKEN", "")
    provided_token = request.headers.get("X-Integration-Token", "")
    return bool(expected_token and provided_token) and compare_digest(
        str(expected_token),
        str(provided_token),
    )


@extend_schema(
    request=WebMessageCreateSerializer,
    responses=inline_serializer(
        name="WebWebhookResponse",
        fields={
            "created": serializers.BooleanField(),
            "conversation": ConversationSerializer(),
            "message": MessageSerializer(),
        },
    ),
    tags=["cases"],
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def web_webhook(request):
    if not _integration_token_valid(request):
        return Response(
            {"detail": "Credencial de integración inválida."},
            status=status.HTTP_403_FORBIDDEN,
        )

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


@extend_schema(
    request=SimulateWebhookSerializer,
    responses=inline_serializer(
        name="SimulateWebhookResponse",
        fields={
            "created": serializers.BooleanField(),
            "conversation_id": serializers.IntegerField(),
            "message_id": serializers.IntegerField(),
        },
    ),
    tags=["cases"],
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


@extend_schema(
    request=WebContactCreateSerializer,
    responses=inline_serializer(
        name="WidgetContactResponse",
        fields={
            "id": serializers.IntegerField(),
            "full_name": serializers.CharField(),
            "document_number": serializers.CharField(),
            "email": serializers.EmailField(),
            "phone": serializers.CharField(),
            "academic_program": serializers.CharField(),
            "semester": serializers.IntegerField(),
            "contact_credential": serializers.CharField(),
        },
    ),
    tags=["cases"],
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def web_create_contact(request):
    serializer = WebContactCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    contact, created = Contact.objects.get_or_create(
        document_number=serializer.validated_data["document_number"],
        defaults=serializer.validated_data,
    )
    if not created:
        return Response(
            {
                "detail": (
                    "No es posible iniciar o recuperar esta sesión sin verificar "
                    "la identidad."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response(
        {
            **ContactSerializer(contact).data,
            "contact_credential": signing.dumps(
                {"contact_id": contact.pk, "purpose": "contact"},
                salt=_CONTACT_CREDENTIAL_SALT,
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    request=WidgetMessageCreateSerializer,
    responses=inline_serializer(
        name="WidgetMessageResponse",
        fields={
            "conversation_id": serializers.IntegerField(),
            "message": MessageSerializer(),
            "conversation_credential": serializers.CharField(),
        },
    ),
    tags=["cases"],
)
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def web_create_message(request):
    payload = _signed_credential(request, salt=_CONTACT_CREDENTIAL_SALT)
    contact_id = payload.get("contact_id") if payload else None
    if (
        not payload
        or payload.get("purpose") != "contact"
        or not isinstance(contact_id, int)
    ):
        return Response(
            {"detail": "La credencial del widget no es válida o venció."},
            status=status.HTTP_403_FORBIDDEN,
        )

    contact = get_object_or_404(Contact, pk=contact_id)
    serializer = WidgetMessageCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
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
    conversation_credential = signing.dumps(
        {
            "conversation_id": conversation.pk,
            "contact_id": contact.pk,
            "purpose": "conversation",
        },
        salt=_CONVERSATION_CREDENTIAL_SALT,
    )
    return Response(
        {
            "conversation_id": conversation.pk,
            "message": MessageSerializer(message).data,
            "conversation_credential": conversation_credential,
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="after_id",
            type=int,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Sólo devuelve mensajes con id mayor a este valor.",
        ),
    ],
    responses=inline_serializer(
        name="WebListMessagesResponse",
        fields={
            "conversation_id": serializers.IntegerField(),
            "messages": MessageSerializer(many=True),
        },
    ),
    tags=["cases"],
)
@csrf_exempt
@api_view(["GET"])
@permission_classes([AllowAny])
def web_list_messages(request, conversation_id: int):
    payload = _signed_credential(request, salt=_CONVERSATION_CREDENTIAL_SALT)
    if (
        not payload
        or payload.get("purpose") != "conversation"
        or payload.get("conversation_id") != conversation_id
        or not isinstance(payload.get("contact_id"), int)
    ):
        return Response(
            {"detail": "La credencial del widget no es válida o venció."},
            status=status.HTTP_403_FORBIDDEN,
        )

    conversation = get_object_or_404(Conversation, pk=conversation_id, channel__code=Channel.Code.WEB)
    if conversation.contact_id != payload["contact_id"]:
        return Response(
            {"detail": "La credencial no corresponde a esta conversación."},
            status=status.HTTP_403_FORBIDDEN,
        )
    after_id = request.GET.get("after_id")
    qs = conversation.messages.exclude(
        direction=Message.Direction.SYSTEM
    ).order_by("sent_at", "id")
    if after_id:
        qs = qs.filter(id__gt=after_id)
    return Response(
        {
            "conversation_id": conversation.id,
            "messages": MessageSerializer(qs, many=True).data,
        }
    )


@extend_schema(
    request=inline_serializer(
        name="AdvisorReplyRequest",
        fields={"body": serializers.CharField()},
    ),
    responses=MessageSerializer,
    tags=["cases"],
)
@api_view(["POST"])
@permission_classes([HasCasesAccess])
def advisor_reply(request, conversation_id: int):
    from cases.services.assignment import advisor_can_reply

    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not advisor_can_reply(conversation, request.user):
        return Response(
            {"detail": "Debes tomar el chat antes de responder."},
            status=status.HTTP_403_FORBIDDEN,
        )
    body = (request.data.get("body") or "").strip()
    if not body:
        return Response({"detail": "body requerido"}, status=status.HTTP_400_BAD_REQUEST)
    message = create_outbound_message(conversation, body, user=request.user)
    return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


@module_access_required(CASES_PERMISSION, module_name="Cases")
@require_GET
def download_attachment(request, attachment_id: int):
    attachment = get_object_or_404(MessageAttachment, pk=attachment_id)
    guessed_type, _encoding = mimetypes.guess_type(
        attachment.original_name,
        strict=True,
    )
    stored_type = (attachment.content_type or "").split(";", 1)[0].strip().lower()
    safe_inline_types = {
        MessageAttachment.Kind.IMAGE: {
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        },
        MessageAttachment.Kind.VIDEO: {
            "video/mp4",
            "video/webm",
            "video/quicktime",
            "video/x-m4v",
        },
    }
    allowed_types = safe_inline_types.get(attachment.kind, set())
    safe_inline = bool(
        guessed_type in allowed_types
        and stored_type == guessed_type
    )
    response = FileResponse(
        attachment.file.open("rb"),
        as_attachment=not safe_inline,
        filename=attachment.original_name,
        content_type=guessed_type if safe_inline else "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response

def deny_direct_attachment_media(request, path: str):
    """Impide acceder a los adjuntos de Cases mediante /media/."""
    return HttpResponseNotFound("Archivo no encontrado.")
