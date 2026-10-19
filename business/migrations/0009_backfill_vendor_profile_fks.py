"""Backfill vendor_profile FKs across apps from existing vendor=User FKs."""
from django.db import migrations


def backfill(apps, schema_editor):
    VendorProfile = apps.get_model('business', 'VendorProfile')

    # user_id -> VendorProfile pk mapping
    vp_by_user = {vp.user_id: vp.pk for vp in VendorProfile.objects.all()}

    def set_profile(model_label, vendor_field='vendor', target_field='vendor_profile'):
        app_label, model_name = model_label.split('.')
        Model = apps.get_model(app_label, model_name)
        for row in Model.objects.filter(**{f'{target_field}__isnull': True}).only('pk', f'{vendor_field}_id'):
            user_id = getattr(row, f'{vendor_field}_id')
            vp_pk = vp_by_user.get(user_id)
            if vp_pk:
                Model.objects.filter(pk=row.pk).update(**{target_field: vp_pk})

    # (app.Model, vendor_fk_name, target_fk_name)
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
        set_profile(model_label, vendor_field=vendor_field, target_field=target_field)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('business', '0008_migrate_vendor_profiles_data'),
        ('products', '0013_product_vendor_profile_vendorreview_vendor_profile'),
        ('orders', '0005_orderitem_vendor_profile_shoppingcart_vendor_profile'),
        ('negotiations', '0002_negotiatedprice_vendor_profile_and_more'),
        ('payments', '0003_paystacksubaccount_vendor_profile'),
        ('tiers', '0003_vendortiersubscription_vendor_profile'),
        ('debit', '0004_creditpurchase_vendor_profile'),
        ('delivery', '0003_deliveryfare_vendor_profile'),
        ('inventory', '0002_purchaseorder_supplier_profile'),
    ]
    operations = [migrations.RunPython(backfill, reverse_code=noop)]
