from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Module(models.TextChoices):
        CASES = "cases", "Bandeja"
        COMMUNICATIONS = "communications", "Campañas"
        KNOWLEDGE = "knowledge", "Conocimiento"
        ANNOUNCEMENTS = "announcements", "Avisos"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Level(models.TextChoices):
        INFO = "info", "Info"
        SUCCESS = "success", "Éxito"
        WARNING = "warning", "Alerta"
        DANGER = "danger", "Error"

    module = models.CharField(max_length=32, choices=Module.choices, db_index=True)
    event = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=255, blank=True)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emitted_notifications",
    )
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class NotificationRead(models.Model):
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="reads",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_reads",
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "user"],
                name="notifications_read_unique_user",
            )
        ]
