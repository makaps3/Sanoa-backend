"""
Serializers for the Credit System (Buy Now, Pay Later).
"""
from decimal import Decimal
from datetime import timedelta

from rest_framework import serializers
from django.utils import timezone

from .models import CreditAccount, CreditPurchase, CreditRepayment
from business.models import BusinessFollower
from orders.models import Order
from subscriptions.models import Subscription


# ── Account ──────────────────────────────────────────────────

class CreditAccountSerializer(serializers.ModelSerializer):
    """Read-only view of a customer's credit account."""

    available_credit = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_owed = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    subscription_plan = serializers.CharField(
        source='subscription.plan.name', read_only=True, default=None,
    )
    subscription_start_date = serializers.DateTimeField(
        source='subscription.current_period_start', read_only=True, default=None,
    )
    next_billing_date = serializers.DateTimeField(
        source='subscription.current_period_end', read_only=True, default=None,
    )
    repayment_days = serializers.IntegerField(
        source='subscription.plan.repayment_days', read_only=True, default=None,
    )
    grace_period_days = serializers.IntegerField(
        source='subscription.plan.grace_period_days', read_only=True, default=None,
    )
    late_penalty_percent = serializers.DecimalField(
        source='subscription.plan.late_payment_penalty_percent',
        max_digits=5, decimal_places=2, read_only=True, default=None,
    )
    is_user_suspended = serializers.BooleanField(source='user.is_suspended', read_only=True)
    overdue_purchases_count = serializers.SerializerMethodField()

    class Meta:
        model = CreditAccount
        fields = [
            'id', 'user_email', 'status', 'credit_limit', 'current_balance',
            'available_credit', 'total_penalties', 'total_owed',
            'subscription_plan', 'subscription_start_date', 'next_billing_date',
            'repayment_days', 'grace_period_days', 'late_penalty_percent',
            'is_user_suspended', 'overdue_purchases_count',
            'suspended_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_overdue_purchases_count(self, obj):
        count = 0
        for p in obj.purchases.filter(status__in=('active', 'defaulted')):
            if p.is_overdue:
                count += 1
        return count


class CreditAccountCreateSerializer(serializers.Serializer):
    """Create a credit account for the authenticated customer."""

    def validate(self, data):
        user = self.context['request'].user

        if user.user_type != 'customer':
            raise serializers.ValidationError(
                'Only customers can create a credit account.'
            )

        if CreditAccount.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                'You already have a credit account.'
            )

        subscription = getattr(user, 'subscription', None)
        if subscription is None or not subscription.is_active:
            raise serializers.ValidationError(
                'You must have an active subscription to create a credit account.'
            )

        data['subscription'] = subscription
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        subscription = validated_data['subscription']

        account = CreditAccount.objects.create(
            user=user,
            subscription=subscription,
            credit_limit=subscription.plan.credit_limit,
            current_balance=0,
        )
        return account


# ── Eligibility ──────────────────────────────────────────────

