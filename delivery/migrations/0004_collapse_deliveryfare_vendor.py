"""Collapse DeliveryFare.vendor (User) + vendor_profile (VendorProfile) into vendor=VendorProfile FK."""
from django.db import migrations, models


def backfill(apps, schema_editor):
    Model = apps.get_model('delivery', 'DeliveryFare')
    VendorProfile = apps.get_model('business', 'VendorProfile')

    vp_by_user = {vp.user_id: vp.pk for vp in VendorProfile.objects.all()}
    for row in Model.objects.filter(vendor_profile__isnull=True).only('pk', 'vendor_id'):
        vp_id = vp_by_user.get(row.vendor_id)
        if vp_id is None:
            vp = VendorProfile.objects.create(
                user_id=row.vendor_id, profile_type='individual',
                name=f'vendor-{row.vendor_id}',
            )
            vp_id = vp.pk
            vp_by_user[row.vendor_id] = vp_id
        Model.objects.filter(pk=row.pk).update(vendor_profile_id=vp_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0003_deliveryfare_vendor_profile'),
        ('business', '0011_add_business_address_type'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=noop),
        migrations.AlterField(
            model_name='deliveryfare', name='vendor_profile',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE, related_name='delivery_fares',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(model_name='deliveryfare', name='vendor'),
        migrations.RenameField(
            model_name='deliveryfare', old_name='vendor_profile', new_name='vendor',
        ),
    ]
