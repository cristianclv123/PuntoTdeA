from django.contrib.auth import get_user_model
from rest_framework import serializers

from cases.models import (
    CaseComment,
    Channel,
    Contact,
    Conversation,
    Department,
    Message,
    MessageAttachment,
    ReplyTemplate,
)

User = get_user_model()


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = [
            "id",
            "full_name",
            "document_number",
            "email",
            "phone",
            "academic_program",
            "semester",
        ]


class WebContactCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = [
            "full_name",
            "document_number",
            "email",
            "phone",
            "academic_program",
            "semester",
        ]

    def validate_semester(self, value):
        if value < 1 or value > 20:
            raise serializers.ValidationError("Semestre inválido.")
        return value


class WebMessageCreateSerializer(serializers.Serializer):
    contact_id = serializers.IntegerField(required=False)
    document_number = serializers.CharField(required=False, allow_blank=True)
    body = serializers.CharField()
    theme = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("contact_id") and not attrs.get("document_number"):
            raise serializers.ValidationError(
                "Se requiere contact_id o document_number."
            )
        return attrs


class SimulateWebhookSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(
        choices=["whatsapp", "facebook", "instagram", "web"]
    )
    body = serializers.CharField()
    external_thread_id = serializers.CharField(required=False, allow_blank=True)
    external_message_id = serializers.CharField(required=False, allow_blank=True)
    full_name = serializers.CharField(required=False, allow_blank=True)
    document_number = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    academic_program = serializers.CharField(required=False, allow_blank=True)
    semester = serializers.IntegerField(required=False, min_value=1, max_value=20)
    theme = serializers.CharField(required=False, allow_blank=True, default="")


class MessageSerializer(serializers.ModelSerializer):
    from_agent = serializers.SerializerMethodField()
    text = serializers.CharField(source="body", read_only=True)
    time = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "direction",
            "body",
            "text",
            "from_agent",
            "time",
            "sent_at",
            "external_id",
        ]

    def get_from_agent(self, obj) -> bool:
        return obj.direction == Message.Direction.OUTBOUND

    def get_time(self, obj) -> str:
        return obj.sent_at.strftime("%H:%M")


class ConversationSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    channel = serializers.CharField(source="channel.code", read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "channel",
            "contact",
            "status",
            "theme",
            "external_thread_id",
            "last_message_at",
        ]


class AdvisorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        ref_name = "CaseAdvisor"
        fields = ["id", "username", "full_name"]

    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name", "is_active"]


class ReplyTemplateSerializer(serializers.ModelSerializer):
    created_by = AdvisorSerializer(read_only=True)

    class Meta:
        model = ReplyTemplate
        fields = [
            "id", "title", "body", "is_active",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]


class CaseCommentSerializer(serializers.ModelSerializer):
    author = AdvisorSerializer(read_only=True)

    class Meta:
        model = CaseComment
        fields = ["id", "conversation", "author", "body", "created_at"]
        read_only_fields = ["author", "created_at"]


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = [
            "id", "message", "file", "original_name",
            "content_type", "kind", "size_bytes", "created_at",
        ]
        read_only_fields = fields


class MessageDetailSerializer(MessageSerializer):
    attachments = MessageAttachmentSerializer(many=True, read_only=True)

    class Meta(MessageSerializer.Meta):
        fields = MessageSerializer.Meta.fields + ["attachments"]


class ConversationDetailSerializer(serializers.ModelSerializer):
    """Vista completa del caso/ticket para la gestión interna (bandeja)."""

    contact = ContactSerializer(read_only=True)
    channel = serializers.CharField(source="channel.code", read_only=True)
    department = DepartmentSerializer(read_only=True)
    escalated_to = DepartmentSerializer(read_only=True)
    assigned_to = AdvisorSerializer(read_only=True)
    claimed_by = AdvisorSerializer(read_only=True)
    closed_by = AdvisorSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    messages_count = serializers.IntegerField(source="messages.count", read_only=True)
    comments_count = serializers.IntegerField(source="comments.count", read_only=True)

    class Meta:
        model = Conversation
        ref_name = "TicketDetail"
        fields = [
            "id", "ticket_number", "channel", "contact",
            "status", "status_label", "priority", "priority_label",
            "department", "escalated_to", "theme",
            "assigned_to", "claimed_at", "claimed_by",
            "closed_at", "closed_by",
            "messages_count", "comments_count",
            "last_message_at", "created_at", "updated_at",
        ]


