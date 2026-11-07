from django.db import migrations, models
from django.db.models import F


def backfill_last_user_activity(apps, schema_editor):
    ChatConversation = apps.get_model('knowledge', 'ChatConversation')
    ChatConversation.objects.filter(last_user_activity_at__isnull=True).update(
        last_user_activity_at=F('updated_at')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0008_alter_knowledgearticle_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation',
            name='last_user_activity_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Última actividad del usuario',
            ),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='inactivity_warned_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Aviso de inactividad enviado',
            ),
        ),
        migrations.RunPython(
            backfill_last_user_activity,
            migrations.RunPython.noop,
        ),
    ]
