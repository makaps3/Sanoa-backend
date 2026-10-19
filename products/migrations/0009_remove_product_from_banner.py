from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_create_banner_model'),
    ]

    operations = [
        # Remove the product FK
        migrations.RemoveField(
            model_name='banner',
            name='product',
        ),
        # Remove banner_type (no longer needed — all banners are category)
        migrations.RemoveField(
            model_name='banner',
            name='banner_type',
        ),
        # Make category non-nullable
        migrations.AlterField(
            model_name='banner',
            name='category',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='banners',
                to='products.category',
            ),
        ),
    ]
