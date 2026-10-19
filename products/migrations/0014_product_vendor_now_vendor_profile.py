"""
Collapse Product.vendor (FK to User) and Product.vendor_profile (FK to
VendorProfile) into a single field named `vendor` that points to
VendorProfile.

Steps:
1. Back-fill vendor_profile for any Product row that doesn't have one,
   creating a skeleton VendorProfile if the vendor user has none.
2. Make vendor_profile non-nullable.
3. Remove the old User-pointing `vendor` field.
4. Rename vendor_profile -> vendor.
"""
from django.db import migrations, models


def backfill_vendor_profile(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    VendorProfile = apps.get_model('business', 'VendorProfile')

    # Map vendor user_id -> vendor_profile_id (only unified profile).
    vp_by_user = {
        vp.user_id: vp.pk for vp in VendorProfile.objects.all()
    }

    missing = Product.objects.filter(vendor_profile__isnull=True).only('pk', 'vendor_id')
    for product in missing:
        vp_id = vp_by_user.get(product.vendor_id)
        if vp_id is None:
            # Create a bare-bones unified profile so the NOT NULL constraint
            # can be added safely. seed_vendor_profiles can enrich later.
            vp = VendorProfile.objects.create(
                user_id=product.vendor_id,
                profile_type='individual',
                name=f"vendor-{product.vendor_id}",
            )
            vp_id = vp.pk
            vp_by_user[product.vendor_id] = vp_id
        Product.objects.filter(pk=product.pk).update(vendor_profile_id=vp_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0013_product_vendor_profile_vendorreview_vendor_profile'),
        ('business', '0011_add_business_address_type'),
    ]

    operations = [
        migrations.RunPython(backfill_vendor_profile, reverse_code=noop),
        migrations.AlterField(
            model_name='product',
            name='vendor_profile',
            field=models.ForeignKey(
                help_text='The vendor profile (store) that owns this product.',
                on_delete=models.deletion.CASCADE,
                related_name='products',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(
            model_name='product',
            name='vendor',
        ),
        migrations.RenameField(
            model_name='product',
            old_name='vendor_profile',
            new_name='vendor',
        ),
    ]
