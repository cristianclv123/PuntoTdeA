from django.db import models


class Announcement(models.Model):
    title = models.CharField(max_length=200, verbose_name="Título")
    content = models.TextField(verbose_name="Contenido")
    image = models.ImageField(upload_to='announcements/', blank=True, null=True, verbose_name="Imagen")
    is_urgent = models.BooleanField(default=False, verbose_name="¿Es urgente?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    def __str__(self):
        return self.title

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
