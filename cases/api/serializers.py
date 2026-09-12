from rest_framework import serializers

from cases.models import Contact, Conversation, Message


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

    def get_from_agent(self, obj):
        return obj.direction == Message.Direction.OUTBOUND

    def get_time(self, obj):
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
