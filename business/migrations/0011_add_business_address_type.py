from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0010_create_missing_vendor_profiles'),
    ]

    operations = [
        migrations.AlterField(
            model_name='address',
            name='address_type',
            field=models.CharField(
                choices=[
                    ('billing', 'Billing Address'),
                    ('shipping', 'Shipping Address'),
                    ('both', 'Billing & Shipping'),
                    ('business', 'Business Address'),
                ],
                default='both',
                max_length=10,
            ),
        ),
    ]
