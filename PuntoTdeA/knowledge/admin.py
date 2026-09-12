from django.contrib import admin

from .models import Category, FAQ, Intent, KnowledgeArticle


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Intent)
class IntentAdmin(admin.ModelAdmin):
    list_display = ('name', 'confidence_threshold', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'published', 'published_at')
    list_filter = ('status', 'published', 'category')
    search_fields = ('title', 'summary', 'content')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'published_at')


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'is_active', 'valid_from', 'valid_until', 'order')
    list_filter = ('is_active', 'category', 'valid_from', 'valid_until')
    search_fields = ('question', 'answer')
    fields = ('question', 'answer', 'category', 'intent', 'is_active', 'order', 'valid_from', 'valid_until', 'image')