class CreditEligibilitySerializer(serializers.Serializer):
    """Check if a user is eligible for credit purchases with a specific vendor."""

    vendor_id = serializers.UUIDField(help_text='VendorProfile id of the vendor to check eligibility for')

    MIN_VENDOR_PURCHASES = 3

    def validate(self, data):
        from business.models import VendorProfile
        try:
            vendor_profile = VendorProfile.objects.select_related('user').get(
                id=data['vendor_id']
            )
        except VendorProfile.DoesNotExist:
            raise serializers.ValidationError({'vendor_id': 'Vendor not found.'})

        data['vendor'] = vendor_profile
        return data

    def check_eligibility(self, user, vendor):
        """Return a dict with each requirement's pass/fail status.

        `vendor` is a VendorProfile; BusinessFollower still FKs to User so
        we compare through vendor.user for that relation.
        """

        # 1. Purchase history (OrderItem.vendor is VendorProfile).
        #    Only fully delivered orders count toward the minimum.
        vendor_purchase_count = Order.objects.filter(
            user=user, items__vendor=vendor,
            status__in=('delivered', 'completed'),
        ).distinct().count()
        has_min_purchases = vendor_purchase_count >= self.MIN_VENDOR_PURCHASES

        # 2. Following — BusinessFollower.vendor is still a User FK
        is_following = BusinessFollower.objects.filter(
            user=user, vendor=vendor.user,
        ).exists()

        # 3. Subscription
        subscription = getattr(user, 'subscription', None)
        has_active_subscription = subscription is not None and subscription.is_active
        subscription_plan = subscription.plan.name if subscription else None
        credit_limit = subscription.plan.credit_limit if has_active_subscription else Decimal('0.00')

        # 4. Account status
        credit_account = getattr(user, 'debit_account', None)
        has_credit_account = credit_account is not None
        account_is_active = has_credit_account and credit_account.is_active
        is_user_suspended = getattr(user, 'is_suspended', False)

        # 5. Overall
        is_eligible = (
            has_min_purchases
            and is_following
            and has_active_subscription
            and account_is_active
            and not is_user_suspended
        )

        return {
            'is_eligible': is_eligible,
            'vendor_purchase_count': vendor_purchase_count,
            'has_min_purchases': has_min_purchases,
            'min_purchases_required': self.MIN_VENDOR_PURCHASES,
            'is_following_vendor': is_following,
            'has_active_subscription': has_active_subscription,
            'subscription_plan': subscription_plan,
            'has_credit_account': has_credit_account,
            'account_is_active': account_is_active,
            'is_user_suspended': is_user_suspended,
            'credit_limit': str(credit_limit),
            'available_credit': str(credit_account.available_credit) if credit_account else '0.00',
            'min_deposit_percent': str(CreditAccount.MIN_DEPOSIT_PERCENT),
        }


# ── Purchase ─────────────────────────────────────────────────

