"""Consolidate PlatformFee rows to the two-category schema.

Old rows used `restaurant_delivery`, `grocery_delivery`, and `retail`.
The new scheme keeps only `retail` (which now covers grocery + e-com)
and `restaurant`, matching `business.VendorProfile.business_category`
verbatim. Each row also gets an explicit `*_percent` (the applied
value Paystack + checkout actually use) defaulted to the midpoint of
its advertised range.

Idempotent — safe to re-run.
"""
from decimal import Decimal

from django.db import migrations


def _midpoint(a, b):
    return ((a or Decimal('0')) + (b or Decimal('0'))) / Decimal('2')


def consolidate(apps, schema_editor):
    PlatformFee = apps.get_model('platform_admin', 'PlatformFee')

    # 1) Drop grocery — its bounds now live under `retail`.
    PlatformFee.objects.filter(business_type='grocery_delivery').delete()

    # 2) Rename restaurant_delivery → restaurant (or fold into existing).
    old_rest = PlatformFee.objects.filter(business_type='restaurant_delivery').first()
    if old_rest is not None:
        existing = PlatformFee.objects.filter(business_type='restaurant').first()
        if existing is None:
            old_rest.business_type = 'restaurant'
            old_rest.save(update_fields=['business_type'])
        else:
            # Already migrated by hand — discard the legacy row.
            old_rest.delete()

    # 3) Backfill the applied % on rows that still read as 0.
    for fee in PlatformFee.objects.all():
        changed = []
        if not fee.customer_service_fee_percent:
            fee.customer_service_fee_percent = _midpoint(
                fee.customer_service_fee_min, fee.customer_service_fee_max,
            )
            changed.append('customer_service_fee_percent')
        if not fee.merchant_commission_percent:
            fee.merchant_commission_percent = _midpoint(
                fee.merchant_commission_min, fee.merchant_commission_max,
            )
            changed.append('merchant_commission_percent')
        if changed:
            fee.save(update_fields=changed)


def reverse(apps, schema_editor):
    # No clean inverse — we'd have to invent the old rows. Treat the
    # consolidation as forward-only.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('platform_admin', '0004_update_platform_fee_schema'),
    ]

    operations = [
        migrations.RunPython(consolidate, reverse_code=reverse),
    ]
