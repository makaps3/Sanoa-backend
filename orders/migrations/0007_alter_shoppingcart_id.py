"""Switch ShoppingCart primary key from auto-int to UUID.

Carts are ephemeral shopping state, so existing CartItem + ShoppingCart
rows are wiped rather than migrated across the PK type change. Clients
just re-add items after deploy.
"""
import uuid
from django.db import migrations, models

from core.migration_ops import AlterPrimaryKeyToUUID


def wipe_carts(apps, schema_editor):
    CartItem = apps.get_model('orders', 'CartItem')
    ShoppingCart = apps.get_model('orders', 'ShoppingCart')
    CartItem.objects.all().delete()
    ShoppingCart.objects.all().delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_collapse_vendor_to_profile'),
    ]

    operations = [
        migrations.RunPython(wipe_carts, reverse_code=noop),
        AlterPrimaryKeyToUUID(
            model_name='shoppingcart',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
    ]
