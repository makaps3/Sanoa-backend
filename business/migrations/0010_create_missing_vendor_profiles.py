"""Create skeleton VendorProfile for any vendor users missing one; re-backfill all FKs."""
from django.db import migrations


def create_and_backfill(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    VendorProfile = apps.get_model('business', 'VendorProfile')

    # Create skeleton profiles for vendor users without one
    existing_user_ids = set(VendorProfile.objects.values_list('user_id', flat=True))
    for user in User.objects.filter(user_type='vendor').exclude(id__in=existing_user_ids):
        email = user.email or ''
        local = email.split('@')[0] if email else (user.username or f'vendor-{user.id}')
        VendorProfile.objects.create(
            user=user,
            profile_type='individual',
            name=local,
        )

    # Build map again now that all vendors have profiles
    vp_by_user = {vp.user_id: vp.pk for vp in VendorProfile.objects.all()}

    targets = [
        ('products.Product', 'vendor', 'vendor_profile'),
        ('products.VendorReview', 'vendor', 'vendor_profile'),
        ('orders.ShoppingCart', 'vendor', 'vendor_profile'),
        ('orders.OrderItem', 'vendor', 'vendor_profile'),
        ('negotiations.PricePolicy', 'vendor', 'vendor_profile'),
        ('negotiations.NegotiatedPrice', 'vendor', 'vendor_profile'),
        ('payments.PaystackSubaccount', 'vendor', 'vendor_profile'),
        ('tiers.VendorTierSubscription', 'vendor', 'vendor_profile'),
        ('debit.CreditPurchase', 'vendor', 'vendor_profile'),
        ('delivery.DeliveryFare', 'vendor', 'vendor_profile'),
        ('inventory.PurchaseOrder', 'supplier', 'supplier_profile'),
    ]
    for model_label, vendor_field, target_field in targets:
        app_label, model_name = model_label.split('.')
        Model = apps.get_model(app_label, model_name)
        for row in Model.objects.filter(**{f'{target_field}__isnull': True}).only('pk', f'{vendor_field}_id'):
            user_id = getattr(row, f'{vendor_field}_id')
            vp_pk = vp_by_user.get(user_id)
            if vp_pk:
                Model.objects.filter(pk=row.pk).update(**{target_field: vp_pk})


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('business', '0009_backfill_vendor_profile_fks')]
    operations = [migrations.RunPython(create_and_backfill, reverse_code=noop)]
