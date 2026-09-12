from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge', '0002_category_intent_remove_producto_categoria_faq_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='faq',
            name='valid_from',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Válida desde'),
        ),
        migrations.AddField(
            model_name='faq',
            name='valid_until',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Válida hasta'),
        ),
        migrations.AddField(
            model_name='faq',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='knowledge/faqs/', verbose_name='Imagen'),
        ),
    ]