"""Seed the three default platform fee rows the ops team quotes.

These are the bounds the user provided when introducing the table:

    Restaurant delivery        customer 5%-10%   merchant 15%-30%
    Grocery delivery           customer 3%-8%    merchant 10%-20%
    E-commerce / retail        customer 0%-5%    merchant 5%-15%

Idempotent — uses get_or_create on business_type so re-running the
migration (or applying after a row was already created via the API)
doesn't blow up.
"""
from decimal import Decimal

from django.db import migrations


SEED = [
    {
        'business_type': 'restaurant_delivery',
        'customer_service_fee_min': Decimal('5.00'),
        'customer_service_fee_max': Decimal('10.00'),
        'merchant_commission_min':  Decimal('15.00'),
        'merchant_commission_max':  Decimal('30.00'),
    },
    {
        'business_type': 'grocery_delivery',
        'customer_service_fee_min': Decimal('3.00'),
        'customer_service_fee_max': Decimal('8.00'),
        'merchant_commission_min':  Decimal('10.00'),
        'merchant_commission_max':  Decimal('20.00'),
    },
    {
        'business_type': 'retail',
        'customer_service_fee_min': Decimal('0.00'),
        'customer_service_fee_max': Decimal('5.00'),
        'merchant_commission_min':  Decimal('5.00'),
        'merchant_commission_max':  Decimal('15.00'),
    },
]


def seed_fees(apps, schema_editor):
    PlatformFee = apps.get_model('platform_admin', 'PlatformFee')
    for row in SEED:
        PlatformFee.objects.get_or_create(
            business_type=row['business_type'],
            defaults={
                'customer_service_fee_min': row['customer_service_fee_min'],
                'customer_service_fee_max': row['customer_service_fee_max'],
                'merchant_commission_min':  row['merchant_commission_min'],
                'merchant_commission_max':  row['merchant_commission_max'],
                'is_active': True,
            },
        )


def unseed_fees(apps, schema_editor):
    PlatformFee = apps.get_model('platform_admin', 'PlatformFee')
    PlatformFee.objects.filter(
        business_type__in=[r['business_type'] for r in SEED],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('platform_admin', '0002_platformfee'),
    ]

    operations = [
        migrations.RunPython(seed_fees, reverse_code=unseed_fees),
    ]
