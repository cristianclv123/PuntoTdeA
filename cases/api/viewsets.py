"""ViewSets de gestión completa del caso (bandeja) y creación de tickets.

Reutilizan las mismas reglas de negocio que las vistas HTML de cases/views.py
(cases.services.assignment/case_events/ingestion) para no duplicar lógica.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from cases.models import CaseComment, Channel, Contact, Conversation, Department, Message, ReplyTemplate
from cases.services.assignment import ClaimError, advisor_can_reply, claim_conversation
from cases.services.case_events import mark_claimed, mark_closed
from cases.services.ingestion import create_outbound_message
from cases.services.realtime import broadcast_conversation_update

from .serializers import (
    CaseCommentSerializer,
    ContactSerializer,
    ConversationCloseSerializer,
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    ConversationUpdateSerializer,
    DepartmentSerializer,
    MessageDetailSerializer,
    ReplyCreateSerializer,
    ReplyTemplateSerializer,
)


class DepartmentViewSet(viewsets.ModelViewSet):
    """Dependencias/áreas a las que se clasifican o escalan los casos."""

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]


class ReplyTemplateViewSet(viewsets.ModelViewSet):
    """Plantillas de respuesta rápida usadas por los asesores."""

    queryset = ReplyTemplate.objects.select_related("created_by").all()
    serializer_class = ReplyTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ContactViewSet(viewsets.ModelViewSet):
    """Gestión de contactos (estudiantes) asociados a los casos."""

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search)
                | Q(document_number__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
        return qs


class CaseCommentViewSet(viewsets.ModelViewSet):
    """Comentarios internos de un caso. Filtra por ?conversation=<id>."""

    queryset = CaseComment.objects.select_related("author").all()
    serializer_class = CaseCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        conversation_id = self.request.query_params.get("conversation")
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def _check_owner_or_staff(self, instance):
        if instance.author_id != self.request.user.id and not self.request.user.is_staff:
            raise PermissionDenied("Solo el autor o un administrador puede modificar este comentario.")

    def perform_update(self, serializer):
        self._check_owner_or_staff(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_owner_or_staff(instance)
        instance.delete()


class MessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Mensajes del caso, de solo lectura (se crean vía la acción 'reply' del
    ticket, que valida adjuntos y dispara el realtime). Filtra por
    ?conversation=<id>."""

    queryset = Message.objects.prefetch_related("attachments").all()
    serializer_class = MessageDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        conversation_id = self.request.query_params.get("conversation")
        if conversation_id:
            qs = qs.filter(conversation_id=conversation_id)
        elif self.action == "list":
            raise ValidationError({"conversation": "Este parámetro es requerido para listar mensajes."})
        return qs


