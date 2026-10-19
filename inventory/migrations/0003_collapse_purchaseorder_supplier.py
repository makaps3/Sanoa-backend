"""Collapse PurchaseOrder.supplier (User) + supplier_profile (VendorProfile) into supplier=VendorProfile FK."""
from django.db import migrations, models


def backfill(apps, schema_editor):
    Model = apps.get_model('inventory', 'PurchaseOrder')
    VendorProfile = apps.get_model('business', 'VendorProfile')

    vp_by_user = {vp.user_id: vp.pk for vp in VendorProfile.objects.all()}
    for row in Model.objects.filter(supplier_profile__isnull=True).only('pk', 'supplier_id'):
        vp_id = vp_by_user.get(row.supplier_id)
        if vp_id is None:
            vp = VendorProfile.objects.create(
                user_id=row.supplier_id, profile_type='individual',
                name=f'vendor-{row.supplier_id}',
            )
            vp_id = vp.pk
            vp_by_user[row.supplier_id] = vp_id
        Model.objects.filter(pk=row.pk).update(supplier_profile_id=vp_id)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0002_purchaseorder_supplier_profile'),
        ('business', '0011_add_business_address_type'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=noop),
        migrations.AlterField(
            model_name='purchaseorder', name='supplier_profile',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE, related_name='purchase_orders',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(model_name='purchaseorder', name='supplier'),
        migrations.RenameField(
            model_name='purchaseorder', old_name='supplier_profile', new_name='supplier',
        ),
    ]