class ConversationCreateSerializer(serializers.Serializer):
    """Crea un ticket/caso nuevo.

    El contacto se referencia por `contact_id` (existente) o se crea uno
    nuevo con los campos `contact_*`.
    """

    channel = serializers.ChoiceField(choices=Channel.Code.choices)
    contact_id = serializers.IntegerField(required=False)
    contact_full_name = serializers.CharField(required=False, allow_blank=True)
    contact_document_number = serializers.CharField(required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_blank=True)
    contact_academic_program = serializers.CharField(required=False, allow_blank=True)
    contact_semester = serializers.IntegerField(required=False, min_value=1, max_value=20)
    theme = serializers.CharField(required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(
        choices=Conversation.Priority.choices, required=False, default=Conversation.Priority.MEDIA
    )
    department_id = serializers.IntegerField(required=False)
    initial_message = serializers.CharField(required=False, allow_blank=True)

    def validate_department_id(self, value):
        if not Department.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Dependencia no encontrada.")
        return value

    def validate(self, attrs):
        if attrs.get("contact_id"):
            if not Contact.objects.filter(pk=attrs["contact_id"]).exists():
                raise serializers.ValidationError({"contact_id": "Contacto no encontrado."})
        elif not (attrs.get("contact_full_name") and attrs.get("contact_document_number")):
            raise serializers.ValidationError(
                "Se requiere contact_id, o contact_full_name y contact_document_number "
                "para crear un contacto nuevo."
            )
        return attrs


class ConversationUpdateSerializer(serializers.Serializer):
    """Gestión del caso: estado, prioridad, dependencia y asignación.

    Para cerrar un caso usa la acción `close`, no este endpoint: el cierre
    exige asesor asignado y dependencia, y registra el evento de auditoría.
    """

    status = serializers.ChoiceField(choices=Conversation.Status.choices, required=False)
    priority = serializers.ChoiceField(choices=Conversation.Priority.choices, required=False)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    escalated_to_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    theme = serializers.CharField(required=False, allow_blank=True)

    def validate_status(self, value):
        if value == Conversation.Status.CERRADO:
            raise serializers.ValidationError(
                "No puedes cerrar el caso desde aquí; usa la acción 'close'."
            )
        return value

    def validate_department_id(self, value):
        if value is not None and not Department.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Dependencia no encontrada.")
        return value

    def validate_escalated_to_id(self, value):
        if value is not None and not Department.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Dependencia no encontrada.")
        return value

    def validate_assigned_to_id(self, value):
        if value is not None and not User.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("Asesor no encontrado o inactivo.")
        return value

    def validate(self, attrs):
        status = attrs.get("status", getattr(self.instance, "status", None))
        escalated_to_id = attrs.get(
            "escalated_to_id",
            getattr(self.instance, "escalated_to_id", None) if self.instance else None,
        )
        if status == Conversation.Status.ESCALADO and not escalated_to_id:
            raise serializers.ValidationError(
                "Si el caso está escalado, debes indicar 'escalated_to_id'."
            )
        return attrs


class ConversationCloseSerializer(serializers.Serializer):
    """Cierra el caso. Requiere asesor asignado y dependencia (ya existentes
    o enviados en esta misma petición)."""

    priority = serializers.ChoiceField(choices=Conversation.Priority.choices, required=False)
    department_id = serializers.IntegerField(required=False)
    assigned_to_id = serializers.IntegerField(required=False)

    def validate_department_id(self, value):
        if not Department.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Dependencia no encontrada.")
        return value

    def validate_assigned_to_id(self, value):
        if not User.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("Asesor no encontrado o inactivo.")
        return value


class ReplyCreateSerializer(serializers.Serializer):
    body = serializers.CharField(required=False, allow_blank=True)
    attachments = serializers.ListField(
        child=serializers.FileField(), required=False
    )
