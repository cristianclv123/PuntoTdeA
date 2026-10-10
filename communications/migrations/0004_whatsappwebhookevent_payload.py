from django.db import migrations, models


class Migration(migrations.Migration):
    # No depende de 0003_messagetemplate_variable_types: hacerlo rompia las
    # bases donde 0004 ya estaba aplicada (InconsistentMigrationHistory). Esa
    # migracion ahora depende de esta. Ver nota en
    # 0003_messagetemplate_variable_types.py.
    dependencies = [
        ("communications", "0003_alter_broadcastrecipient_provider_message_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="whatsappwebhookevent",
            name="payload",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Fragmento crudo del evento de Meta, para conservar el motivo de un failed.",
            ),
        ),
    ]
