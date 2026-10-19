"""
Analytics models — pre-computed ML scores and daily platform snapshots.
All scores are recomputed automatically via Celery beat tasks.

Already-applied ML (do not touch):
  - fraud app: fraud scoring (XGBoost/Scikit-learn)
  - negotiations app: XGBoost AI chatbot

New ML applied here:
  - CustomerChurnScore    → Scikit-learn (rule-based → RandomForest as data grows)
  - VendorPerformanceScore → XGBoost
  - DriverPerformanceScore → Scikit-learn
"""
from decimal import Decimal
from django.conf import settings
from django.db import models


class DailyPlatformSnapshot(models.Model):
    """Pre-computed daily platform-wide metrics. Computed nightly via Celery."""

    date = models.DateField(unique=True, db_index=True)

    # Registrations
    new_customers = models.IntegerField(default=0)
    new_vendors = models.IntegerField(default=0)
    new_drivers = models.IntegerField(default=0)
    total_customers = models.IntegerField(default=0)
    total_vendors = models.IntegerField(default=0)
    total_drivers = models.IntegerField(default=0)

    # Orders
    total_orders = models.IntegerField(default=0)
    completed_orders = models.IntegerField(default=0)
    cancelled_orders = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Transactions
    total_transactions = models.IntegerField(default=0)
    successful_transactions = models.IntegerField(default=0)
    failed_transactions = models.IntegerField(default=0)
    total_transaction_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    total_refunds = models.IntegerField(default=0)
    total_refund_value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # Negotiations
    total_negotiations = models.IntegerField(default=0)
    agreed_negotiations = models.IntegerField(default=0)

    # Deliveries
    total_deliveries = models.IntegerField(default=0)
    completed_deliveries = models.IntegerField(default=0)
    failed_deliveries = models.IntegerField(default=0)

    # Credit / Debit
    credit_accounts_opened = models.IntegerField(default=0)
    credit_issued = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    credit_repaid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    overdue_accounts = models.IntegerField(default=0)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Daily Platform Snapshot'
        verbose_name_plural = 'Daily Platform Snapshots'

    def __str__(self):
        return f'Snapshot {self.date}'


class CustomerChurnScore(models.Model):
    """
    ML churn risk per customer.
    Stage 1 (current): rule-based scoring.
    Stage 2 (medium): Scikit-learn RandomForest when > 500 labeled samples exist.
    Recomputed weekly via Celery.
    """

    RISK_CHOICES = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='churn_score',
    )
    churn_probability = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.0000'),
        help_text='0.0 = no risk, 1.0 = certain churn',
    )
    risk_segment = models.CharField(max_length=10, choices=RISK_CHOICES, default='low')

    # Feature snapshot at scoring time
    days_since_last_order = models.IntegerField(default=0)
    total_orders = models.IntegerField(default=0)
    total_spend = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    avg_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    has_subscription = models.BooleanField(default=False)
    loyalty_points = models.IntegerField(default=0)

    scored_at = models.DateTimeField(auto_now=True)
    model_version = models.CharField(max_length=20, default='rule-based-v1')

    class Meta:
        verbose_name = 'Customer Churn Score'
        verbose_name_plural = 'Customer Churn Scores'
        ordering = ['-churn_probability']

    def __str__(self):
        return f'{self.user.email} — {self.risk_segment} ({self.churn_probability})'


class VendorPerformanceScore(models.Model):
    """
    XGBoost vendor performance score (0–100).
    Recomputed weekly via Celery.
    """

    TIER_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
    ]

    vendor = models.OneToOneField(
        'business.VendorProfile',
        on_delete=models.CASCADE,
        related_name='performance_score',
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='bronze')

    # Feature snapshot
    total_orders = models.IntegerField(default=0)
    completion_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    avg_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    refund_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    dispute_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    negotiation_agreement_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    days_since_last_sale = models.IntegerField(default=0)

    scored_at = models.DateTimeField(auto_now=True)
    model_version = models.CharField(max_length=20, default='xgb-rule-v1')

    class Meta:
        verbose_name = 'Vendor Performance Score'
        verbose_name_plural = 'Vendor Performance Scores'
        ordering = ['-score']

    def __str__(self):
        return f'{self.vendor} — {self.score} ({self.tier})'


class DriverPerformanceScore(models.Model):
    """
    Scikit-learn driver performance score (0–100).
    Also flags payout anomalies (XGBoost).
    Recomputed weekly via Celery.
    """

    GRADE_CHOICES = [
        ('A', 'Excellent (90-100)'),
        ('B', 'Good (75-89)'),
        ('C', 'Average (60-74)'),
        ('D', 'Below Average (40-59)'),
        ('F', 'Poor (0-39)'),
    ]

    driver = models.OneToOneField(
        'delivery.DeliveryDriver',
        on_delete=models.CASCADE,
        related_name='performance_score',
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    grade = models.CharField(max_length=2, choices=GRADE_CHOICES, default='C')
    payout_anomaly = models.BooleanField(
        default=False,
        help_text='True when payout pattern is flagged as abnormal by XGBoost.',
    )

    # Feature snapshot
    total_deliveries = models.IntegerField(default=0)
    completion_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))
    avg_rating = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.00'))
    avg_delivery_time_mins = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    on_time_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.0000'))

    scored_at = models.DateTimeField(auto_now=True)
    model_version = models.CharField(max_length=20, default='sklearn-rule-v1')

    class Meta:
        verbose_name = 'Driver Performance Score'
        verbose_name_plural = 'Driver Performance Scores'
        ordering = ['-score']

    def __str__(self):
        return f'{self.driver.user.email} — {self.score} ({self.grade})'
