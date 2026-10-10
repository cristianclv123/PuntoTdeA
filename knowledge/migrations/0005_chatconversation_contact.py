from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('communications', '0004_whatsappwebhookevent_payload'),
        ('knowledge', '0004_chatconversation_whatsapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation',
            name='contact',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='chat_conversations',
                to='communications.contact',
            ),
        ),
    ]
