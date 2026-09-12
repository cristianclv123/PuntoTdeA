from django.contrib import admin

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
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "document_number",
        "email",
        "phone",
        "academic_program",
        "semester",
    )
    search_fields = ("full_name", "document_number", "email", "phone")


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)


class CaseCommentInline(admin.TabularInline):
    model = CaseComment
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
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
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "direction", "external_id", "sent_at")
    list_filter = ("direction",)
    search_fields = ("body", "external_id")


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ("id", "message", "original_name", "kind", "size_bytes", "created_at")
    list_filter = ("kind",)
    search_fields = ("original_name",)


@admin.register(CaseComment)
class CaseCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "author", "created_at")
    search_fields = ("body", "conversation__ticket_number")


@admin.register(ReplyTemplate)
class ReplyTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "created_by", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("title", "body")
