from django.conf import settings
from django.db import models
from django.utils import timezone


class Channel(models.Model):
    class Code(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"
        WEB = "web", "Web"

    code = models.CharField(max_length=32, choices=Code.choices, unique=True)
    name = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Contact(models.Model):
    full_name = models.CharField(max_length=200)
    document_number = models.CharField(max_length=32, unique=True)
    email = models.EmailField()
    phone = models.CharField(max_length=32)
    academic_program = models.CharField(max_length=200)
    semester = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    @property
    def initials(self):
        parts = [p for p in self.full_name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f"{parts[0][0]}{parts[-1][0]}".upper()


class Conversation(models.Model):
    class Status(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        COMPLETADO = "completado", "Completado"
        RECHAZADO = "rechazado", "Rechazado"
        ESCALADO = "escalado", "Escalado"
        CERRADO = "cerrado", "Cerrado"

    class Priority(models.TextChoices):
        BAJA = "baja", "Baja"
        MEDIA = "media", "Media"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"

    channel = models.ForeignKey(
        Channel,
        on_delete=models.PROTECT,
        related_name="conversations",
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name="conversations",
    )
    external_thread_id = models.CharField(max_length=255, blank=True, db_index=True)
    ticket_number = models.CharField(max_length=32, unique=True, blank=True, null=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDIENTE,
        db_index=True,
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.MEDIA,
        db_index=True,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    escalated_to = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalated_conversations",
    )
    theme = models.CharField(max_length=120, blank=True, default="")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversations",
    )
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_message_at"]
        indexes = [
            models.Index(fields=["channel", "external_thread_id"]),
        ]

    def __str__(self):
        return self.ticket_number or f"{self.contact.full_name} · {self.channel.code}"

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.ticket_number:
            self.ticket_number = f"TDEA-{self.pk:06d}"
            Conversation.objects.filter(pk=self.pk).update(ticket_number=self.ticket_number)
            self.refresh_from_db(fields=["ticket_number"])


class Message(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "inbound", "Entrante"
        OUTBOUND = "outbound", "Saliente"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    direction = models.CharField(max_length=16, choices=Direction.choices)
    body = models.TextField()
    external_id = models.CharField(max_length=255, blank=True, db_index=True)
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sent_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "external_id"],
                condition=~models.Q(external_id=""),
                name="uniq_message_external_id_per_conversation",
            ),
        ]

    def __str__(self):
        return f"{self.direction}: {self.body[:40]}"


class CaseComment(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="case_comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment #{self.pk} on {self.conversation_id}"


class MessageAttachment(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Imagen"
        VIDEO = "video", "Video"
        OFFICE = "office", "Ofimática"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="cases/attachments/%Y/%m/")
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, blank=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    size_bytes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.original_name


class ReplyTemplate(models.Model):
    title = models.CharField(max_length=120)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reply_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
