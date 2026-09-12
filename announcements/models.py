from django.db import models

# Create your models here.
from django.db import models

class Announcement(models.Model):
    title = models.CharField(max_length=200, verbose_name="Título")
    content = models.TextField(verbose_name="Contenido")
    is_urgent = models.BooleanField(default=False, verbose_name="¿Es urgente?")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    def __str__(self):
        return self.title