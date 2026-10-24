import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("module", models.CharField(choices=[("cases", "Bandeja"), ("communications", "Campañas"), ("knowledge", "Conocimiento"), ("announcements", "Avisos"), ("whatsapp", "WhatsApp")], db_index=True, max_length=32)),
                ("event", models.CharField(db_index=True, max_length=64)),
                ("title", models.CharField(max_length=160)),
                ("body", models.TextField(blank=True)),
                ("url", models.CharField(blank=True, max_length=255)),
                ("level", models.CharField(choices=[("info", "Info"), ("success", "Éxito"), ("warning", "Alerta"), ("danger", "Error")], default="info", max_length=16)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="emitted_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="NotificationRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reads", to="notifications.notification")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_reads", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="notificationread",
            constraint=models.UniqueConstraint(fields=("notification", "user"), name="notifications_read_unique_user"),
        ),
    ]
