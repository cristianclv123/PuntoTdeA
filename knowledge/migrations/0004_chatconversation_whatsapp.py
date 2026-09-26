import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge', '0003_chatconversation'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation',
            name='channel',
            field=models.CharField(db_index=True, default='webchat', max_length=30),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='external_user_id',
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='flow_state',
            field=models.CharField(default='waiting_question', max_length=40),
        ),
        migrations.AddField(
            model_name='chatconversation',
            name='last_question',
            field=models.TextField(blank=True),
        ),
    ]