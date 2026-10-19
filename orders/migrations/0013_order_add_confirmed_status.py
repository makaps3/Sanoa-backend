from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0012_cartitem_add_negotiation_room_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('pending', 'Pending'),
                    ('confirmed', 'Confirmed'),
                    ('processing', 'Processing'),
                    ('shipped', 'Shipped'),
                    ('delivered', 'Delivered'),
                    ('cancelled', 'Cancelled'),
                    ('refunded', 'Refunded'),
                    ('partially_refunded', 'Partially Refunded'),
                ],
                default='pending',
            ),
        ),
    ]
