"""Rename ShippingAddress.address_type choices from home/work/other to
shipping/billing/both, matching the rest of the codebase.

Existing rows (created by migration 0008 when customer addresses were
copied out of business.Address) get remapped: any legacy value becomes
'shipping', which is the most useful default for an orders-side address.
"""
from django.db import migrations, models


def remap_address_types(apps, schema_editor):
    ShippingAddress = apps.get_model('orders', 'ShippingAddress')
    REMAP = {
        'home': 'shipping',
        'work': 'shipping',
        'other': 'shipping',
    }
    for old, new in REMAP.items():
        ShippingAddress.objects.filter(address_type=old).update(address_type=new)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_shippingaddress_and_order_fk'),
    ]

    operations = [
        migrations.RunPython(remap_address_types, reverse_code=noop),
        migrations.AlterField(
            model_name='shippingaddress',
            name='address_type',
            field=models.CharField(
                choices=[
                    ('shipping', 'Shipping Address'),
                    ('billing', 'Billing Address'),
                    ('both', 'Billing & Shipping'),
                ],
                default='shipping',
                max_length=10,
            ),
        ),
    ]
