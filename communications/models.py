import uuid

from django.db import models
from django.utils import timezone


class Contact(models.Model):
    """Perfil unificado de contacto (CDP).

    Campos obligatorios alineados con T-01.3 del documento de requerimientos:
    Nombre completo, Documento, Correo, Teléfono, Programa académico, Semestre.
    """

    class Role(models.TextChoices):
        ASPIRANTE = "aspirante", "Aspirante"
        ESTUDIANTE = "estudiante", "Estudiante"
        EGRESADO = "egresado", "Egresado"
        OTRO = "otro", "Otro"

    class OptInStatus(models.TextChoices):
        SUSCRITO = "suscrito", "Suscrito"
        NO_CONTACTADO = "no_contactado", "No contactado"
        BAJA = "baja", "Dado de baja"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    full_name = models.CharField("Nombre completo", max_length=180)
    document_number = models.CharField(
        "Número de documento", max_length=30, unique=True, db_index=True
    )
    email = models.EmailField("Correo electrónico", blank=True)
    phone = models.CharField(
        "Teléfono (WhatsApp)", max_length=20, db_index=True,
        help_text="Formato E.164, ej. +573001234567",
    )
    academic_program = models.CharField("Programa académico", max_length=150, blank=True)
    semester = models.CharField("Semestre", max_length=10, blank=True)

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OTRO)
    whatsapp_opt_in = models.CharField(
        max_length=20, choices=OptInStatus.choices, default=OptInStatus.NO_CONTACTADO
    )

    # Atributos dinámicos adicionales sin necesidad de migraciones (estilo CDP).
    attributes = models.JSONField(default=dict, blank=True)

    source = models.CharField(
        "Origen del registro", max_length=50, blank=True,
        help_text="ej. excel_campus, formulario_web, importacion_manual",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone"]),
            models.Index(fields=["document_number"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"


class ContactEvent(models.Model):
    """Línea de tiempo de interacciones de un contacto (RF-12 / CDP timeline)."""

    class EventType(models.TextChoices):
        MESSAGE_SENT = "message_sent", "Mensaje enviado"
        MESSAGE_DELIVERED = "message_delivered", "Mensaje entregado"
        MESSAGE_READ = "message_read", "Mensaje leído"
        MESSAGE_FAILED = "message_failed", "Mensaje fallido"
        MESSAGE_REPLIED = "message_replied", "Respuesta recibida"
        OPTED_OUT = "opted_out", "Se dio de baja"
        SEGMENT_ADDED = "segment_added", "Agregado a audiencia"
        NOTE = "note", "Nota interna"

    id = models.BigAutoField(primary_key=True)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    channel = models.CharField(max_length=20, default="whatsapp")
    payload = models.JSONField(default=dict, blank=True)

    # Referencias opcionales para trazar el evento hasta su origen.
    campaign = models.ForeignKey(
        "Campaign", on_delete=models.SET_NULL, null=True, blank=True, related_name="events"
    )
    broadcast_recipient = models.ForeignKey(
        "BroadcastRecipient", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="events",
    )

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["contact", "-created_at"])]

    def __str__(self):
        return f"{self.contact_id} · {self.get_event_type_display()}"


class MessageTemplate(models.Model):
    """Plantilla aprobada por Meta para envíos de WhatsApp (HU-06 / T-06.2)."""

    class Category(models.TextChoices):
        MARKETING = "marketing", "Marketing"
        UTILITY = "utility", "Utilidad"
        AUTHENTICATION = "authentication", "Autenticación"

    class HeaderType(models.TextChoices):
        NONE = "none", "Sin encabezado"
        IMAGE = "image", "Imagen"
        VIDEO = "video", "Video"
        DOCUMENT = "document", "Documento (PDF)"

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador local"
        PENDING = "pending", "Pendiente de aprobación"
        APPROVED = "approved", "Aprobada"
        REJECTED = "rejected", "Rechazada"

    id = models.BigAutoField(primary_key=True)
    name = models.CharField("Nombre interno", max_length=150)
    meta_template_name = models.CharField(
        "Nombre en Meta Business Manager", max_length=150, unique=True
    )
    language = models.CharField(max_length=10, default="es_CO")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.UTILITY)

    body_text = models.TextField(
        help_text="Usa {{1}}, {{2}}, etc. para parámetros dinámicos."
    )
    header_type = models.CharField(max_length=10, choices=HeaderType.choices, default=HeaderType.NONE)
    header_media_url = models.URLField(blank=True)
    buttons = models.JSONField(
        default=list, blank=True,
        help_text='Lista de botones URL, ej. [{"text": "Ver más", "url": "https://..."}]',
    )

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def param_count(self) -> int:
        import re
        return len(set(re.findall(r"\{\{(\d+)\}\}", self.body_text)))