class CreditPurchaseCreateSerializer(serializers.Serializer):
    """
    Create a credit purchase (buy now, pay later).
    Validates all eligibility requirements and minimum 10% deposit.
    """

    vendor_id = serializers.UUIDField(help_text='VendorProfile id (store) to buy on credit from')
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    due_date = serializers.DateField(
        required=False,
        help_text='Defaults to plan repayment_days from now',
    )
    order_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        user = self.context['request'].user
        total = data['total_amount']
        deposit = data['deposit_amount']

        # Suspended users cannot make new credit purchases
        if getattr(user, 'is_suspended', False):
            raise serializers.ValidationError(
                'Your account is suspended due to overdue payments. '
                'Please settle your outstanding balance before making new credit purchases.'
            )

        # Validate vendor (now a VendorProfile, not a User)
        from business.models import VendorProfile
        try:
            vendor_profile = VendorProfile.objects.select_related('user').get(
                id=data['vendor_id']
            )
        except VendorProfile.DoesNotExist:
            raise serializers.ValidationError({'vendor_id': 'Vendor not found.'})
        data['vendor'] = vendor_profile

        # Credit account check
        try:
            credit_account = CreditAccount.objects.get(user=user)
        except CreditAccount.DoesNotExist:
            raise serializers.ValidationError(
                'You must create a credit account before making a credit purchase.'
            )

        if not credit_account.is_active:
            raise serializers.ValidationError(
                'Your credit account is suspended or closed. '
                'Please settle outstanding balances first.'
            )

        # Purchase history — only fully delivered/completed orders count
        vendor_purchase_count = Order.objects.filter(
            user=user, items__vendor=vendor_profile,
            status__in=('delivered', 'completed'),
        ).distinct().count()
        if vendor_purchase_count < CreditEligibilitySerializer.MIN_VENDOR_PURCHASES:
            raise serializers.ValidationError(
                f'You must have at least {CreditEligibilitySerializer.MIN_VENDOR_PURCHASES} '
                f'completed orders with this vendor. You have {vendor_purchase_count}.'
            )

        # Following — BusinessFollower.vendor is still a User FK
        if not BusinessFollower.objects.filter(user=user, vendor=vendor_profile.user).exists():
            raise serializers.ValidationError(
                'You must follow this business before you can buy on credit.'
            )

        # Subscription
        subscription = getattr(user, 'subscription', None)
        if subscription is None or not subscription.is_active:
            raise serializers.ValidationError(
                'You must have an active subscription to buy on credit.'
            )

        # Sync credit limit from current plan
        credit_account.credit_limit = subscription.plan.credit_limit
        credit_account.save(update_fields=['credit_limit', 'updated_at'])

        # Deposit check (minimum from plan or 10%)
        min_deposit_pct = max(subscription.plan.deposit_percent, CreditAccount.MIN_DEPOSIT_PERCENT)
        min_deposit = total * (min_deposit_pct / Decimal('100'))
        if deposit < min_deposit:
            raise serializers.ValidationError({
                'deposit_amount': (
                    f'Minimum deposit is {min_deposit_pct}% of total '
                    f'(R{min_deposit:.2f}). You provided R{deposit:.2f}.'
                )
            })

        # ── Hard credit-limit cap ─────────────────────────────────
        #
        # Policy: a customer can never buy an item on BNPL whose total
        # exceeds their available credit, regardless of how big a
        # deposit they're willing to pay. If they want an R800 item and
        # only have R200 of available credit, BNPL is off the table for
        # that purchase — they need to pay in full via Pay Now or
        # choose a cheaper item.
        if total > credit_account.available_credit:
            raise serializers.ValidationError(
                f'This item costs R{total:.2f} but your available credit '
                f'is only R{credit_account.available_credit:.2f}. '
                f'You can\'t buy items priced above your credit limit '
                f'with Buy Now Pay Later.'
            )

        remaining = total - deposit

        # Max items on credit check
        active_count = credit_account.purchases.filter(status__in=('active', 'pending')).count()
        max_items = subscription.plan.max_items_on_credit
        if active_count >= max_items:
            raise serializers.ValidationError(
                f'You can only have {max_items} active credit purchase(s) at a time. '
                f'You currently have {active_count}.'
            )

        data['credit_account'] = credit_account
        data['remaining'] = remaining
        data['subscription'] = subscription
        return data

    def create(self, validated_data):
        credit_account = validated_data['credit_account']
        remaining = validated_data['remaining']
        subscription = validated_data['subscription']
        plan = subscription.plan

        # Calculate due date from plan repayment_days
        repayment_days = plan.repayment_days or 30
        due_date = validated_data.get('due_date') or (
            timezone.now().date() + timedelta(days=repayment_days)
        )

        # Calculate grace end date
        grace_days = plan.grace_period_days or 3
        grace_end_date = due_date + timedelta(days=grace_days)

        purchase = CreditPurchase.objects.create(
            credit_account=credit_account,
            vendor=validated_data['vendor'],
            total_amount=validated_data['total_amount'],
            deposit_amount=validated_data['deposit_amount'],
            remaining_amount=remaining,
            due_date=due_date,
            grace_end_date=grace_end_date,
            status='active',
        )

        # Link order if provided
        if validated_data.get('order_id'):
            from orders.models import Order
            try:
                order = Order.objects.get(
                    id=validated_data['order_id'],
                    user=self.context['request'].user,
                )
                purchase.order = order
                purchase.save(update_fields=['order_id'])
            except Order.DoesNotExist:
                pass

        # Update account balance
        credit_account.current_balance += remaining
        credit_account.save(update_fields=['current_balance', 'updated_at'])

        return purchase


class CreditPurchaseSerializer(serializers.ModelSerializer):
    """Read-only serializer for viewing credit purchases."""

    outstanding_balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    outstanding_penalty = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_outstanding = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_fully_paid = serializers.BooleanField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    is_grace_expired = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    deposit_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    vendor_email = serializers.CharField(source='vendor.user.email', read_only=True)
    vendor_info = serializers.SerializerMethodField()
    repayments = serializers.SerializerMethodField()

    class Meta:
        model = CreditPurchase
        fields = [
            'id', 'vendor', 'vendor_email', 'vendor_info', 'order',
            'total_amount', 'deposit_amount', 'deposit_percentage',
            'remaining_amount', 'amount_paid', 'outstanding_balance',
            'penalty_amount', 'penalty_paid', 'outstanding_penalty',
            'total_outstanding',
            'status', 'is_fully_paid', 'is_overdue', 'is_grace_expired',
            'days_overdue', 'due_date', 'grace_end_date',
            'paid_at', 'defaulted_at', 'created_at', 'updated_at',
            'repayments',
        ]
        read_only_fields = fields

    def get_vendor_info(self, obj):
        from business.utils import build_vendor_info
        return build_vendor_info(obj.vendor.user, self.context.get('request'))

    def get_repayments(self, obj):
        return CreditRepaymentSerializer(obj.repayments.all(), many=True).data


