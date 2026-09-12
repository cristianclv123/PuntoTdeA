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
        fields = [
            "id", "full_name", "document_number", "email", "phone",
            "academic_program", "semester", "role", "whatsapp_opt_in",
            "attributes", "source", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MessageTemplateSerializer(serializers.ModelSerializer):
    param_count = serializers.ReadOnlyField()

    class Meta:
        model = MessageTemplate
        fields = [
            "id", "name", "meta_template_name", "language", "category",
            "body_text", "header_type", "header_media_url", "buttons",
            "status", "param_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


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
    template_name = serializers.CharField(source="template.name", read_only=True)
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
            "template", "template_name", "segment", "segment_name",
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