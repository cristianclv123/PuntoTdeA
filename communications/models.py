import uuid
from django.db import models


class Contact(models.Model):
    document_number = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    academic_program = models.CharField(max_length=255, blank=True, null=True)
    semester = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=50, default="student")
    whatsapp_opt_in = models.BooleanField(default=True)
    source = models.CharField(max_length=100, default="excel_campus")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.document_number})"


class ContactEvent(models.Model):
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=50)
    channel = models.CharField(max_length=50, default="whatsapp")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AudienceSegment(models.Model):
    class SourceType(models.TextChoices):
        EXCEL_IMPORT = "excel_import", "Importación Excel"
        MANUAL = "manual", "Manual"
        FILTER = "filter", "Filtro Dinámico"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    source_type = models.CharField(
        max_length=50,
        choices=SourceType.choices,
        default=SourceType.EXCEL_IMPORT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def contact_count(self):
        return self.memberships.count()

    def __str__(self):
        return self.name


class SegmentMembership(models.Model):
    segment = models.ForeignKey(
        AudienceSegment, on_delete=models.CASCADE, related_name="memberships"
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="segment_memberships"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("segment", "contact")


class MessageTemplate(models.Model):
    name = models.CharField(max_length=255)
    meta_template_name = models.CharField(max_length=255)
    category = models.CharField(max_length=50, default="UTILITY")
    status = models.CharField(max_length=50, default="APPROVED")
    param_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        SCHEDULED = "SCHEDULED", "Programada"
        SENDING = "SENDING", "Enviando"
        SENT = "SENT", "Enviada"
        FAILED = "FAILED", "Fallida"

    name = models.CharField(max_length=255)
    template = models.ForeignKey(
        MessageTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    segment = models.ForeignKey(
        AudienceSegment, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.DRAFT
    )
    channel = models.CharField(max_length=50, default="whatsapp")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)
    read_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BroadcastRecipient(models.Model):
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="recipients"
    )
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    phone_snapshot = models.CharField(max_length=50)
    status = models.CharField(max_length=50, default="PENDING")
    provider = models.CharField(max_length=50, default="meta")
    provider_message_id = models.CharField(
        max_length=255, null=True, blank=True
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.campaign.name} -> {self.phone_snapshot}"