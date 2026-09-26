from django.contrib import admin

from .models import (
    AudienceSegment,
    BroadcastRecipient,
    Campaign,
    Contact,
    ContactEvent,
    MessageTemplate,
    SegmentMembership,
)
from .services import campaign_service


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "document_number", "role", "whatsapp_opt_in", "created_at")
    search_fields = ("full_name", "phone", "document_number", "email")
    list_filter = ("role", "whatsapp_opt_in", "source")


@admin.register(ContactEvent)
class ContactEventAdmin(admin.ModelAdmin):
    list_display = ("contact", "event_type", "channel", "created_at")
    list_filter = ("event_type", "channel")
    autocomplete_fields = ("contact",)


class SegmentMembershipInline(admin.TabularInline):
    model = SegmentMembership
    extra = 0
    autocomplete_fields = ("contact",)


@admin.register(AudienceSegment)
class AudienceSegmentAdmin(admin.ModelAdmin):
    list_display = ("name", "source_type", "contact_count", "created_at")
    inlines = [SegmentMembershipInline]


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "meta_template_name", "category", "status", "param_count")
    list_filter = ("category", "status")


class BroadcastRecipientInline(admin.TabularInline):
    model = BroadcastRecipient
    extra = 0
    readonly_fields = ("contact", "phone_snapshot", "status", "provider_message_id", "sent_at", "delivered_at", "read_at")
    can_delete = False


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "template", "segment", "status", "scheduled_at", "sent_count", "delivered_count", "read_count")
    list_filter = ("status", "channel")
    inlines = [BroadcastRecipientInline]
    actions = ["enviar_campana_seleccionada"]

    @admin.action(description="📤 Enviar campaña(s) seleccionada(s) ahora (mock)")
    def enviar_campana_seleccionada(self, request, queryset):
        enviadas = 0
        for campaign in queryset:
            if campaign.status not in (Campaign.Status.DRAFT, Campaign.Status.SCHEDULED):
                self.message_user(
                    request,
                    f"'{campaign.name}' está en estado '{campaign.status}', no se puede reenviar.",
                    level="warning",
                )
                continue
            campaign_service.send_campaign(campaign)
            enviadas += 1
        if enviadas:
            self.message_user(request, f"{enviadas} campaña(s) enviada(s) correctamente.")


@admin.register(BroadcastRecipient)
class BroadcastRecipientAdmin(admin.ModelAdmin):
    list_display = ("campaign", "contact", "phone_snapshot", "status", "provider", "sent_at")
    list_filter = ("status", "provider")
    search_fields = ("phone_snapshot",)