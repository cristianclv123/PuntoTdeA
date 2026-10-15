from django.db import models


class Announcement(models.Model):
    title = models.CharField(max_length=200, verbose_name="Título")
    content = models.TextField(verbose_name="Contenido")
    # La imagen se guarda como bytes en la base de datos (no en MEDIA_ROOT):
    # en produccion (Render plan gratis) no hay disco persistente y las
    # subidas a media se pierden entre despliegues.
    image_data = models.BinaryField(
        blank=True, null=True, editable=False, verbose_name="Imagen (bytes)"
    )
    image_name = models.CharField(max_length=255, blank=True, verbose_name="Nombre del archivo")
    image_content_type = models.CharField(
        max_length=100, blank=True, verbose_name="Tipo de contenido de la imagen"
    )
    is_urgent = models.BooleanField(default=False, verbose_name="¿Es urgente?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    def __str__(self):
        return self.title

    @property
    def has_image(self) -> bool:
        """True si el aviso tiene una imagen guardada en la base de datos."""
        return bool(self.image_data)

    def set_image(self, uploaded_file) -> None:
        """Guarda un archivo subido (request.FILES) como bytes en la BD."""
        if uploaded_file is None:
            return
        self.image_data = uploaded_file.read()
        self.image_name = getattr(uploaded_file, "name", "") or "aviso.jpg"
        self.image_content_type = (
            getattr(uploaded_file, "content_type", "") or "application/octet-stream"
        )

    def get_image_bytes(self) -> bytes | None:
        """Devuelve los bytes de la imagen o None si no hay imagen."""
        if not self.image_data:
            return None
        return bytes(self.image_data)

    @property
    def is_published_in_status(self) -> bool:
        """True si el aviso ya tiene un anuncio vigente en WhatsApp (pausado o activo)."""
        return self.status_ads.filter(
            state__in=[StatusAd.State.PAUSED, StatusAd.State.ACTIVE]
        ).exists()


class StatusAd(models.Model):
    """Anuncio en WhatsApp Status asociado a un aviso (Meta Marketing API).

    Se guarda el rastro de los objetos creados en Meta para poder auditar y
    reintentar. Por defecto el anuncio queda en PAUSED (prueba, sin gastar).
    """

    class State(models.TextChoices):
        DRAFT = "draft", "Borrador"
        PAUSED = "paused", "Pausado"
        ACTIVE = "active", "Activo"
        ERROR = "error", "Error"

    id = models.BigAutoField(primary_key=True)
    announcement = models.ForeignKey(
        Announcement, on_delete=models.CASCADE, related_name="status_ads"
    )

    campaign_id = models.CharField(max_length=40, blank=True)
    ad_set_id = models.CharField(max_length=40, blank=True)
    creative_id = models.CharField(max_length=40, blank=True)
    ad_id = models.CharField(max_length=40, blank=True)
    audience_ids = models.JSONField(default=list, blank=True)
    # Segmentos de origen (ids de AudienceSegment) para poder reintentar con la
    # misma audiencia sin depender de que la lista ya se haya creado en Meta.
    segment_ids = models.JSONField(default=list, blank=True)

    daily_budget = models.BigIntegerField(default=2000000)
    countries = models.JSONField(default=list, blank=True)
    advantage_audience = models.BooleanField(default=False)

    state = models.CharField(
        max_length=10, choices=State.choices, default=State.DRAFT
    )
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"StatusAd {self.announcement_id} ({self.state})"
