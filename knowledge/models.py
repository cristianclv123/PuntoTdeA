from decimal import Decimal
import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.db import models
from django.utils.text import slugify

VectorField = None
if getattr(settings, 'KNOWLEDGE_ENABLE_VECTOR', False):
    try:
        from pgvector.django import VectorField  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - optional dependency for PostgreSQL vector support
        pass


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


class BaseKnowledgeModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(BaseKnowledgeModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.name)


class Intent(BaseKnowledgeModel):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    confidence_threshold = models.FloatField(
        default=0.75,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.name)


class KnowledgeArticle(BaseKnowledgeModel):
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('published', 'Publicado'),
        ('archived', 'Archivado'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.TextField(blank=True)
    content = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='articles')
    intent = models.ForeignKey(Intent, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    embedding = models.JSONField(default=list, blank=True)
    if VectorField is not None:
        embedding_vector = VectorField(dimensions=1536, null=True, blank=True)

    class Meta:
        ordering = ['-published_at', '-created_at']
        indexes = [
            models.Index(fields=['title', 'status']),
            models.Index(fields=['category', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.published and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.published or self.status == 'published'

    @property
    def indexable_text(self):
        return ' '.join(filter(None, [self.title, self.summary, self.content]))

    def __str__(self) -> str:
        return str(self.title)


class FAQ(BaseKnowledgeModel):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='faqs')
    intent = models.ForeignKey(Intent, on_delete=models.SET_NULL, null=True, blank=True, related_name='faqs')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True, verbose_name='Válida desde')
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name='Válida hasta')
    image = models.ImageField(upload_to='knowledge/faqs/', null=True, blank=True, verbose_name='Imagen')

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self) -> str:
        return str(self.question)


class ChatConversation(BaseKnowledgeModel):
    STATUS_ACTIVE = 'active'
    STATUS_ENDED = 'ended'
    STATUS_PENDING = 'pending'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Activa'),
        (STATUS_ENDED, 'Finalizada'),
        (STATUS_PENDING, 'Pendiente de asesor'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel = models.CharField(max_length=30, default='webchat', db_index=True)
    external_user_id = models.CharField(max_length=120, blank=True, db_index=True)
    flow_state = models.CharField(max_length=40, default='waiting_question')
    last_question = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    messages = models.JSONField(default=list, blank=True)
    escalation_reason = models.TextField(blank=True)
    advisor_question = models.TextField(blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Conversación del chatbot'
        verbose_name_plural = 'Conversaciones del chatbot'

    def __str__(self) -> str:
        return f'Conversación {self.pk}'
