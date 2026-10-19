import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('business', '0012_address_to_vendorprofile'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='FraudProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('risk_score', models.FloatField(default=0.0)),
                ('risk_level', models.CharField(
                    choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
                    default='low', max_length=10,
                )),
                ('total_orders', models.PositiveIntegerField(default=0)),
                ('total_order_value', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('refund_count', models.PositiveIntegerField(default=0)),
                ('dispute_count', models.PositiveIntegerField(default=0)),
                ('failed_payment_count', models.PositiveIntegerField(default=0)),
                ('is_flagged', models.BooleanField(default=False)),
                ('auto_flagged_at', models.DateTimeField(blank=True, null=True)),
                ('is_reviewed', models.BooleanField(default=False)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_outcome', models.CharField(
                    blank=True, max_length=20,
                    choices=[('cleared', 'Cleared'), ('confirmed', 'Confirmed Fraud'), ('monitoring', 'Under Monitoring')],
                )),
                ('review_notes', models.TextField(blank=True)),
                ('last_scored_at', models.DateTimeField(blank=True, null=True)),
                ('score_features', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='reviewed_fraud_profiles',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('user', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fraud_profile',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('vendor', models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='fraud_profile',
                    to='business.vendorprofile',
                )),
            ],
        ),
        migrations.CreateModel(
            name='FraudEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(
                    max_length=30,
                    choices=[
                        ('rapid_orders', 'Rapid Order Velocity'),
                        ('high_refund_rate', 'High Refund Rate'),
                        ('refund_abuse', 'Refund Abuse'),
                        ('dispute_pattern', 'Dispute Pattern'),
                        ('new_account_surge', 'New Account Order Surge'),
                        ('suspicious_vendor', 'Suspicious Vendor Activity'),
                        ('new_vendor_surge', 'New Vendor Order Surge'),
                        ('ml_anomaly', 'ML Anomaly Detected'),
                        ('credit_abuse', 'Credit/BNPL Abuse'),
                        ('payment_failure_spike', 'Payment Failure Spike'),
                        ('unverified_high_value', 'Unverified High-Value Transaction'),
                        ('unverified_active', 'Unverified Vendor with High Activity'),
                    ],
                )),
                ('severity', models.CharField(
                    choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')],
                    default='medium', max_length=10,
                )),
                ('description', models.TextField()),
                ('entity_type', models.CharField(
                    max_length=20,
                    choices=[('user', 'User'), ('vendor', 'Vendor'), ('order', 'Order'), ('transaction', 'Transaction'), ('refund', 'Refund')],
                )),
                ('entity_id', models.CharField(max_length=100)),
                ('metadata', models.JSONField(default=dict)),
                ('ml_score', models.FloatField(blank=True, null=True)),
                ('is_false_positive', models.BooleanField(default=False)),
                ('is_resolved', models.BooleanField(default=False)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='events',
                    to='fraud.fraudprofile',
                )),
                ('resolved_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='resolved_fraud_events',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='fraudprofile',
            constraint=models.CheckConstraint(
                check=(
                    models.Q(user__isnull=False, vendor__isnull=True)
                    | models.Q(user__isnull=True, vendor__isnull=False)
                ),
                name='fraud_profile_user_xor_vendor',
            ),
        ),
    ]
