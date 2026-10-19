"""Collapse ShoppingCart.vendor (User) + ShoppingCart.vendor_profile (VendorProfile) into a single vendor=VendorProfile FK. Same for OrderItem."""
from django.db import migrations, models


def backfill(apps, schema_editor):
    VendorProfile = apps.get_model('business', 'VendorProfile')
    vp_by_user = {vp.user_id: vp.pk for vp in VendorProfile.objects.all()}

    def _fill(model, user_fk, profile_fk):
        missing = model.objects.filter(**{f'{profile_fk}__isnull': True}).only('pk', f'{user_fk}_id')
        for row in missing:
            user_id = getattr(row, f'{user_fk}_id')
            vp_id = vp_by_user.get(user_id)
            if vp_id is None:
                vp = VendorProfile.objects.create(
                    user_id=user_id, profile_type='individual',
                    name=f'vendor-{user_id}',
                )
                vp_id = vp.pk
                vp_by_user[user_id] = vp_id
            model.objects.filter(pk=row.pk).update(**{f'{profile_fk}_id': vp_id})

    _fill(apps.get_model('orders', 'ShoppingCart'), 'vendor', 'vendor_profile')
    _fill(apps.get_model('orders', 'OrderItem'), 'vendor', 'vendor_profile')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_orderitem_vendor_profile_shoppingcart_vendor_profile'),
        ('business', '0011_add_business_address_type'),
        ('products', '0014_product_vendor_now_vendor_profile'),
    ]

    operations = [
        migrations.RunPython(backfill, reverse_code=noop),

        # ShoppingCart
        migrations.AlterUniqueTogether(name='shoppingcart', unique_together=set()),
        migrations.AlterField(
            model_name='shoppingcart', name='vendor_profile',
            field=models.ForeignKey(
                help_text='The vendor profile (store) this cart belongs to. All items must be from this vendor.',
                on_delete=models.deletion.CASCADE, related_name='carts',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(model_name='shoppingcart', name='vendor'),
        migrations.RenameField(model_name='shoppingcart', old_name='vendor_profile', new_name='vendor'),
        migrations.AlterUniqueTogether(
            name='shoppingcart',
            unique_together={('user', 'vendor')},
        ),

        # OrderItem
        migrations.AlterField(
            model_name='orderitem', name='vendor_profile',
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE, related_name='order_items',
                to='business.vendorprofile',
            ),
        ),
        migrations.RemoveField(model_name='orderitem', name='vendor'),
        migrations.RenameField(model_name='orderitem', old_name='vendor_profile', new_name='vendor'),
    ]
