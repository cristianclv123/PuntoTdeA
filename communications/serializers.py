# DRF serializers
from rest_framework import serializers

from .models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    MessageTemplate,
)


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        ref_name = "CommunicationsContact"
        fields = [
            "id", "full_name", "document_number", "email", "phone",
            "academic_program", "semester", "role", "whatsapp_opt_in",
            "attributes", "source", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer de un borrador local de plantilla (aún no enviada a Meta)."""

    param_count = serializers.ReadOnlyField()

    class Meta:
        model = MessageTemplate
        fields = [
            "id", "name", "category",
            "body_text", "variable_types", "header_type",
            "header_text", "header_media_url", "buttons",
            "param_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "param_count", "created_at", "updated_at"]

    def validate(self, attrs):
        header_type = attrs.get(
            "header_type",
            getattr(
                self.instance,
                "header_type",
                MessageTemplate.HeaderType.NONE,
            ),
        )

        current_header_text = getattr(self.instance, "header_text", "")
        header_text = attrs.get("header_text", current_header_text)
        header_text = (header_text or "").strip()

        if header_type == MessageTemplate.HeaderType.TEXT:
            if not header_text:
                raise serializers.ValidationError(
                    {"header_text": "El encabezado de texto no puede estar vacío."}
                )

            if "{{" in header_text or "}}" in header_text:
                raise serializers.ValidationError(
                    {"header_text": "El encabezado de texto no admite variables."}
                )

            if len(header_text) > 60:
                raise serializers.ValidationError(
                    {"header_text": "El encabezado no puede superar 60 caracteres."}
                )

            attrs["header_text"] = header_text

        elif header_type == MessageTemplate.HeaderType.NONE:
            attrs["header_text"] = ""

        elif header_type in {
            MessageTemplate.HeaderType.IMAGE,
            MessageTemplate.HeaderType.VIDEO,
            MessageTemplate.HeaderType.DOCUMENT,
        }:
            raise serializers.ValidationError(
                {
                    "header_type": (
                        "Los encabezados multimedia todavía no están "
                        "disponibles para los borradores."
                    )
                }
            )

        return attrs

class AudienceSegmentSerializer(serializers.ModelSerializer):
    contact_count = serializers.ReadOnlyField()

    class Meta:
        model = AudienceSegment
        fields = [
            "id", "name", "description", "source_type", "filter_rules",
            "contact_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "contact_count", "created_at", "updated_at"]


class SegmentImportSerializer(serializers.Serializer):
    """Serializer de entrada para POST /segments/import_excel/ (multipart)."""

    name = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    file = serializers.FileField()


class BroadcastRecipientSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source="contact.full_name", read_only=True)

    class Meta:
        model = BroadcastRecipient
        fields = [
            "id", "campaign", "contact", "contact_name", "phone_snapshot",
            "params", "status", "provider", "provider_message_id",
            "error_message", "queued_at", "sent_at", "delivered_at", "read_at",
        ]
        read_only_fields = fields


class CampaignSerializer(serializers.ModelSerializer):
    # `template` se mantiene como alias del id de Meta para no romper a los
    # clientes que ya lo enviaban; ahora se guarda en `template_meta_id`.
    template = serializers.CharField(
        source="template_meta_id", required=False, allow_blank=True, max_length=64
    )
    segment_name = serializers.CharField(source="segment.name", read_only=True)

    total_recipients = serializers.ReadOnlyField()
    sent_count = serializers.ReadOnlyField()
    delivered_count = serializers.ReadOnlyField()
    read_count = serializers.ReadOnlyField()
    failed_count = serializers.ReadOnlyField()

    class Meta:
        model = Campaign
        fields = [
            "id", "name", "channel",
            "template", "template_name", "template_language", "template_snapshot",
            "segment", "segment_name",
            "default_params", "status", "scheduled_at", "rate_limit_per_minute",
            "created_by", "created_at", "updated_at", "sent_at",
            "total_recipients", "sent_count", "delivered_count",
            "read_count", "failed_count",
        ]
        read_only_fields = [
            "id", "channel", "status", "created_at", "updated_at", "sent_at",
            "total_recipients", "sent_count", "delivered_count",
            "read_count", "failed_count",
        ]