class ConversationViewSet(viewsets.ModelViewSet):
    """Gestión completa del caso/ticket: creación, consulta, clasificación,
    toma, cierre y respuesta."""

    queryset = Conversation.objects.select_related(
        "channel", "contact", "department", "escalated_to",
        "assigned_to", "claimed_by", "closed_by",
    ).all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return ConversationCreateSerializer
        if self.action in ("update", "partial_update"):
            return ConversationUpdateSerializer
        if self.action == "close":
            return ConversationCloseSerializer
        if self.action == "reply":
            return ReplyCreateSerializer
        if self.action == "comments":
            return CaseCommentSerializer
        return ConversationDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action != "list":
            # Los filtros de estado son para la bandeja (listado); el acceso
            # por pk (retrieve/update/destroy/acciones) no debe verse afectado
            # o un caso recién cerrado quedaría inalcanzable por su propio id.
            return qs

        params = self.request.query_params
        status_filter = params.get("status")
        priority_filter = params.get("priority")
        department_filter = params.get("department")
        channel_filter = params.get("channel")
        assigned_to = params.get("assigned_to")
        unassigned = params.get("unassigned")
        closed = params.get("closed")

        if closed == "1":
            qs = qs.filter(status=Conversation.Status.CERRADO)
        elif status_filter:
            qs = qs.filter(status=status_filter)
        else:
            qs = qs.exclude(status=Conversation.Status.CERRADO)

        if priority_filter:
            qs = qs.filter(priority=priority_filter)
        if department_filter:
            qs = qs.filter(department_id=department_filter)
        if channel_filter:
            qs = qs.filter(channel__code=channel_filter)
        if unassigned == "1":
            qs = qs.filter(assigned_to__isnull=True)
        elif assigned_to == "me":
            qs = qs.filter(assigned_to=self.request.user)
        elif assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(ticket_number__icontains=search)
                | Q(contact__full_name__icontains=search)
                | Q(contact__document_number__icontains=search)
            )
        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        channel, _ = Channel.objects.get_or_create(
            code=data["channel"], defaults={"name": data["channel"].title(), "is_active": True}
        )
        if data.get("contact_id"):
            contact = get_object_or_404(Contact, pk=data["contact_id"])
        else:
            contact = Contact.objects.create(
                full_name=data["contact_full_name"],
                document_number=data["contact_document_number"],
                email=data.get("contact_email") or "",
                phone=data.get("contact_phone") or "",
                academic_program=data.get("contact_academic_program") or "Sin definir",
                semester=data.get("contact_semester") or 1,
            )

        conversation = Conversation.objects.create(
            channel=channel,
            contact=contact,
            theme=data.get("theme") or "",
            priority=data.get("priority") or Conversation.Priority.MEDIA,
            department_id=data.get("department_id"),
            status=Conversation.Status.PENDIENTE,
        )

        initial_message = (data.get("initial_message") or "").strip()
        if initial_message:
            Message.objects.create(
                conversation=conversation,
                direction=Message.Direction.INBOUND,
                body=initial_message,
            )

        conversation.refresh_from_db()
        output = ConversationDetailSerializer(conversation)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        return self._update(request, partial=False)

    def partial_update(self, request, *args, **kwargs):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        conversation = self.get_object()
        if conversation.status == Conversation.Status.CERRADO:
            raise ValidationError("Este caso está cerrado y no puede modificarse.")

        serializer = ConversationUpdateSerializer(
            instance=conversation, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        was_unassigned = conversation.assigned_to_id is None
        for field in ("status", "priority", "theme"):
            if field in data:
                setattr(conversation, field, data[field])
        if "department_id" in data:
            conversation.department_id = data["department_id"]
        if "escalated_to_id" in data:
            conversation.escalated_to_id = data["escalated_to_id"]
        if "assigned_to_id" in data:
            conversation.assigned_to_id = data["assigned_to_id"]
        if conversation.status != Conversation.Status.ESCALADO:
            conversation.escalated_to = None
        conversation.save()

        if conversation.assigned_to_id and (was_unassigned or not conversation.claimed_at):
            assignee = conversation.assigned_to or request.user
            mark_claimed(conversation, assignee, assign=False)

        conversation.refresh_from_db()
        return Response(ConversationDetailSerializer(conversation).data)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Solo un administrador puede eliminar un caso.")
        return super().destroy(request, *args, **kwargs)

    @extend_schema(responses=ConversationDetailSerializer)
    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        try:
            conversation = claim_conversation(pk, request.user)
        except ClaimError as exc:
            error_status = {
                "not_found": status.HTTP_404_NOT_FOUND,
                "already_assigned": status.HTTP_409_CONFLICT,
                "closed": status.HTTP_400_BAD_REQUEST,
                "unauthenticated": status.HTTP_401_UNAUTHORIZED,
            }.get(exc.code, status.HTTP_400_BAD_REQUEST)
            return Response({"detail": exc.message, "code": exc.code}, status=error_status)
        return Response(ConversationDetailSerializer(conversation).data)

    @extend_schema(request=ConversationCloseSerializer, responses=ConversationDetailSerializer)
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        conversation = self.get_object()
        if conversation.status == Conversation.Status.CERRADO:
            return Response({"detail": "El caso ya estaba cerrado."}, status=status.HTTP_200_OK)

        serializer = ConversationCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        assigned_to_id = data.get("assigned_to_id") or conversation.assigned_to_id
        department_id = data.get("department_id") or conversation.department_id
        if not assigned_to_id:
            if request.user.is_staff or conversation.assigned_to_id is None:
                assigned_to_id = request.user.id
        if not assigned_to_id:
            raise ValidationError("Debes asignar un asesor (assigned_to_id) antes de cerrar el caso.")
        if not department_id:
            raise ValidationError("Debes indicar la dependencia (department_id) antes de cerrar el caso.")

        conversation.assigned_to_id = assigned_to_id
        conversation.department_id = department_id
        if data.get("priority"):
            conversation.priority = data["priority"]
        conversation.escalated_to = None
        if not conversation.claimed_at:
            mark_claimed(conversation, conversation.assigned_to, assign=False)
        conversation.status = Conversation.Status.CERRADO
        conversation.save()
        mark_closed(conversation, request.user)
        broadcast_conversation_update(conversation)

        conversation.refresh_from_db()
        return Response(ConversationDetailSerializer(conversation).data)

    @extend_schema(
        request=ReplyCreateSerializer,
        responses=MessageDetailSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
    )
    def reply(self, request, pk=None):
        conversation = self.get_object()
        if not advisor_can_reply(conversation, request.user):
            raise PermissionDenied("Debes tomar el caso antes de responder.")

        serializer = ReplyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = create_outbound_message(
                conversation,
                serializer.validated_data.get("body", ""),
                user=request.user,
                uploaded_files=serializer.validated_data.get("attachments"),
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
        return Response(MessageDetailSerializer(message).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=MessageDetailSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="messages")
    def list_messages(self, request, pk=None):
        conversation = self.get_object()
        qs = conversation.messages.prefetch_related("attachments").order_by("sent_at", "id")
        page = self.paginate_queryset(qs)
        serializer = MessageDetailSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        request=CaseCommentSerializer,
        responses=CaseCommentSerializer(many=True),
    )
    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        conversation = self.get_object()
        if request.method == "POST":
            serializer = CaseCommentSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            if not serializer.validated_data.get("body"):
                raise ValidationError({"body": "Este campo es requerido."})
            comment = CaseComment.objects.create(
                conversation=conversation,
                author=request.user,
                body=serializer.validated_data["body"],
            )
            return Response(CaseCommentSerializer(comment).data, status=status.HTTP_201_CREATED)

        qs = conversation.comments.select_related("author").all()
        page = self.paginate_queryset(qs)
        serializer = CaseCommentSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
