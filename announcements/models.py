from django.db import models

# Create your models here.
from django.db import models

class Announcement(models.Model):
    title = models.CharField(max_length=200, verbose_name="Título")
    content = models.TextField(verbose_name="Contenido")
    image = models.ImageField(upload_to='announcements/', blank=True, null=True, verbose_name="Imagen")
    is_urgent = models.BooleanField(default=False, verbose_name="¿Es urgente?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    def __str__(self):
        return self.title