# ── Repayment ────────────────────────────────────────────────

class CreditRepaymentSerializer(serializers.ModelSerializer):
    """Read-only serializer for repayments."""

    class Meta:
        model = CreditRepayment
        fields = [
            'id', 'amount', 'principal_portion', 'penalty_portion',
            'payment_method', 'repayment_type', 'reference',
            'paystack_transaction_id', 'created_at',
        ]
        read_only_fields = fields


class CreditRepaymentCreateSerializer(serializers.Serializer):
    """
    Create a repayment towards a credit purchase.
    Payments are applied to PENALTIES first, then to the principal balance.
    If all overdue balances are cleared, the user's suspension is automatically lifted.
    """

    purchase_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.ChoiceField(
        choices=CreditRepayment.PAYMENT_METHOD_CHOICES, default='card',
    )
    reference = serializers.CharField(max_length=200, required=False, default='')
    paystack_transaction_id = serializers.CharField(max_length=200, required=False, default='')

    def validate(self, data):
        user = self.context['request'].user

        try:
            purchase = CreditPurchase.objects.select_related(
                'credit_account', 'credit_account__user',
            ).get(
                id=data['purchase_id'],
                credit_account__user=user,
            )
        except CreditPurchase.DoesNotExist:
            raise serializers.ValidationError({'purchase_id': 'Purchase not found.'})

        if purchase.is_fully_paid:
            raise serializers.ValidationError('This purchase is already fully paid.')

        if purchase.status not in ('active', 'defaulted'):
            raise serializers.ValidationError('Cannot make repayments on this purchase.')

        if data['amount'] > purchase.total_outstanding:
            raise serializers.ValidationError({
                'amount': (
                    f'Amount exceeds total outstanding of R{purchase.total_outstanding:.2f} '
                    f'(principal: R{purchase.outstanding_balance:.2f}, '
                    f'penalty: R{purchase.outstanding_penalty:.2f}).'
                )
            })

        if data['amount'] <= 0:
            raise serializers.ValidationError({'amount': 'Amount must be greater than zero.'})

        data['purchase'] = purchase
        return data

    def create(self, validated_data):
        purchase = validated_data['purchase']
        amount = validated_data['amount']
        remaining = amount

        # Apply payment to penalties first, then principal
        penalty_portion = Decimal('0.00')
        principal_portion = Decimal('0.00')

        if purchase.outstanding_penalty > 0:
            penalty_payment = min(remaining, purchase.outstanding_penalty)
            penalty_portion = penalty_payment
            remaining -= penalty_payment

        if remaining > 0:
            principal_portion = min(remaining, purchase.outstanding_balance)

        # Determine repayment type
        if penalty_portion > 0 and principal_portion > 0:
            repayment_type = 'mixed'
        elif penalty_portion > 0:
            repayment_type = 'penalty'
        else:
            repayment_type = 'principal'

        repayment = CreditRepayment.objects.create(
            purchase=purchase,
            amount=amount,
            principal_portion=principal_portion,
            penalty_portion=penalty_portion,
            payment_method=validated_data['payment_method'],
            repayment_type=repayment_type,
            reference=validated_data.get('reference', ''),
            paystack_transaction_id=validated_data.get('paystack_transaction_id', ''),
        )

        # Update purchase amounts
        purchase.amount_paid += principal_portion
        purchase.penalty_paid += penalty_portion

        if purchase.is_fully_paid:
            purchase.status = 'paid'
            purchase.paid_at = timezone.now()

        purchase.save(update_fields=[
            'amount_paid', 'penalty_paid', 'status', 'paid_at', 'updated_at',
        ])

        # Update credit account balance
        account = purchase.credit_account
        account.current_balance -= principal_portion
        if account.current_balance < 0:
            account.current_balance = Decimal('0.00')
        account.total_penalties -= penalty_portion
        if account.total_penalties < 0:
            account.total_penalties = Decimal('0.00')
        account.save(update_fields=['current_balance', 'total_penalties', 'updated_at'])

        # Auto-unsuspend if all overdue balances are cleared
        if account.user.is_suspended:
            account.unsuspend()

        return repayment
