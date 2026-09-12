# Generated manually for case actions metadata

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


DEPARTMENTS = [
    ("registro_academico", "Registro Académico"),
    ("admisiones", "Admisiones"),
    ("bienestar", "Bienestar Universitario"),
    ("financiera", "Financiera"),
    ("ti", "Tecnología (TI)"),
    ("comunicaciones", "Comunicaciones"),
    ("rectoria", "Rectoría / Secretaría General"),
    ("biblioteca", "Biblioteca"),
]


def seed_departments(apps, schema_editor):
    Department = apps.get_model("cases", "Department")
    for code, name in DEPARTMENTS:
        Department.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )


def unseed_departments(apps, schema_editor):
    Department = apps.get_model("cases", "Department")
    Department.objects.filter(code__in=[c for c, _ in DEPARTMENTS]).delete()


def migrate_statuses_and_tickets(apps, schema_editor):
    Conversation = apps.get_model("cases", "Conversation")
    Conversation.objects.filter(status="atendido").update(status="completado")
    Conversation.objects.filter(status="en_gestion").update(status="pendiente")
    for conv in Conversation.objects.filter(models.Q(ticket_number__isnull=True) | models.Q(ticket_number="")).iterator():
        Conversation.objects.filter(pk=conv.pk).update(ticket_number=f"TDEA-{conv.pk:06d}")


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="conversation",
            name="ticket_number",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="conversation",
            name="priority",
            field=models.CharField(
                choices=[
                    ("baja", "Baja"),
                    ("media", "Media"),
                    ("alta", "Alta"),
                    ("urgente", "Urgente"),
                ],
                db_index=True,
                default="media",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conversations",
                to="cases.department",
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="escalated_to",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="escalated_conversations",
                to="cases.department",
            ),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="status",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("completado", "Completado"),
                    ("rechazado", "Rechazado"),
                    ("escalado", "Escalado"),
                    ("cerrado", "Cerrado"),
                ],
                db_index=True,
                default="pendiente",
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="CaseComment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="case_comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="cases.conversation",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(seed_departments, unseed_departments),
        migrations.RunPython(migrate_statuses_and_tickets, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="conversation",
            name="ticket_number",
            field=models.CharField(blank=True, max_length=32, null=True, unique=True),
        ),
    ]
