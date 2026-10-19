"""Create orders.ShippingAddress + Order.shipping_address FK + copy existing customer
addresses from business.Address into the new table."""
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def copy_customer_addresses(apps, schema_editor):
    """Copy business.Address rows owned by customer users into orders.ShippingAddress.

    Vendor-owned Address rows are left alone — the business.Address migration
    (0012) will re-point them to their VendorProfile. After this copy, the
    customer rows are deleted from business.Address.
    """
    BusinessAddress = apps.get_model('business', 'Address')
    ShippingAddress = apps.get_model('orders', 'ShippingAddress')

    TYPE_MAP = {
        'billing': 'billing',
        'shipping': 'shipping',
        'both': 'both',
        'business': 'shipping',
    }

    customer_rows = BusinessAddress.objects.select_related('user').filter(
        user__user_type='customer',
    )
    for row in customer_rows:
        ShippingAddress.objects.create(
            user_id=row.user_id,
            address_type=TYPE_MAP.get(row.address_type, 'shipping'),
            full_name=row.full_name,
            phone_number=row.phone_number,
            street_address=row.street_address,
            apartment_number=row.apartment_number,
            city=row.city,
            state_province=row.state_province,
            postal_code=row.postal_code,
            country=row.country,
            latitude=row.latitude,
            longitude=row.longitude,
            is_default=row.is_default,
            delivery_instructions=row.delivery_instructions,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    customer_rows.delete()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_alter_shoppingcart_id'),
        ('business', '0011_add_business_address_type'),
        (settings.AUTH_USER_MODEL.split('.')[0], '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShippingAddress',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('address_type', models.CharField(
                    choices=[
                        ('shipping', 'Shipping Address'),
                        ('billing', 'Billing Address'),
                        ('both', 'Billing & Shipping'),
                    ],
                    default='shipping', max_length=10,
                )),
                ('label', models.CharField(
                    blank=True, help_text="Optional label, e.g. 'Mom's house', 'Office annex'.",
                    max_length=50,
                )),
                ('full_name', models.CharField(max_length=100)),
                ('phone_number', models.CharField(max_length=17)),
                ('street_address', models.CharField(max_length=255)),
                ('apartment_number', models.CharField(blank=True, max_length=20)),
                ('city', models.CharField(max_length=100)),
                ('state_province', models.CharField(max_length=100)),
                ('postal_code', models.CharField(max_length=20)),
                ('country', models.CharField(default='South Africa', max_length=100)),
                ('latitude', models.DecimalField(
                    blank=True, decimal_places=6,
                    help_text='Latitude for delivery distance calculation',
                    max_digits=9, null=True,
                )),
                ('longitude', models.DecimalField(
                    blank=True, decimal_places=6,
                    help_text='Longitude for delivery distance calculation',
                    max_digits=9, null=True,
                )),
                ('is_default', models.BooleanField(default=False)),
                ('delivery_instructions', models.TextField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    help_text='The customer who owns this shipping address.',
                    limit_choices_to={'user_type': 'customer'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='shipping_addresses',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Shipping Address',
                'verbose_name_plural': 'Shipping Addresses',
                'ordering': ['-is_default', '-created_at'],
            },
        ),
        migrations.AddField(
            model_name='order',
            name='shipping_address',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='orders', to='orders.shippingaddress',
            ),
        ),
        migrations.RunPython(copy_customer_addresses, reverse_code=noop),
    ]
