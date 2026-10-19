"""Reset existing PlatformFee.* `_percent` fields to the minimum bound.

The earlier consolidation defaulted to the midpoint of the range, but
the platform policy is to always advertise + charge at the minimum
until ops bumps it explicitly. This nudges every existing row down to
that floor in one shot.
"""
from django.db import migrations


def use_min(apps, schema_editor):
    PlatformFee = apps.get_model('platform_admin', 'PlatformFee')
    for fee in PlatformFee.objects.all():
        fee.customer_service_fee_percent = fee.customer_service_fee_min
        fee.merchant_commission_percent = fee.merchant_commission_min
        fee.save(update_fields=[
            'customer_service_fee_percent',
            'merchant_commission_percent',
            'updated_at',
        ])


def reverse(apps, schema_editor):
    pass  # No clean inverse — what was the prior value? Forward-only.


class Migration(migrations.Migration):

    dependencies = [
        ('platform_admin', '0005_consolidate_platform_fees'),
    ]

    operations = [
        migrations.RunPython(use_min, reverse_code=reverse),
    ]
