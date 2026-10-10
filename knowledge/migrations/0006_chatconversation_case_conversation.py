import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('cases', '0003_conversation_claim_close_audit'),
        ('knowledge', '0005_chatconversation_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatconversation',
            name='case_conversation',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='knowledge_conversations',
                to='cases.conversation',
            ),
        ),
    ]
