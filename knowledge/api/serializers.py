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
    class Meta:
        model = FAQ
        fields = [
            "id", "question", "answer", "category", "intent",
            "is_active", "order", "valid_from", "valid_until", "image",
        ]


class ChatConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatConversation
        fields = [
            "id", "channel", "external_user_id", "flow_state", "last_question",
            "status", "messages", "escalation_reason", "advisor_question",
            "escalated_at", "created_at", "updated_at",
        ]
        read_only_fields = fields
