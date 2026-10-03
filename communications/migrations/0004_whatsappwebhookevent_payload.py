from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
    ("communications", "0003_alter_broadcastrecipient_provider_message_id_and_more"),
    ("communications", "0003_messagetemplate_variable_types"),
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
