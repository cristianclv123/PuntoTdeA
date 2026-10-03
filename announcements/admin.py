from django.contrib import admin

from .models import Announcement, StatusAd


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_urgent", "created_at")
    list_filter = ("is_urgent",)
    search_fields = ("title", "content")


@admin.register(StatusAd)
class StatusAdAdmin(admin.ModelAdmin):
    list_display = ("announcement", "state", "ad_id", "created_at")
    list_filter = ("state",)
    search_fields = ("announcement__title", "ad_id", "campaign_id")
    readonly_fields = (
        "campaign_id",
        "ad_set_id",
        "creative_id",
        "ad_id",
        "audience_ids",
        "segment_ids",
        "error",
        "created_at",
        "updated_at",
    )
