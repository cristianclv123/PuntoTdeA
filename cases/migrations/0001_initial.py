# Generated manually for HU-01

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def seed_channels(apps, schema_editor):
    Channel = apps.get_model("cases", "Channel")
    defaults = [
        ("whatsapp", "WhatsApp"),
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("web", "Web"),
    ]
    for code, name in defaults:
        Channel.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )


def unseed_channels(apps, schema_editor):
    Channel = apps.get_model("cases", "Channel")
    Channel.objects.filter(
        code__in=["whatsapp", "facebook", "instagram", "web"]
    ).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Channel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(choices=[("whatsapp", "WhatsApp"), ("facebook", "Facebook"), ("instagram", "Instagram"), ("web", "Web")], max_length=32, unique=True)),
                ("name", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Contact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=200)),
                ("document_number", models.CharField(max_length=32, unique=True)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(max_length=32)),
                ("academic_program", models.CharField(max_length=200)),
                ("semester", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["full_name"],
            },
        ),
        migrations.CreateModel(
            name="Conversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_thread_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("status", models.CharField(choices=[("pendiente", "Pendiente"), ("en_gestion", "En gestión"), ("escalado", "Escalado"), ("atendido", "Atendido"), ("cerrado", "Cerrado")], db_index=True, default="pendiente", max_length=32)),
                ("theme", models.CharField(blank=True, default="", max_length=120)),
                ("last_message_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_conversations", to=settings.AUTH_USER_MODEL)),
                ("channel", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="conversations", to="cases.channel")),
                ("contact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="conversations", to="cases.contact")),
            ],
            options={
                "ordering": ["-last_message_at"],
            },
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("direction", models.CharField(choices=[("inbound", "Entrante"), ("outbound", "Saliente")], max_length=16)),
                ("body", models.TextField()),
                ("external_id", models.CharField(blank=True, db_index=True, max_length=255)),
                ("sent_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="cases.conversation")),
            ],
            options={
                "ordering": ["sent_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(fields=["channel", "external_thread_id"], name="cases_conve_channel_9f0d2a_idx"),
        ),
        migrations.AddConstraint(
            model_name="message",
            constraint=models.UniqueConstraint(
                condition=~models.Q(external_id=""),
                fields=("conversation", "external_id"),
                name="uniq_message_external_id_per_conversation",
            ),
        ),
        migrations.RunPython(seed_channels, unseed_channels),
    ]
