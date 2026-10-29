from django.contrib import admin
from PuntoTdeA.module_admin import ModuleAccessModelAdmin, ModuleAccessTabularInline

from .models import (
    CaseComment,
    Channel,
    Contact,
    Conversation,
    Department,
    Message,
    MessageAttachment,
    ReplyTemplate,
)


@admin.register(Channel)
class ChannelAdmin(ModuleAccessModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Department)
class DepartmentAdmin(ModuleAccessModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Contact)
class ContactAdmin(ModuleAccessModelAdmin):
    list_display = (
        "full_name",
        "document_number",
        "email",
        "phone",
        "academic_program",
        "semester",
    )
    search_fields = ("full_name", "document_number", "email", "phone")


class MessageInline(ModuleAccessTabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)


class CaseCommentInline(ModuleAccessTabularInline):
    model = CaseComment
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(ModuleAccessModelAdmin):
    list_display = (
        "ticket_number",
        "contact",
        "channel",
        "status",
        "priority",
        "department",
        "escalated_to",
        "assigned_to",
        "last_message_at",
    )
    list_filter = ("status", "priority", "channel", "department", "assigned_to")
    search_fields = (
        "ticket_number",
        "contact__full_name",
        "external_thread_id",
        "theme",
    )
    inlines = [MessageInline, CaseCommentInline]


@admin.register(Message)
class MessageAdmin(ModuleAccessModelAdmin):
    list_display = ("id", "conversation", "direction", "external_id", "sent_at")
    list_filter = ("direction",)
    search_fields = ("body", "external_id")


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(ModuleAccessModelAdmin):
    list_display = ("id", "message", "original_name", "kind", "size_bytes", "created_at")
    list_filter = ("kind",)
    search_fields = ("original_name",)


@admin.register(CaseComment)
class CaseCommentAdmin(ModuleAccessModelAdmin):
    list_display = ("id", "conversation", "author", "created_at")
    search_fields = ("body", "conversation__ticket_number")


@admin.register(ReplyTemplate)
class ReplyTemplateAdmin(ModuleAccessModelAdmin):
    list_display = ("title", "is_active", "created_by", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("title", "body")
