"""Convierte ``MessageTemplate`` en borradores locales y desliga la campaña.

Antes, ``MessageTemplate`` replicaba las plantillas de Meta (estado, idioma,
id de Meta...) y la campaña dependía de esa fila vía ForeignKey. Ahora la base
local solo guarda borradores y la lista de plantillas sale de Meta. La campaña
conserva un snapshot de la plantilla elegida para poder enviarla sin FK.

La copia de datos se hace antes de eliminar el ForeignKey y las columnas del
espejo de Meta, para no perder las campañas existentes.
"""

from django.db import migrations, models


def copy_campaign_templates(apps, schema_editor):
    """Vuelca la plantilla enlazada en los campos snapshot de la campaña."""
    Campaign = apps.get_model("communications", "Campaign")
    for campaign in Campaign.objects.select_related("template").all():
        template = campaign.template
        if template is None:
            continue
        campaign.template_meta_id = template.meta_template_id or ""
        campaign.template_name = template.meta_template_name or ""
        campaign.template_language = template.language or "es_CO"
        campaign.template_snapshot = {
            "category": template.category,
            "body_text": template.body_text,
            "variable_types": template.variable_types or {},
            "header_type": template.header_type,
            "header_media_url": template.header_media_url,
            "buttons": template.buttons or [],
        }
        campaign.save(
            update_fields=[
                "template_meta_id",
                "template_name",
                "template_language",
                "template_snapshot",
            ]
        )


def noop(apps, schema_editor):
    """No se puede reconstruir el ForeignKey: el borrador pudo eliminarse."""


class Migration(migrations.Migration):

    dependencies = [
        ("communications", "0005_messagetemplate_meta_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="template_meta_id",
            field=models.CharField(
                blank=True, max_length=64, verbose_name="ID de la plantilla en Meta"
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="template_name",
            field=models.CharField(
                blank=True, max_length=150, verbose_name="Nombre de la plantilla en Meta"
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="template_language",
            field=models.CharField(
                default="es_CO", max_length=10, verbose_name="Idioma de la plantilla"
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="template_snapshot",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Cuerpo, variables y encabezado de la plantilla al crear la campaña.",
                verbose_name="Copia de la plantilla",
            ),
        ),
        migrations.RunPython(copy_campaign_templates, noop),
        migrations.RemoveField(
            model_name="campaign",
            name="template",
        ),
        migrations.RemoveField(
            model_name="messagetemplate",
            name="meta_template_name",
        ),
        migrations.RemoveField(
            model_name="messagetemplate",
            name="language",
        ),
        migrations.RemoveField(
            model_name="messagetemplate",
            name="status",
        ),
        migrations.RemoveField(
            model_name="messagetemplate",
            name="meta_template_id",
        ),
        migrations.RemoveField(
            model_name="messagetemplate",
            name="meta_status",
        ),
        migrations.RemoveField(
            model_name="messagetemplate",
            name="meta_rejection_reason",
        ),
        migrations.RemoveField(
            model_name="messagetemplate",
            name="meta_synced_at",
        ),
        migrations.AlterModelOptions(
            name="messagetemplate",
            options={
                "ordering": ["name"],
                "verbose_name": "borrador de plantilla",
                "verbose_name_plural": "borradores de plantilla",
            },
        ),
    ]
