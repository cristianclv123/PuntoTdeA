from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from PuntoTdeA.module_admin import ModuleAccessModelAdmin

from .models import Category, ChatConversation, FAQ, Intent, KnowledgeArticle


@admin.register(Category)
class CategoryAdmin(ModuleAccessModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('is_active',)


@admin.register(Intent)
class IntentAdmin(ModuleAccessModelAdmin):
    list_display = ('name', 'slug', 'confidence_threshold', 'is_active')
    search_fields = ('name', 'description')
    list_filter = ('is_active',)


@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(ModuleAccessModelAdmin):
    list_display = ('title', 'category', 'status', 'published', 'published_at')
    search_fields = ('title', 'summary', 'content', 'tags')
    list_filter = ('status', 'published', 'category')
    prepopulated_fields = {'slug': ('title',)}


class FAQAdminForm(forms.ModelForm):
    """Formulario del admin: recibe la imagen como archivo y la guarda como
    bytes en la BD con `set_image` (no en MEDIA_ROOT)."""

    image_upload = forms.FileField(
        required=False,
        label='Imagen',
        widget=forms.FileInput(attrs={'accept': 'image/*'}),
    )
    clear_image = forms.BooleanField(
        required=False,
        label='Eliminar imagen actual',
    )

    class Meta:
        model = FAQ
        fields = [
            'question', 'answer', 'category', 'intent', 'is_active',
            'order', 'valid_from', 'valid_until', 'image_upload', 'clear_image',
        ]

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('clear_image'):
            instance.image_data = None
            instance.image_name = ''
            instance.image_content_type = ''
        uploaded = self.cleaned_data.get('image_upload')
        if uploaded is not None:
            instance.set_image(uploaded)
        if commit:
            instance.save()
        return instance


@admin.register(FAQ)
class FAQAdmin(ModuleAccessModelAdmin):
    form = FAQAdminForm
    list_display = ('question', 'category', 'is_active', 'order', 'has_image')
    search_fields = ('question', 'answer')
    list_filter = ('is_active', 'category')
    readonly_fields = ('image_preview',)

    @admin.display(boolean=True, description='Imagen')
    def has_image(self, obj):
        return obj.has_image

    @admin.display(description='Imagen actual')
    def image_preview(self, obj):
        if not obj.has_image:
            return '—'
        url = reverse('knowledge:faq-image', args=[obj.pk])
        return format_html(
            '<img src="{}" style="max-height:140px; border-radius:6px;">', url
        )


@admin.register(ChatConversation)
class ChatConversationAdmin(ModuleAccessModelAdmin):
    list_display = ('id', 'channel', 'external_user_id', 'status', 'flow_state', 'created_at')
    search_fields = ('external_user_id', 'last_question', 'escalation_reason')
    list_filter = ('channel', 'status', 'flow_state')
    readonly_fields = ('created_at', 'updated_at', 'messages')
