from django.contrib import admin

<<<<<<< Updated upstream
# Register your models here.
=======
from .models import Category, ChatConversation, FAQ, Intent, KnowledgeArticle


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('is_active',)


@admin.register(Intent)
class IntentAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'confidence_threshold', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('is_active',)


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'published', 'published_at')
    search_fields = ('title', 'summary', 'content', 'tags')
    list_filter = ('status', 'published', 'category')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'is_active', 'order')
    search_fields = ('question', 'answer')
    list_filter = ('is_active', 'category')


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel', 'external_user_id', 'status', 'flow_state', 'created_at')
    search_fields = ('external_user_id', 'last_question', 'escalation_reason')
    list_filter = ('channel', 'status', 'flow_state')
    readonly_fields = ('created_at', 'updated_at', 'messages')
>>>>>>> Stashed changes
