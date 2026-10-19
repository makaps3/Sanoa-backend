"""
Rebuild migration: drops NegotiatedPrice, adds min_floor_percent to PricePolicy,
and creates NegotiationRoom / NegotiationMessage / NegotiationOffer.
"""
import uuid
from datetime import timedelta

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('negotiations', '0003_collapse_vendor_to_profile'),
        ('orders', '0011_cartitem_negotiation_room'),  # drop old FK before deleting NegotiatedPrice
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ------------------------------------------------------------------ #
        # 1. Drop the old NegotiatedPrice model                              #
        # ------------------------------------------------------------------ #
        migrations.DeleteModel(name='NegotiatedPrice'),

        # ------------------------------------------------------------------ #
        # 2. Add min_floor_percent to PricePolicy                            #
        # ------------------------------------------------------------------ #
        migrations.AddField(
            model_name='pricepolicy',
            name='min_floor_percent',
            field=models.DecimalField(
                default=5.00,
                max_digits=5,
                decimal_places=2,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(50),
                ],
                help_text="Hard floor: AI won't accept offers below (price - min_floor%)",
            ),
        ),

        # ------------------------------------------------------------------ #
        # 3. NegotiationRoom                                                 #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name='NegotiationRoom',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True, default=uuid.uuid4, editable=False,
                )),
                ('product', models.ForeignKey(
                    to='products.Product',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='negotiation_rooms',
                )),
                ('buyer', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='negotiation_rooms_as_buyer',
                    limit_choices_to={'user_type': 'customer'},
                )),
                ('vendor', models.ForeignKey(
                    to='business.VendorProfile',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='negotiation_rooms',
                )),
                ('mode', models.CharField(
                    max_length=10,
                    choices=[('ai', 'AI Chatbot'), ('manual', 'Manual Vendor Chat')],
                    default='ai',
                )),
                ('status', models.CharField(
                    max_length=10,
                    choices=[
                        ('open', 'Open'),
                        ('agreed', 'Agreed — awaiting checkout'),
                        ('expired', 'Expired'),
                        ('cancelled', 'Cancelled'),
                    ],
                    default='open',
                )),
                ('agreed_price', models.DecimalField(
                    max_digits=10, decimal_places=2, null=True, blank=True,
                )),
                ('offer_expires_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Negotiation Room',
                'verbose_name_plural': 'Negotiation Rooms',
                'ordering': ['-created_at'],
            },
        ),

        # ------------------------------------------------------------------ #
        # 4. NegotiationMessage                                              #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name='NegotiationMessage',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True, default=uuid.uuid4, editable=False,
                )),
                ('room', models.ForeignKey(
                    to='negotiations.NegotiationRoom',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                )),
                ('sender_type', models.CharField(
                    max_length=10,
                    choices=[
                        ('buyer', 'Buyer'), ('vendor', 'Vendor'),
                        ('ai', 'AI Bot'), ('system', 'System'),
                    ],
                )),
                ('sender', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='negotiation_messages',
                )),
                ('content', models.TextField()),
                ('message_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('text', 'Text'), ('offer', 'Price Offer'),
                        ('counter_offer', 'Counter Offer'), ('accepted', 'Accepted'),
                        ('rejected', 'Rejected'), ('expired', 'Expired'),
                        ('system', 'System'),
                    ],
                    default='text',
                )),
                ('price_value', models.DecimalField(
                    max_digits=10, decimal_places=2, null=True, blank=True,
                )),
                ('is_seen', models.BooleanField(default=False)),
                ('seen_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Negotiation Message',
                'verbose_name_plural': 'Negotiation Messages',
                'ordering': ['created_at'],
            },
        ),

        # ------------------------------------------------------------------ #
        # 5. NegotiationOffer                                                #
        # ------------------------------------------------------------------ #
        migrations.CreateModel(
            name='NegotiationOffer',
            fields=[
                ('id', models.UUIDField(
                    primary_key=True, default=uuid.uuid4, editable=False,
                )),
                ('room', models.ForeignKey(
                    to='negotiations.NegotiationRoom',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='offers',
                )),
                ('message', models.OneToOneField(
                    to='negotiations.NegotiationMessage',
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='offer_detail',
                )),
                ('offered_by', models.CharField(
                    max_length=10,
                    choices=[
                        ('buyer', 'Buyer'), ('vendor', 'Vendor'), ('ai', 'AI Bot'),
                    ],
                )),
                ('original_price', models.DecimalField(max_digits=10, decimal_places=2)),
                ('offered_price', models.DecimalField(max_digits=10, decimal_places=2)),
                ('counter_offer_price', models.DecimalField(
                    max_digits=10, decimal_places=2, null=True, blank=True,
                )),
                ('status', models.CharField(
                    max_length=10,
                    choices=[
                        ('pending', 'Pending'), ('accepted', 'Accepted'),
                        ('rejected', 'Rejected'), ('countered', 'Countered'),
                        ('expired', 'Expired'),
                    ],
                    default='pending',
                )),
                ('ai_confidence', models.FloatField(null=True, blank=True)),
                ('ai_action', models.CharField(max_length=20, null=True, blank=True)),
                ('round_number', models.PositiveSmallIntegerField(default=1)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('responded_at', models.DateTimeField(null=True, blank=True)),
            ],
            options={
                'verbose_name': 'Negotiation Offer',
                'verbose_name_plural': 'Negotiation Offers',
                'ordering': ['-created_at'],
            },
        ),
    ]
