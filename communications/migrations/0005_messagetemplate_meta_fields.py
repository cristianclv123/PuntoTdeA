from django.db import migrations, models


class Migration(migrations.Migration):
    # Depende del único nodo hoja del historial: 0003_messagetemplate_variable_types
    # (que a su vez depende de 0004). Ver la nota de esa migración antes de tocar
    # el orden.
    dependencies = [
        ("communications", "0003_messagetemplate_variable_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="messagetemplate",
            name="meta_template_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="ID que devuelve Meta al crear la plantilla.",
                max_length=64,
                verbose_name="ID en Meta",
            ),
        ),
        migrations.AddField(
            model_name="messagetemplate",
            name="meta_status",
            field=models.CharField(
                blank=True,
                help_text="Valor crudo de Meta: PENDING, APPROVED, REJECTED, PAUSED...",
                max_length=32,
                verbose_name="Estado en Meta",
            ),
        ),
        migrations.AddField(
            model_name="messagetemplate",
            name="meta_rejection_reason",
            field=models.TextField(
                blank=True, verbose_name="Motivo de rechazo de Meta"
            ),
        ),
        migrations.AddField(
            model_name="messagetemplate",
            name="meta_synced_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Última consulta a Meta"
            ),
        ),
    ]
