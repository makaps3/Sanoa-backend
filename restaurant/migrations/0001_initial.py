import uuid
import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('business', '__first__'),
        ('orders', '0010_remove_restaurant_fields'),
        ('products', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RestaurantCart',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='restaurant_carts', to=settings.AUTH_USER_MODEL)),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='restaurant_carts', to='business.vendorprofile')),
            ],
            options={
                'verbose_name': 'Restaurant Cart',
                'verbose_name_plural': 'Restaurant Carts',
                'unique_together': {('user', 'vendor')},
            },
        ),
        migrations.CreateModel(
            name='RestaurantCartItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ('price_at_time', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('special_instructions', models.CharField(blank=True, max_length=500)),
                ('selected_addons', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cart', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='restaurant.restaurantcart')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='products.product')),
                ('product_variant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='products.productvariant')),
            ],
            options={
                'verbose_name': 'Restaurant Cart Item',
                'verbose_name_plural': 'Restaurant Cart Items',
            },
        ),
        migrations.CreateModel(
            name='RestaurantOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('order_number', models.CharField(blank=True, max_length=50, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('confirmed', 'Confirmed'), ('preparing', 'Preparing'), ('ready', 'Ready'), ('out_for_delivery', 'Out for Delivery'), ('delivered', 'Delivered'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('refunded', 'Refunded')], default='pending', max_length=20)),
                ('payment_status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('partially_paid', 'Partially Paid'), ('failed', 'Failed'), ('refunded', 'Refunded'), ('partially_refunded', 'Partially Refunded')], default='pending', max_length=20)),
                ('fulfillment_type', models.CharField(choices=[('delivery', 'Delivery'), ('pickup', 'Pickup'), ('dine_in', 'Dine-in')], default='delivery', max_length=20)),
                ('estimated_prep_minutes', models.PositiveIntegerField(blank=True, null=True)),
                ('scheduled_for', models.DateTimeField(blank=True, null=True)),
                ('table_number', models.CharField(blank=True, max_length=20)),
                ('subtotal', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('tax_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('delivery_fee', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('discount_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('customer_email', models.EmailField(max_length=254)),
                ('customer_phone', models.CharField(blank=True, max_length=17)),
                ('shipping_full_name', models.CharField(blank=True, max_length=100)),
                ('shipping_street_address', models.CharField(blank=True, max_length=255)),
                ('shipping_apartment_number', models.CharField(blank=True, max_length=20)),
                ('shipping_city', models.CharField(blank=True, max_length=100)),
                ('shipping_state_province', models.CharField(blank=True, max_length=100)),
                ('shipping_postal_code', models.CharField(blank=True, max_length=20)),
                ('shipping_country', models.CharField(blank=True, max_length=100)),
                ('coupon_code', models.CharField(blank=True, max_length=50)),
                ('order_notes', models.TextField(blank=True)),
                ('internal_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('ready_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='restaurant_orders', to=settings.AUTH_USER_MODEL)),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='restaurant_orders', to='business.vendorprofile')),
                ('shipping_address', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='restaurant_orders', to='orders.shippingaddress')),
            ],
            options={
                'verbose_name': 'Restaurant Order',
                'verbose_name_plural': 'Restaurant Orders',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'status'], name='restaurant__user_id_status_idx'),
                    models.Index(fields=['vendor', 'status'], name='restaurant__vendor_id_status_idx'),
                    models.Index(fields=['status', 'created_at'], name='restaurant__status_created_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='RestaurantOrderItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('product_name', models.CharField(max_length=300)),
                ('product_sku', models.CharField(max_length=100)),
                ('variant_name', models.CharField(blank=True, max_length=200)),
                ('quantity', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('addons_total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('special_instructions', models.CharField(blank=True, max_length=500)),
                ('selected_addons', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='restaurant.restaurantorder')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='products.product')),
                ('product_variant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='products.productvariant')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='restaurant_order_items', to='business.vendorprofile')),
            ],
            options={
                'verbose_name': 'Restaurant Order Item',
                'verbose_name_plural': 'Restaurant Order Items',
            },
        ),
        migrations.CreateModel(
            name='KitchenTicket',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('status', models.CharField(choices=[('new', 'New'), ('acknowledged', 'Acknowledged'), ('preparing', 'Preparing'), ('ready', 'Ready'), ('handed_off', 'Handed Off')], default='new', max_length=20)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('ready_at', models.DateTimeField(blank=True, null=True)),
                ('handed_off_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='kitchen_ticket', to='restaurant.restaurantorder')),
            ],
            options={
                'verbose_name': 'Kitchen Ticket',
                'verbose_name_plural': 'Kitchen Tickets',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='RestaurantOrderTrackingEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(choices=[('order_placed', 'Order Placed'), ('payment_confirmed', 'Payment Confirmed'), ('order_confirmed', 'Order Confirmed'), ('preparing', 'Kitchen is Preparing'), ('ready', 'Ready'), ('driver_assigned', 'Driver Assigned'), ('driver_at_vendor', 'Driver at Restaurant'), ('out_for_delivery', 'Out for Delivery'), ('delivered', 'Delivered'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], max_length=50)),
                ('message', models.CharField(max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tracking_events', to='restaurant.restaurantorder')),
            ],
            options={
                'verbose_name': 'Order Tracking Event',
                'verbose_name_plural': 'Order Tracking Events',
                'ordering': ['created_at'],
            },
        ),
    ]
