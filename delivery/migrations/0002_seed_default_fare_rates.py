from decimal import Decimal
from django.db import migrations


def seed(apps, schema_editor):
    FareRate = apps.get_model('delivery', 'FareRate')
    defaults = [
        {
            'business_category': 'retail',
            'base_fare': Decimal('20.00'),
            'per_km_rate': Decimal('8.00'),
            'max_distance_km': Decimal('100.00'),
        },
        {
            'business_category': 'restaurant',
            'base_fare': Decimal('20.00'),
            'per_km_rate': Decimal('10.00'),
            'max_distance_km': Decimal('50.00'),
        },
    ]
    for d in defaults:
        FareRate.objects.update_or_create(
            business_category=d['business_category'],
            defaults={
                'base_fare': d['base_fare'],
                'per_km_rate': d['per_km_rate'],
                'max_distance_km': d['max_distance_km'],
                'is_active': True,
            },
        )


def unseed(apps, schema_editor):
    FareRate = apps.get_model('delivery', 'FareRate')
    FareRate.objects.filter(business_category__in=['retail', 'restaurant']).delete()


class Migration(migrations.Migration):
    dependencies = [('delivery', '0001_initial')]
    operations = [migrations.RunPython(seed, reverse_code=unseed)]
