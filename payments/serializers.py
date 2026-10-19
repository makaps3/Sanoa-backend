"""
Serializers for the Paystack-integrated payments app.
"""
from rest_framework import serializers
from .models import (
    PaystackSubaccount, TransactionSplit, TransactionSplitSubaccount,
    Transaction, Refund, Dispute, PaymentLog,
)


# ── Subaccount ───────────────────────────────────────────────

class PaystackSubaccountSerializer(serializers.ModelSerializer):
    vendor_email = serializers.CharField(source='vendor.user.email', read_only=True)
    vendor_info = serializers.SerializerMethodField()
    # Surface the PlatformFee that drives this subaccount's commission
    # so the vendor app can show "X% commission applied from your
    # business category" without a second round-trip.
    platform_fee_business_type = serializers.CharField(
        source='platform_fee.business_type', read_only=True,
    )
    platform_fee_business_type_display = serializers.CharField(
        source='platform_fee.get_business_type_display', read_only=True,
    )

    class Meta:
        model = PaystackSubaccount
        fields = [
            'id', 'vendor', 'vendor_email', 'vendor_info', 'subaccount_code',
            'business_name', 'settlement_bank', 'account_number',
            'bank_name', 'account_name', 'percentage_charge',
            'platform_fee', 'platform_fee_business_type',
            'platform_fee_business_type_display',
            'flat_charge', 'primary_contact_email', 'is_active',
            'metadata', 'created_at', 'updated_at',
        ]
        # `percentage_charge` is read-only now — auto-derived from the
        # linked PlatformFee at subaccount creation.
        read_only_fields = [
            'id', 'subaccount_code', 'paystack_subaccount_id',
            'percentage_charge', 'platform_fee',
            'platform_fee_business_type',
            'platform_fee_business_type_display',
            'account_name', 'created_at', 'updated_at',
        ]

    def get_vendor_info(self, obj):
        # obj.vendor is a VendorProfile; build_vendor_info wants the User.
        from business.utils import build_vendor_info
        return build_vendor_info(obj.vendor.user, self.context.get('request'))


class PaystackSubaccountCreateSerializer(serializers.Serializer):
    """Create a Paystack subaccount for the authenticated vendor.

    `percentage_charge` is no longer accepted — the commission comes
    from the PlatformFee row matching the vendor's business_category.
    """
    business_name = serializers.CharField(max_length=255)
    settlement_bank = serializers.CharField(
        max_length=100,
        help_text='Bank code from Paystack bank list',
    )
    account_number = serializers.CharField(max_length=20)
    primary_contact_email = serializers.EmailField(required=False, default='')


# ── Transaction Split ────────────────────────────────────────

class TransactionSplitSubaccountSerializer(serializers.ModelSerializer):
    subaccount_code = serializers.CharField(
        source='subaccount.subaccount_code', read_only=True,
    )
    business_name = serializers.CharField(
        source='subaccount.business_name', read_only=True,
    )

    class Meta:
        model = TransactionSplitSubaccount
        fields = ['id', 'subaccount', 'subaccount_code', 'business_name', 'share']


class TransactionSplitSerializer(serializers.ModelSerializer):
    subaccounts = TransactionSplitSubaccountSerializer(many=True, read_only=True)

    class Meta:
        model = TransactionSplit
        fields = [
            'id', 'name', 'paystack_split_code', 'split_type',
            'currency', 'bearer_type', 'bearer_subaccount',
            'is_active', 'subaccounts', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'paystack_split_code', 'paystack_split_id',
            'created_at', 'updated_at',
        ]


class TransactionSplitCreateSerializer(serializers.Serializer):
    """Create a transaction split on Paystack."""
    name = serializers.CharField(max_length=200)
    split_type = serializers.ChoiceField(choices=['percentage', 'flat'])
    currency = serializers.CharField(max_length=3, default='ZAR')
    bearer_type = serializers.ChoiceField(
        choices=['subaccount', 'account', 'all-proportional', 'all'],
        default='account',
    )
    bearer_subaccount = serializers.CharField(max_length=100, required=False, default='')
    subaccounts = serializers.ListField(
        child=serializers.DictField(),
        help_text='List of {subaccount: "<code>", share: <int>}',
    )


