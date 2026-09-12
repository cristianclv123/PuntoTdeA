# Generated manually for chat attachments and reply templates

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


DEFAULT_TEMPLATES = [
    (
        "Saludo inicial",
        "Hola, gracias por contactar a Punto TdeA. ¿En qué podemos ayudarte hoy?",
    ),
    (
        "Solicitud de datos",
        "Para continuar con tu solicitud, por favor confirma tu nombre completo, número de documento y programa académico.",
    ),
    (
        "Cierre de caso",
        "Hemos gestionado tu solicitud. Si necesitas algo más, vuelve a escribirnos. ¡Que tengas un buen día!",
    ),
    (
        "Derivación a dependencia",
        "Tu caso será escalado a la dependencia correspondiente. Te confirmaremos cuando tengamos una respuesta.",
    ),
]


def seed_templates(apps, schema_editor):
    ReplyTemplate = apps.get_model("cases", "ReplyTemplate")
    for title, body in DEFAULT_TEMPLATES:
        ReplyTemplate.objects.update_or_create(
            title=title,
            defaults={"body": body, "is_active": True},
        )


def unseed_templates(apps, schema_editor):
    ReplyTemplate = apps.get_model("cases", "ReplyTemplate")
    ReplyTemplate.objects.filter(title__in=[t for t, _ in DEFAULT_TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0002_case_actions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MessageAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="cases/attachments/%Y/%m/")),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=120)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("image", "Imagen"),
                            ("video", "Video"),
                            ("office", "Ofimática"),
                        ],
                        max_length=16,
                    ),
                ),
                ("size_bytes", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="cases.message",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="ReplyTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("body", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reply_templates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["title"],
            },
        ),
        migrations.RunPython(seed_templates, unseed_templates),
    ]
