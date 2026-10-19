"""Re-scope business.Address from a per-user table to a per-VendorProfile table.

By the time this runs, orders.ShippingAddress has already absorbed every
customer-owned address (see orders.0008). Any remaining Address row should
belong to a vendor user whose VendorProfile we can re-point it to; rows
that can't be mapped are deleted.
"""
import django.db.models.deletion
from django.db import migrations, models


def backfill_vendor_fk(apps, schema_editor):
    Address = apps.get_model('business', 'Address')
    VendorProfile = apps.get_model('business', 'VendorProfile')

    vp_by_user = {vp.user_id: vp.pk for vp in VendorProfile.objects.all()}

    for row in Address.objects.all().only('pk', 'user_id'):
        vp_id = vp_by_user.get(row.user_id)
        if vp_id is None:
            # No vendor profile → not a vendor address; drop it.
            row.delete()
            continue
        Address.objects.filter(pk=row.pk).update(vendor_id=vp_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('business', '0011_add_business_address_type'),
        ('orders', '0008_shippingaddress_and_order_fk'),
    ]

    operations = [
        # Add the new FK as nullable so existing rows survive until backfilled.
        migrations.AddField(
            model_name='address',
            name='vendor',
            field=models.ForeignKey(
                help_text='The vendor profile (store) that owns this address.',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='addresses',
                to='business.vendorprofile',
            ),
        ),
        migrations.RunPython(backfill_vendor_fk, reverse_code=noop),
        # Now require vendor.
        migrations.AlterField(
            model_name='address',
            name='vendor',
            field=models.ForeignKey(
                help_text='The vendor profile (store) that owns this address.',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='addresses',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(
            model_name='address',
            name='user',
        ),
        migrations.AlterField(
            model_name='address',
            name='address_type',
            field=models.CharField(
                choices=[
                    ('billing', 'Billing Address'),
                    ('shipping', 'Shipping Address'),
                    ('both', 'Billing & Shipping'),
                    ('business', 'Business Address'),
                ],
                default='business',
                max_length=10,
            ),
        ),
        migrations.AlterModelOptions(
            name='address',
            options={
                'ordering': ['-is_default', '-created_at'],
                'verbose_name': 'Vendor Address',
                'verbose_name_plural': 'Vendor Addresses',
            },
        ),
    ]
