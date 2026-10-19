import uuid
import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('delivery', '0005_deliveryfare_address_to_shippingaddress'),
        ('orders', '0010_remove_restaurant_fields'),
        ('restaurant', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # DriverShift
        migrations.CreateModel(
            name='DriverShift',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('ended_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('start_latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('start_longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('end_latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('end_longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shifts', to='delivery.deliverydriver')),
            ],
            options={
                'verbose_name': 'Driver Shift',
                'verbose_name_plural': 'Driver Shifts',
                'ordering': ['-started_at'],
            },
        ),

        # DeliveryJob
        migrations.CreateModel(
            name='DeliveryJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'), ('accepted', 'Accepted'),
                        ('driver_at_vendor', 'Driver at Vendor'), ('picked_up', 'Picked Up'),
                        ('in_transit', 'In Transit'), ('delivered', 'Delivered'),
                        ('cancelled', 'Cancelled'), ('failed', 'Failed'),
                    ],
                    default='pending', max_length=20,
                )),
                ('pickup_latitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('pickup_longitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('dropoff_latitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('dropoff_longitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('distance_km', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6)),
                ('fare_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8)),
                ('delivery_notes', models.TextField(blank=True)),
                ('proof_of_delivery_image', models.ImageField(blank=True, null=True, upload_to='delivery/proof/')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('driver_at_vendor_at', models.DateTimeField(blank=True, null=True)),
                ('picked_up_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('customer', models.ForeignKey(
                    limit_choices_to={'user_type': 'customer'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='delivery_jobs', to=settings.AUTH_USER_MODEL,
                )),
                ('driver', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='jobs', to='delivery.deliverydriver',
                )),
                ('fare', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='job', to='delivery.deliveryfare',
                )),
                ('retail_order', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='delivery_job', to='orders.order',
                )),
                ('vendor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='delivery_jobs', to='business.vendorprofile',
                )),
            ],
            options={
                'verbose_name': 'Delivery Job',
                'verbose_name_plural': 'Delivery Jobs',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', 'created_at'], name='delivery_job_status_created_idx'),
                    models.Index(fields=['driver', 'status'], name='delivery_job_driver_status_idx'),
                ],
            },
        ),

        # Restaurant order FK on DeliveryJob — deferred because restaurant app
        # migration runs after delivery migration.
        # Added as a separate operation so it can handle the dependency cleanly.
        migrations.AddField(
            model_name='deliveryjob',
            name='restaurant_order',
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='delivery_job', to='restaurant.restaurantorder',
            ),
        ),

        # DriverLocationPing
        migrations.CreateModel(
            name='DriverLocationPing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('latitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('longitude', models.DecimalField(decimal_places=6, max_digits=9)),
                ('accuracy_meters', models.FloatField(blank=True, null=True)),
                ('speed_kmh', models.FloatField(blank=True, null=True)),
                ('heading_degrees', models.FloatField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('driver', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='location_pings', to='delivery.deliverydriver',
                )),
                ('job', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='location_pings', to='delivery.deliveryjob',
                )),
            ],
            options={
                'verbose_name': 'Driver Location Ping',
                'verbose_name_plural': 'Driver Location Pings',
                'ordering': ['timestamp'],
                'indexes': [
                    models.Index(fields=['job', 'timestamp'], name='delivery_ping_job_ts_idx'),
                ],
            },
        ),

        # DriverPayout (must precede DriverEarning)
        migrations.CreateModel(
            name='DriverPayout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('period_start', models.DateTimeField()),
                ('period_end', models.DateTimeField()),
                ('total_gross', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total_commission', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total_net', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('processing', 'Processing'), ('paid', 'Paid'), ('failed', 'Failed')],
                    default='pending', max_length=20,
                )),
                ('payment_reference', models.CharField(blank=True, max_length=100)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('driver', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='payouts', to='delivery.deliverydriver',
                )),
            ],
            options={
                'verbose_name': 'Driver Payout',
                'verbose_name_plural': 'Driver Payouts',
                'ordering': ['-period_end'],
            },
        ),

        # DriverEarning
        migrations.CreateModel(
            name='DriverEarning',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('gross_amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('platform_commission', models.DecimalField(decimal_places=2, max_digits=8)),
                ('net_amount', models.DecimalField(decimal_places=2, max_digits=8)),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('paid', 'Paid'), ('disputed', 'Disputed')],
                    default='pending', max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('driver', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='earnings', to='delivery.deliverydriver',
                )),
                ('job', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='earning', to='delivery.deliveryjob',
                )),
                ('payout', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='earnings', to='delivery.driverpayout',
                )),
            ],
            options={
                'verbose_name': 'Driver Earning',
                'verbose_name_plural': 'Driver Earnings',
                'ordering': ['-created_at'],
            },
        ),

        # DriverRating
        migrations.CreateModel(
            name='DriverRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('rating', models.PositiveSmallIntegerField(
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(5),
                    ]
                )),
                ('comment', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(
                    limit_choices_to={'user_type': 'customer'},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='driver_ratings_given', to=settings.AUTH_USER_MODEL,
                )),
                ('driver', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ratings', to='delivery.deliverydriver',
                )),
                ('job', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rating', to='delivery.deliveryjob',
                )),
            ],
            options={
                'verbose_name': 'Driver Rating',
                'verbose_name_plural': 'Driver Ratings',
            },
        ),
    ]
