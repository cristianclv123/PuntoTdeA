from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0006_chatconversation_case_conversation'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='faq',
            name='image',
        ),
        migrations.AddField(
            model_name='faq',
            name='image_content_type',
            field=models.CharField(blank=True, max_length=100, verbose_name='Tipo de contenido de la imagen'),
        ),
        migrations.AddField(
            model_name='faq',
            name='image_data',
            field=models.BinaryField(blank=True, null=True, verbose_name='Imagen (bytes)'),
        ),
        migrations.AddField(
            model_name='faq',
            name='image_name',
            field=models.CharField(blank=True, max_length=255, verbose_name='Nombre del archivo'),
        ),
    ]
