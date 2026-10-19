"""Collapse VendorReview.vendor (User) + vendor_profile (VendorProfile) into single vendor=VendorProfile FK."""
from django.db import migrations, models


def backfill(apps, schema_editor):
    VendorReview = apps.get_model('products', 'VendorReview')
    VendorProfile = apps.get_model('business', 'VendorProfile')

    vp_by_user = {vp.user_id: vp.pk for vp in VendorProfile.objects.all()}

    missing = VendorReview.objects.filter(vendor_profile__isnull=True).only('pk', 'vendor_id')
    for row in missing:
        vp_id = vp_by_user.get(row.vendor_id)
        if vp_id is None:
            vp = VendorProfile.objects.create(
                user_id=row.vendor_id, profile_type='individual',
                name=f'vendor-{row.vendor_id}',
            )
            vp_id = vp.pk
            vp_by_user[row.vendor_id] = vp_id
        VendorReview.objects.filter(pk=row.pk).update(vendor_profile_id=vp_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0014_product_vendor_now_vendor_profile'),
        ('business', '0011_add_business_address_type'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=noop),

        migrations.AlterUniqueTogether(name='vendorreview', unique_together=set()),
        migrations.AlterField(
            model_name='vendorreview', name='vendor_profile',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE, related_name='reviews',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(model_name='vendorreview', name='vendor'),
        migrations.RenameField(model_name='vendorreview', old_name='vendor_profile', new_name='vendor'),
        migrations.AlterUniqueTogether(
            name='vendorreview',
            unique_together={('user', 'vendor')},
        ),
    ]
