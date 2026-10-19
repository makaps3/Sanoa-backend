"""Collapse vendor (User FK) + vendor_profile (VendorProfile FK) on PricePolicy and NegotiatedPrice."""
from django.db import migrations, models


def backfill(apps, schema_editor):
    VendorProfile = apps.get_model('business', 'VendorProfile')
    vp_by_user = {vp.user_id: vp.pk for vp in VendorProfile.objects.all()}

    def _fill(model):
        missing = model.objects.filter(vendor_profile__isnull=True).only('pk', 'vendor_id')
        for row in missing:
            vp_id = vp_by_user.get(row.vendor_id)
            if vp_id is None:
                vp = VendorProfile.objects.create(
                    user_id=row.vendor_id, profile_type='individual',
                    name=f'vendor-{row.vendor_id}',
                )
                vp_id = vp.pk
                vp_by_user[row.vendor_id] = vp_id
            model.objects.filter(pk=row.pk).update(vendor_profile_id=vp_id)

    _fill(apps.get_model('negotiations', 'PricePolicy'))
    _fill(apps.get_model('negotiations', 'NegotiatedPrice'))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('negotiations', '0002_negotiatedprice_vendor_profile_and_more'),
        ('business', '0011_add_business_address_type'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=noop),

        # PricePolicy
        migrations.AlterField(
            model_name='pricepolicy', name='vendor_profile',
            field=models.OneToOneField(
                on_delete=models.deletion.CASCADE, related_name='price_policy',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(model_name='pricepolicy', name='vendor'),
        migrations.RenameField(model_name='pricepolicy', old_name='vendor_profile', new_name='vendor'),

        # NegotiatedPrice
        migrations.AlterField(
            model_name='negotiatedprice', name='vendor_profile',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE, related_name='negotiated_prices',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(model_name='negotiatedprice', name='vendor'),
        migrations.RenameField(model_name='negotiatedprice', old_name='vendor_profile', new_name='vendor'),
    ]
