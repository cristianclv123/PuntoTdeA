from django.contrib import admin

from notifications.models import Notification, NotificationRead


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "module", "event", "title", "level")
    list_filter = ("module", "level", "event")
    search_fields = ("title", "body")


@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ("read_at", "user", "notification")
