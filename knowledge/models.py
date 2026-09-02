from django.db import models

from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'categoria'
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    # Clave primaria implícita (id) o explícita
    codigo_barras = models.CharField(max_length=50, unique=True, db_index=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)

    # Mapeo a NUMERIC / DECIMAL en PostgreSQL para evitar errores de redondeo
    precio_compra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    precio_venta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    stock = models.IntegerField(default=0)
    stock_minimo = models.IntegerField(default=5)

    # Relación ForeignKey (Clave foránea)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='productos'
    )

    # Campos específicos útiles con PostgreSQL
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'producto'  # Nombre exacto de la tabla en PostgreSQL
        ordering = ['-creado_en']
        indexes = [
            # Índice compuesto optimizado para PostgreSQL
            models.Index(fields=['nombre', 'activo']),
        ]

    def __str__(self):
        return f"{self.nombre} - ${self.precio_venta}"
# Create your models here.
