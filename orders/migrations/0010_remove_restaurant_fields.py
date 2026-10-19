from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_shippingaddress_type_choices'),
    ]

    operations = [
        # Remove restaurant-only fields from CartItem
        migrations.RemoveField(model_name='cartitem', name='special_instructions'),
        migrations.RemoveField(model_name='cartitem', name='selected_addons'),

        # Remove restaurant-only fields from Order
        migrations.RemoveField(model_name='order', name='estimated_prep_minutes'),
        migrations.RemoveField(model_name='order', name='scheduled_for'),
        migrations.RemoveField(model_name='order', name='table_number'),

        # Narrow fulfillment_type choices to delivery + pickup only
        migrations.AlterField(
            model_name='order',
            name='fulfillment_type',
            field=models.CharField(
                max_length=20,
                choices=[('delivery', 'Delivery'), ('pickup', 'Pickup')],
                default='delivery',
            ),
        ),

        # Remove restaurant-only fields from OrderItem
        migrations.RemoveField(model_name='orderitem', name='special_instructions'),
        migrations.RemoveField(model_name='orderitem', name='selected_addons'),
    ]
