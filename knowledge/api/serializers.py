from django.urls import reverse
from rest_framework import serializers

from knowledge.models import Category, ChatConversation, FAQ, Intent, KnowledgeArticle


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "is_active"]
        read_only_fields = ["slug"]


class IntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intent
        fields = ["id", "name", "slug", "description", "confidence_threshold", "is_active"]
        read_only_fields = ["slug"]


class KnowledgeArticleSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeArticle
        fields = [
            "id", "title", "slug", "summary", "content",
            "category", "intent", "tags", "status", "published",
            "published_at", "created_at", "updated_at",
        ]
        read_only_fields = ["slug", "published_at", "created_at", "updated_at"]


class FAQSerializer(serializers.ModelSerializer):
    # `image` recibe el archivo (multipart) y `image_url` lo expone de solo
    # lectura; los bytes se guardan con `set_image`, nunca en MEDIA_ROOT.
    image = serializers.FileField(write_only=True, required=False)
    clear_image = serializers.BooleanField(write_only=True, required=False)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = FAQ
        fields = [
            "id", "question", "answer", "category", "intent",
            "is_active", "order", "valid_from", "valid_until",
            "image", "image_url",
        ]
        read_only_fields = ["id", "image_url"]

    def get_image_url(self, obj):
        if not obj.has_image:
            return None
        return reverse("knowledge:faq-image", args=[obj.pk])

    def create(self, validated_data):
        uploaded = validated_data.pop("image", None)
        instance = super().create(validated_data)
        if uploaded is not None:
            instance.set_image(uploaded)
            instance.save(update_fields=[
                "image_data", "image_name", "image_content_type", "updated_at",
            ])
        return instance

    def update(self, instance, validated_data):
        clear_image = validated_data.pop("clear_image", False)
        uploaded = validated_data.pop("image", None)
        instance = super().update(instance, validated_data)
        if clear_image:
            instance.image_data = None
            instance.image_name = ""
            instance.image_content_type = ""
            instance.save(update_fields=[
                "image_data", "image_name", "image_content_type", "updated_at",
            ])
        elif uploaded is not None:
            instance.set_image(uploaded)
            instance.save(update_fields=[
                "image_data", "image_name", "image_content_type", "updated_at",
            ])
        return instance


class FAQImportSerializer(serializers.Serializer):
    file = serializers.FileField()


class ArticleImportSerializer(serializers.Serializer):
    file = serializers.FileField()


class ChatConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatConversation
        fields = [
            "id", "channel", "external_user_id", "flow_state", "last_question",
            "status", "messages", "escalation_reason", "advisor_question",
            "escalated_at", "created_at", "updated_at",
        ]
        read_only_fields = fields
