"""
Notification models.

Notification  — one persisted record per notification event per recipient.
NotificationPreference — per-user category toggles.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    # ── Types ────────────────────────────────────────────────────
    # Customer-facing
    WELCOME               = 'welcome'
    ORDER_CREATED         = 'order_created'
    ORDER_PROCESSING      = 'order_processing'
    ORDER_SHIPPED         = 'order_shipped'
    ORDER_DELIVERED       = 'order_delivered'
    ORDER_CANCELLED       = 'order_cancelled'
    ORDER_REFUNDED        = 'order_refunded'
    PAYMENT_SUCCESS       = 'payment_success'
    PAYMENT_FAILED        = 'payment_failed'
    SUBSCRIPTION_CREATED  = 'subscription_created'
    SUBSCRIPTION_EXPIRING = 'subscription_expiring'
    SUBSCRIPTION_EXPIRED  = 'subscription_expired'
    SUBSCRIPTION_PAST_DUE = 'subscription_past_due'
    CREDIT_ACCOUNT_CREATED  = 'credit_account_created'
    CREDIT_PURCHASE_CREATED = 'credit_purchase_created'
    CREDIT_REPAYMENT        = 'credit_repayment_received'
    CREDIT_LOW_BALANCE      = 'credit_low_balance'
    CREDIT_OVERDUE          = 'credit_overdue'
    CREDIT_SUSPENDED        = 'credit_suspended'
    CREDIT_UNSUSPENDED      = 'credit_unsuspended'
    NEGOTIATION_OFFER       = 'negotiation_offer'
    NEGOTIATION_COUNTER     = 'negotiation_counter'
    NEGOTIATION_ACCEPTED    = 'negotiation_accepted'
    NEGOTIATION_REJECTED    = 'negotiation_rejected'
    NEGOTIATION_REMINDER    = 'negotiation_reminder'
    NEGOTIATION_EXPIRED     = 'negotiation_expired'
    NEGOTIATION_AGREED      = 'negotiation_agreed'
    DELIVERY_ASSIGNED       = 'delivery_assigned'
    DELIVERY_PICKED_UP      = 'delivery_picked_up'
    DELIVERY_IN_TRANSIT     = 'delivery_in_transit'
    DELIVERY_COMPLETED      = 'delivery_completed'
    VENDOR_FOLLOWED         = 'vendor_followed'
    VENDOR_UNFOLLOWED       = 'vendor_unfollowed'
    REFUND_REQUESTED        = 'refund_requested'
    REFUND_PROCESSED        = 'refund_processed'
    DISPUTE_CREATED         = 'dispute_created'
    DISPUTE_RESOLVED        = 'dispute_resolved'
    # Vendor-facing
    NEW_ORDER               = 'new_order'
    NEW_FOLLOWER            = 'new_follower'
    UNFOLLOWED_BY           = 'unfollowed_by'
    VENDOR_NEGOTIATION_OFFER    = 'vendor_negotiation_offer'
    VENDOR_NEGOTIATION_REMINDER = 'vendor_negotiation_reminder'
    VENDOR_PAYMENT_RECEIVED = 'vendor_payment_received'
    VERIFICATION_APPROVED   = 'verification_approved'
    VERIFICATION_REJECTED   = 'verification_rejected'
    VENDOR_ORDER_CANCELLED  = 'vendor_order_cancelled'
    VENDOR_REFUND_REQUESTED = 'vendor_refund_requested'
    VENDOR_DISPUTE          = 'vendor_dispute'
    VENDOR_FRAUD_FLAGGED    = 'vendor_fraud_flagged'
    VENDOR_FRAUD_CLEARED    = 'vendor_fraud_cleared'
    # Vendor-facing — tier subscription
    VENDOR_TIER_ACTIVATED   = 'vendor_tier_activated'
    VENDOR_TIER_EXPIRING    = 'vendor_tier_expiring'
    VENDOR_TIER_EXPIRED     = 'vendor_tier_expired'
    VENDOR_TIER_PAST_DUE    = 'vendor_tier_past_due'
    VENDOR_TIER_CANCELLED   = 'vendor_tier_cancelled'
    # Vendor-facing — inventory
    VENDOR_LOW_STOCK        = 'vendor_low_stock'
    VENDOR_OUT_OF_STOCK     = 'vendor_out_of_stock'
    # Vendor-facing — vetting result
    VENDOR_VETTING_PASSED   = 'vendor_vetting_passed'
    VENDOR_VETTING_FAILED   = 'vendor_vetting_failed'
    VENDOR_VETTING_RESUBMIT = 'vendor_vetting_resubmit'
    # Admin-facing
    ADMIN_NEW_USER          = 'admin_new_user'
    ADMIN_NEW_BUSINESS      = 'admin_new_business'
    ADMIN_REFUND_PENDING    = 'admin_refund_pending'
    ADMIN_DISPUTE           = 'admin_dispute'
    ADMIN_FRAUD_HIGH        = 'admin_fraud_high'
    ADMIN_FRAUD_CRITICAL    = 'admin_fraud_critical'
    ADMIN_CREDIT_DEFAULTED  = 'admin_credit_defaulted'
    ADMIN_VENDOR_PENDING    = 'admin_vendor_pending'
    ADMIN_VETTING_SUBMITTED = 'admin_vetting_submitted'
    ADMIN_PAYMENT_FAILED    = 'admin_payment_failed'
    ADMIN_TIER_PAST_DUE     = 'admin_tier_past_due'

    NOTIFICATION_TYPE_CHOICES = [
        (WELCOME,               'Welcome'),
        (ORDER_CREATED,         'Order Created'),
        (ORDER_PROCESSING,      'Order Processing'),
        (ORDER_SHIPPED,         'Order Shipped'),
        (ORDER_DELIVERED,       'Order Delivered'),
        (ORDER_CANCELLED,       'Order Cancelled'),
        (ORDER_REFUNDED,        'Order Refunded'),
        (PAYMENT_SUCCESS,       'Payment Successful'),
        (PAYMENT_FAILED,        'Payment Failed'),
        (SUBSCRIPTION_CREATED,  'Subscription Created'),
        (SUBSCRIPTION_EXPIRING, 'Subscription Expiring Soon'),
        (SUBSCRIPTION_EXPIRED,  'Subscription Expired'),
        (SUBSCRIPTION_PAST_DUE, 'Subscription Past Due'),
        (CREDIT_ACCOUNT_CREATED,  'Credit Account Created'),
        (CREDIT_PURCHASE_CREATED, 'Credit Purchase Created'),
        (CREDIT_REPAYMENT,        'Credit Repayment Received'),
        (CREDIT_LOW_BALANCE,      'Low Credit Balance'),
        (CREDIT_OVERDUE,          'Credit Payment Overdue'),
        (CREDIT_SUSPENDED,        'Credit Account Suspended'),
        (CREDIT_UNSUSPENDED,      'Credit Account Reactivated'),
        (NEGOTIATION_OFFER,       'New Negotiation Offer'),
        (NEGOTIATION_COUNTER,     'Negotiation Counter-Offer'),
        (NEGOTIATION_ACCEPTED,    'Offer Accepted'),
        (NEGOTIATION_REJECTED,    'Offer Rejected'),
        (NEGOTIATION_REMINDER,    'Negotiation Expiry Reminder'),
        (NEGOTIATION_EXPIRED,     'Negotiation Expired'),
        (NEGOTIATION_AGREED,      'Price Agreement Reached'),
        (DELIVERY_ASSIGNED,       'Delivery Assigned'),
        (DELIVERY_PICKED_UP,      'Order Picked Up'),
        (DELIVERY_IN_TRANSIT,     'Order In Transit'),
        (DELIVERY_COMPLETED,      'Delivery Completed'),
        (VENDOR_FOLLOWED,         'Vendor Followed'),
        (VENDOR_UNFOLLOWED,       'Vendor Unfollowed'),
        (REFUND_REQUESTED,        'Refund Requested'),
        (REFUND_PROCESSED,        'Refund Processed'),
        (DISPUTE_CREATED,         'Dispute Opened'),
        (DISPUTE_RESOLVED,        'Dispute Resolved'),
        (NEW_ORDER,               'New Order Received'),
        (NEW_FOLLOWER,            'New Follower'),
        (UNFOLLOWED_BY,           'Unfollowed By Customer'),
        (VENDOR_NEGOTIATION_OFFER,    'Offer Received from Buyer'),
        (VENDOR_NEGOTIATION_REMINDER, 'Pending Offer Reminder'),
        (VENDOR_PAYMENT_RECEIVED,     'Payment Received'),
        (VERIFICATION_APPROVED,       'Verification Approved'),
        (VERIFICATION_REJECTED,       'Verification Rejected'),
        (VENDOR_ORDER_CANCELLED,      'Order Cancelled by Customer'),
        (VENDOR_REFUND_REQUESTED,     'Customer Refund Request'),
        (VENDOR_DISPUTE,              'Dispute Filed Against You'),
        (VENDOR_FRAUD_FLAGGED,        'Account Flagged for Review'),
        (VENDOR_FRAUD_CLEARED,        'Fraud Review Cleared'),
        (VENDOR_TIER_ACTIVATED,       'Business Tier Activated'),
        (VENDOR_TIER_EXPIRING,        'Business Tier Expiring Soon'),
        (VENDOR_TIER_EXPIRED,         'Business Tier Expired'),
        (VENDOR_TIER_PAST_DUE,        'Business Tier Payment Overdue'),
        (VENDOR_TIER_CANCELLED,       'Business Tier Cancelled'),
        (VENDOR_LOW_STOCK,            'Product Low Stock'),
        (VENDOR_OUT_OF_STOCK,         'Product Out of Stock'),
        (VENDOR_VETTING_PASSED,       'Vetting Check Passed'),
        (VENDOR_VETTING_FAILED,       'Vetting Check Failed'),
        (VENDOR_VETTING_RESUBMIT,     'Vetting Resubmission Required'),
        (ADMIN_NEW_USER,              'New User Signup'),
        (ADMIN_NEW_BUSINESS,          'New Business Registered'),
        (ADMIN_REFUND_PENDING,        'Refund Needs Approval'),
        (ADMIN_DISPUTE,               'New Dispute Filed'),
        (ADMIN_FRAUD_HIGH,            'High Fraud Risk Detected'),
        (ADMIN_FRAUD_CRITICAL,        'Critical Fraud Risk Detected'),
        (ADMIN_CREDIT_DEFAULTED,      'Credit Default'),
        (ADMIN_VENDOR_PENDING,        'Vendor Awaiting Verification'),
        (ADMIN_VETTING_SUBMITTED,     'Vetting Application Submitted'),
        (ADMIN_PAYMENT_FAILED,        'Payment Transaction Failed'),
        (ADMIN_TIER_PAST_DUE,         'Vendor Tier Payment Overdue'),
    ]

    # ── Categories ───────────────────────────────────────────────
    CAT_ORDER        = 'order'
    CAT_PAYMENT      = 'payment'
    CAT_SUBSCRIPTION = 'subscription'
    CAT_CREDIT       = 'credit'
    CAT_NEGOTIATION  = 'negotiation'
    CAT_DELIVERY     = 'delivery'
    CAT_SOCIAL       = 'social'
    CAT_FRAUD        = 'fraud'
    CAT_ACCOUNT      = 'account'
    CAT_ADMIN        = 'admin'
    CAT_INVENTORY    = 'inventory'

    CATEGORY_CHOICES = [
        (CAT_ORDER,        'Order'),
        (CAT_PAYMENT,      'Payment'),
        (CAT_SUBSCRIPTION, 'Subscription'),
        (CAT_CREDIT,       'Credit'),
        (CAT_NEGOTIATION,  'Negotiation'),
        (CAT_DELIVERY,     'Delivery'),
        (CAT_SOCIAL,       'Social'),
        (CAT_FRAUD,        'Fraud'),
        (CAT_ACCOUNT,      'Account'),
        (CAT_ADMIN,        'Admin'),
        (CAT_INVENTORY,    'Inventory'),
    ]

    # ── Fields ───────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_notifications',
        help_text='User who triggered the action (null for system events)',
    )
    notification_type = models.CharField(max_length=40, choices=NOTIFICATION_TYPE_CHOICES)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(
        default=dict, blank=True,
        help_text='Extra context e.g. {"order_id": "...", "amount": "150.00"}',
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', 'created_at']),
            models.Index(fields=['category', 'notification_type']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f'[{self.notification_type}] -> {self.recipient_id} – {self.title[:50]}'

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])


class NotificationPreference(models.Model):
    """Per-user category toggles. Created automatically on user signup."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
    # Category-level toggles
    order_notifications        = models.BooleanField(default=True)
    payment_notifications      = models.BooleanField(default=True)
    subscription_notifications = models.BooleanField(default=True)
    credit_notifications       = models.BooleanField(default=True)
    negotiation_notifications  = models.BooleanField(default=True)
    delivery_notifications     = models.BooleanField(default=True)
    social_notifications       = models.BooleanField(default=True)
    fraud_notifications        = models.BooleanField(default=True)
    account_notifications      = models.BooleanField(default=True)
    admin_notifications        = models.BooleanField(default=True)
    inventory_notifications    = models.BooleanField(default=True)
    # Channel toggles
    in_app_enabled = models.BooleanField(default=True)
    push_enabled   = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'

    def __str__(self):
        return f'Preferences for {self.user_id}'

    # Map category string to the preference field name
    CATEGORY_FIELD_MAP = {
        'order':        'order_notifications',
        'payment':      'payment_notifications',
        'subscription': 'subscription_notifications',
        'credit':       'credit_notifications',
        'negotiation':  'negotiation_notifications',
        'delivery':     'delivery_notifications',
        'social':       'social_notifications',
        'fraud':        'fraud_notifications',
        'account':      'account_notifications',
        'admin':        'admin_notifications',
        'inventory':    'inventory_notifications',
    }

    def is_enabled(self, category: str) -> bool:
        field = self.CATEGORY_FIELD_MAP.get(category, 'account_notifications')
        return getattr(self, field, True) and self.in_app_enabled
