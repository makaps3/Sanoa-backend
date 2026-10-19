"""
Tags each Category with the storefront mode it belongs to so the
frontend toggle (Shopping vs Restaurants) can request a different
category list per mode. Defaults to 'retail' for all existing rows
to preserve current behaviour.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_add_banner_image_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='business_category',
            field=models.CharField(
                choices=[
                    ('retail', 'Retail / Shopping'),
                    ('restaurant', 'Restaurant / Food'),
                    ('both', 'Both'),
                ],
                default='retail',
                help_text=(
                    "Which storefront mode this category belongs to. "
                    "'retail' shows in the Shopping experience, 'restaurant' "
                    "shows in the Restaurants/fast-food experience, 'both' "
                    "shows in either."
                ),
                max_length=20,
            ),
        ),
    ]