# ── Transaction ──────────────────────────────────────────────

class TransactionSerializer(serializers.ModelSerializer):
    """Read-only transaction details."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    vendor_uuid = serializers.UUIDField(source='vendor.id', read_only=True, allow_null=True)
    vendor_name = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()
    net_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    # Vendor-facing revenue for this transaction: items subtotal − commission.
    # `amount` is the gross the customer paid (incl. delivery + service fees,
    # which never settle to the vendor), so the vendor app should display
    # `vendor_payout` as the transaction's revenue.
    vendor_payout = serializers.SerializerMethodField()
    commission_amount = serializers.SerializerMethodField()
    items_subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'id', 'reference', 'payment_intent',
            'order', 'order_number',
            'subscription', 'vendor_tier_subscription', 'credit_purchase',
            'user', 'user_email',
            'vendor', 'vendor_uuid', 'vendor_name',
            'amount', 'currency', 'paystack_fees', 'net_amount',
            'items_subtotal', 'commission_amount', 'vendor_payout',
            'status', 'channel', 'gateway_response',
            'authorization_url', 'access_code',
            'card_type', 'last4', 'bank',
            'subaccount', 'split',
            'ip_address', 'metadata',
            'paid_at', 'created_at', 'updated_at',
            'failure_reason',
        ]
        read_only_fields = fields

    def get_order_number(self, obj):
        return obj.order.order_number if obj.order else None

    @staticmethod
    def _linked_order(obj):
        """The order behind this payment — retail OR restaurant.

        Restaurant checkouts live in their own table, so reading only
        `obj.order` returned null for every vendor figure and the apps fell
        back to the customer-paid gross (which includes delivery + service
        fees the vendor never receives).
        """
        if obj.order_id:
            return obj.order
        if getattr(obj, 'restaurant_order_id', None):
            return obj.restaurant_order
        return None

    def get_vendor_payout(self, obj):
        o = self._linked_order(obj)
        return str(o.vendor_payout) if o is not None else None

    def get_commission_amount(self, obj):
        o = self._linked_order(obj)
        return str(o.commission_amount) if o is not None else None

    def get_items_subtotal(self, obj):
        o = self._linked_order(obj)
        return str(o.subtotal) if o is not None else None

    def get_vendor_name(self, obj):
        if obj.vendor:
            return obj.vendor.trading_name or obj.vendor.name or str(obj.vendor)
        return None


class TransactionInitializeSerializer(serializers.Serializer):
    """Initialize a Paystack transaction."""
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2,
        required=False,
        allow_null=True,
        default=None,
        help_text=(
            'Amount in rands (e.g. 150.00). '
            'Optional for order_payment — the backend derives the amount from '
            'order.total_amount when omitted or when an order_id is supplied, '
            'ensuring the delivery fee is always included.'
        ),
    )
    order_id = serializers.UUIDField(
        required=False,
        help_text=(
            'UUID of the related entity. Resolved based on payment_intent: '
            'Order (order_payment), Subscription (subscription_payment), '
            'VendorTierSubscription (tier_payment), or CreditPurchase (credit_payment).'
        ),
    )
    payment_intent = serializers.ChoiceField(
        choices=[
            'order_payment', 'subscription_payment', 'tier_payment',
            'credit_payment', 'deposit',
        ],
        default='order_payment',
    )
    callback_url = serializers.URLField(
        required=False,
        help_text='URL to redirect to after payment',
    )
    channels = serializers.ListField(
        child=serializers.ChoiceField(
            choices=['card', 'bank', 'ussd', 'qr', 'mobile_money', 'bank_transfer', 'eft'],
        ),
        required=False,
        help_text='Allowed payment channels',
    )
    subaccount_code = serializers.CharField(
        required=False,
        help_text='Subaccount code for split payment (ignored for subscription_payment/tier_payment)',
    )
    split_code = serializers.CharField(
        required=False,
        help_text='Split code for multi-way split (ignored for subscription_payment/tier_payment)',
    )
    delivery_fare_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        help_text='ID of the DeliveryFare for this order (stored in metadata, delivery orders only).',
    )
    metadata = serializers.DictField(required=False, default=dict)

    def validate(self, attrs):
        payment_intent = attrs.get('payment_intent', 'order_payment')

        if payment_intent in ('subscription_payment', 'tier_payment'):
            # Strip fields not applicable to subscription/tier payments
            attrs.pop('subaccount_code', None)
            attrs.pop('split_code', None)
            attrs['metadata'] = {}

        if payment_intent == 'credit_payment' and not attrs.get('order_id'):
            raise serializers.ValidationError({
                'order_id': 'CreditPurchase UUID is required for credit_payment.',
            })

        # For non-order_payment intents, amount is always required on the client
        if payment_intent != 'order_payment' and not attrs.get('amount'):
            raise serializers.ValidationError({
                'amount': 'Amount is required for this payment intent.',
            })

        return attrs


class ChargeAuthorizationSerializer(serializers.Serializer):
    """Charge a returning customer using their saved card."""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    authorization_code = serializers.CharField(max_length=200)
    order_id = serializers.UUIDField(required=False)
    payment_intent = serializers.ChoiceField(
        choices=[
            'order_payment', 'subscription_payment', 'tier_payment',
            'credit_payment', 'deposit',
        ],
        default='order_payment',
    )
    subaccount_code = serializers.CharField(required=False)
    split_code = serializers.CharField(required=False)
    metadata = serializers.DictField(required=False, default=dict)


# ── Refund ───────────────────────────────────────────────────

def _order_number_of(obj):
    """Order number behind a refund or dispute — retail OR restaurant."""
    order = getattr(obj, 'order', None) or getattr(obj, 'restaurant_order', None)
    if order is None:
        txn = getattr(obj, 'transaction', None)
        order = getattr(txn, 'order', None) or getattr(txn, 'restaurant_order', None)
    return getattr(order, 'order_number', '') if order is not None else ''


class RefundSerializer(serializers.ModelSerializer):
    transaction_reference = serializers.CharField(
        source='transaction.reference', read_only=True,
    )
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Refund
        fields = [
            'id', 'paystack_refund_id',
            'transaction', 'transaction_reference',
            'order', 'restaurant_order', 'order_number',
            'vendor', 'vendor_name',
            'user', 'user_email', 'user_name',
            'amount', 'currency', 'reason', 'reason_display',
            'customer_note', 'merchant_note',
            'status', 'status_display', 'approved_by', 'admin_notes', 'approved_at',
            'failure_reason', 'processed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'paystack_refund_id', 'user', 'status',
            'approved_by', 'approved_at', 'failure_reason',
            'processed_at', 'created_at', 'updated_at',
        ]

    def get_user_name(self, obj):
        u = obj.user
        full = f'{u.first_name} {u.last_name}'.strip() if u else ''
        return full or (getattr(u, 'email', '') if u else '')

    def get_vendor_name(self, obj):
        v = obj.vendor or getattr(obj.transaction, 'vendor', None)
        if v is None:
            return ''
        return getattr(v, 'trading_name', '') or getattr(v, 'name', '')

    def get_order_number(self, obj):
        return _order_number_of(obj)


class RefundCreateSerializer(serializers.Serializer):
    """Request a refund on a transaction."""
    transaction_id = serializers.UUIDField(help_text='UUID of the transaction to refund')
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        help_text='Amount to refund (defaults to full transaction amount)',
    )
    reason = serializers.ChoiceField(
        choices=[c[0] for c in Refund.REFUND_REASON_CHOICES],
        default='customer_request',
    )
    customer_note = serializers.CharField(required=False, default='')
    merchant_note = serializers.CharField(required=False, default='')


# ── Dispute ──────────────────────────────────────────────────

class DisputeSerializer(serializers.ModelSerializer):
    transaction_reference = serializers.CharField(
        source='transaction.reference', read_only=True,
    )
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    vendor_name = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    refunds = serializers.SerializerMethodField()

    class Meta:
        model = Dispute
        fields = [
            'id', 'paystack_dispute_id', 'source',
            'transaction', 'transaction_reference',
            'order', 'restaurant_order', 'order_number',
            'vendor', 'vendor_name',
            'user', 'user_email', 'user_name',
            'amount', 'currency', 'status', 'status_display',
            'category', 'category_display',
            'resolution', 'message', 'merchant_response', 'vendor_responded_at',
            'resolved_by', 'resolution_note',
            'evidence', 'attachments', 'refunds',
            'due_at', 'resolved_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'paystack_dispute_id', 'source', 'transaction', 'user',
            'amount', 'currency', 'status', 'category',
            'due_at', 'resolved_at', 'created_at', 'updated_at',
        ]

    def get_user_name(self, obj):
        u = obj.user
        full = f'{u.first_name} {u.last_name}'.strip() if u else ''
        return full or (getattr(u, 'email', '') if u else '')

    def get_vendor_name(self, obj):
        v = obj.vendor or getattr(obj.transaction, 'vendor', None)
        if v is None:
            return ''
        return getattr(v, 'trading_name', '') or getattr(v, 'name', '')

    def get_order_number(self, obj):
        return _order_number_of(obj)

    def get_refunds(self, obj):
        """Refunds raised off the back of this dispute, so every screen can
        show what the customer actually got back."""
        return [
            {
                'id': str(r.id),
                'amount': str(r.amount),
                'status': r.status,
                'created_at': r.created_at.isoformat() if r.created_at else None,
            }
            for r in obj.transaction.refunds.all()
        ]


class DisputeCreateSerializer(serializers.Serializer):
    """A customer raising a dispute against their own paid transaction."""
    transaction_id = serializers.UUIDField()
    category = serializers.ChoiceField(
        choices=[c[0] for c in Dispute.CATEGORY_CHOICES], default='general',
    )
    message = serializers.CharField(
        max_length=4000,
        error_messages={
            'blank': 'Please describe what went wrong so we can look into it.',
        },
    )
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        help_text='Amount in dispute (defaults to the full transaction).',
    )
    attachments = serializers.ListField(
        child=serializers.URLField(), required=False, default=list,
        help_text='Links to photos or documents supporting the claim.',
    )


class DisputeRespondSerializer(serializers.Serializer):
    """Vendor (or admin) replying to a dispute."""
    merchant_response = serializers.CharField(
        max_length=4000,
        error_messages={
            'blank': 'Please write a response before submitting.',
        },
    )
    attachments = serializers.ListField(
        child=serializers.URLField(), required=False, default=list,
    )


class RefundRejectSerializer(serializers.Serializer):
    """Admin declining a refund request."""
    admin_notes = serializers.CharField(
        max_length=2000,
        error_messages={
            'blank': 'Please tell the customer why the refund was declined.',
        },
    )


class DisputeResolveSerializer(serializers.Serializer):
    """Resolve a dispute."""
    resolution = serializers.ChoiceField(choices=['merchant-accepted', 'declined'])
    message = serializers.CharField()
    refund_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        help_text='Amount to refund if accepting the dispute',
    )
    upload_url = serializers.URLField(required=False)


class DisputeEvidenceSerializer(serializers.Serializer):
    """Add evidence to a dispute."""
    customer_email = serializers.EmailField(required=False)
    customer_name = serializers.CharField(required=False)
    customer_phone = serializers.CharField(required=False)
    service_details = serializers.CharField(required=False)
    delivery_address = serializers.CharField(required=False)
    description = serializers.CharField(required=False)


# ── Payment Log ──────────────────────────────────────────────

class PaymentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentLog
        fields = [
            'id', 'transaction', 'refund', 'dispute',
            'log_type', 'message', 'http_status_code',
            'ip_address', 'created_at',
        ]
        read_only_fields = fields


# ── Banks ────────────────────────────────────────────────────

class BankListSerializer(serializers.Serializer):
    """Paystack bank list response."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    code = serializers.CharField()
    country = serializers.CharField()
    currency = serializers.CharField()
    type = serializers.CharField()


class ResolveAccountSerializer(serializers.Serializer):
    """Resolve bank account number."""
    account_number = serializers.CharField(max_length=20)
    bank_code = serializers.CharField(max_length=20)
