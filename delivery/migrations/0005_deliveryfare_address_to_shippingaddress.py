"""Re-point DeliveryFare.address from business.Address (int PK) to
orders.ShippingAddress (UUID PK).

The old int address_id cannot be translated to the new UUID key in a
zero-data-loss way, and delivery fares are ephemeral quotes. So this
migration clears the table before swapping the FK target.
"""
import django.db.models.deletion
from django.db import migrations, models

from core.migration_ops import AlterForeignKeyToUUID


def wipe_delivery_fares(apps, schema_editor):
    DeliveryFare = apps.get_model('delivery', 'DeliveryFare')
    DeliveryFare.objects.all().delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0004_collapse_deliveryfare_vendor'),
        ('orders', '0008_shippingaddress_and_order_fk'),
        ('business', '0012_address_to_vendorprofile'),
    ]

    operations = [
        migrations.RunPython(wipe_delivery_fares, reverse_code=noop),
        AlterForeignKeyToUUID(
            model_name='deliveryfare',
            name='address',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='delivery_fares',
                to='orders.shippingaddress',
            ),
        ),
    ]