class AudienceSegment(models.Model):
    """Segmento de audiencia (HU-06). Puede poblarse por importación Excel
    o, más adelante, por reglas dinámicas contra el Backend CRUD."""

    class SourceType(models.TextChoices):
        EXCEL_IMPORT = "excel_import", "Importación Excel (Campus)"
        MANUAL = "manual", "Selección manual"
        DYNAMIC = "dynamic", "Regla dinámica"

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    source_type = models.CharField(
        max_length=20, choices=SourceType.choices, default=SourceType.EXCEL_IMPORT
    )
    filter_rules = models.JSONField(
        default=dict, blank=True,
        help_text="Solo aplica cuando source_type='dynamic'.",
    )
    contacts = models.ManyToManyField(
        Contact, through="SegmentMembership", related_name="segments", blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def contact_count(self) -> int:
        return self.contacts.count()


class SegmentMembership(models.Model):
    id = models.BigAutoField(primary_key=True)
    segment = models.ForeignKey(AudienceSegment, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["segment", "contact"], name="unique_segment_contact"
            )
        ]


class Campaign(models.Model):
    """Campaña de mensajería masiva por WhatsApp (HU-06 / HU-07)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        SCHEDULED = "scheduled", "Programada"
        SENDING = "sending", "Enviando"
        SENT = "sent", "Enviada"
        PAUSED = "paused", "Pausada"
        CANCELLED = "cancelled", "Cancelada"
        FAILED = "failed", "Fallida"

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=150)
    channel = models.CharField(max_length=20, default="whatsapp", editable=False)

    template = models.ForeignKey(
        MessageTemplate, on_delete=models.PROTECT, related_name="campaigns"
    )
    segment = models.ForeignKey(
        AudienceSegment, on_delete=models.PROTECT, related_name="campaigns"
    )
    # Valores por defecto para los parámetros {{1}}, {{2}}... de la plantilla.
    # Puede sobreescribirse por destinatario en BroadcastRecipient.params.
    default_params = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    scheduled_at = models.DateTimeField(null=True, blank=True)

    rate_limit_per_minute = models.PositiveIntegerField(
        default=60, help_text="Límite de envíos por minuto (Rate Limiting Meta API)."
    )

    created_by = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    # --- métricas agregadas, usadas por la vista de listado ---
    def _count(self, status):
        return self.recipients.filter(status=status).count()

    @property
    def total_recipients(self) -> int:
        return self.recipients.count()

    @property
    def sent_count(self) -> int:
        return self.recipients.exclude(
            status__in=[
                BroadcastRecipient.Status.PENDING,
                BroadcastRecipient.Status.OPTED_OUT,
            ]
        ).count()

    @property
    def delivered_count(self) -> int:
        return self._count(BroadcastRecipient.Status.DELIVERED) + self._count(
            BroadcastRecipient.Status.READ
        )

    @property
    def read_count(self) -> int:
        return self._count(BroadcastRecipient.Status.READ)

    @property
    def failed_count(self) -> int:
        return self._count(BroadcastRecipient.Status.FAILED)


class BroadcastRecipient(models.Model):
    """Registro de envío individual de una campaña a un contacto."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        QUEUED = "queued", "En cola"
        SENT = "sent", "Enviado"
        DELIVERED = "delivered", "Entregado"
        READ = "read", "Leído"
        FAILED = "failed", "Fallido"
        OPTED_OUT = "opted_out", "Excluido (baja)"

    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="recipients")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="broadcasts")

    # Snapshot del teléfono al momento del envío (por si el contacto lo cambia después).
    phone_snapshot = models.CharField(max_length=20)
    params = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=20, blank=True, help_text="twilio | meta | mock")
    provider_message_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    queued_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "contact"], name="unique_campaign_contact"
            )
        ]
        indexes = [models.Index(fields=["campaign", "status"])]

    def __str__(self):
        return f"{self.campaign_id} → {self.phone_snapshot} ({self.status})"