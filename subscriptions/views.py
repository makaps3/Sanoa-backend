"""
Views for the Subscriptions app.
Integrated with Paystack for payment processing.
"""
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from .models import Plan, Subscription
from .serializers import (
    PlanSerializer, SubscriptionSerializer, SubscriptionCreateSerializer,
    AdminPlanSerializer, AdminSubscriptionSerializer, AdminSubscriptionAssignSerializer,
)
from core.permissions import IsPlatformAdmin

User = get_user_model()


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve available subscription plans."""

    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Plan.objects.filter(is_active=True)
    lookup_field = 'slug'

    def list(self, request, *args, **kwargs):
        """Auto-sync any un-synced plans to Paystack before listing."""
        unsynced = Plan.objects.filter(is_active=True, paystack_plan_code__isnull=True)
        if unsynced.exists():
            from .serializers import SubscriptionCreateSerializer
            for plan in unsynced:
                SubscriptionCreateSerializer._sync_plan_to_paystack(plan)
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='sync-paystack',
            permission_classes=[permissions.IsAuthenticated])
    def sync_paystack(self, request, slug=None):
        """Sync this plan to Paystack (creates or updates the Paystack plan)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Admin only.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        plan = self.get_object()
        from .serializers import SubscriptionCreateSerializer
        plan = SubscriptionCreateSerializer._sync_plan_to_paystack(plan)

        if plan.paystack_plan_code:
            return Response({
                'message': 'Plan synced to Paystack.',
                'paystack_plan_code': plan.paystack_plan_code,
            })
        return Response(
            {'error': 'Failed to sync plan to Paystack.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class SubscriptionViewSet(viewsets.GenericViewSet):
    """Manage user subscriptions with Paystack payment."""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='my-subscription')
    def my_subscription(self, request):
        """Get current subscription details.

        Inline enforcement: if the subscription's billing period has
        lapsed but Paystack hasn't renewed it (or the user cancelled
        their card), we downgrade right here so the customer sees the
        truth on first read — no waiting on the daily Celery task.

        `was_downgraded` is set to True when the downgrade was applied
        *during this request*. The frontend uses it to show a one-time
        "Your plan expired — you're on Free now" banner.
        """
        subscription = getattr(request.user, 'subscription', None)
        if subscription is None:
            plans = Plan.objects.filter(is_active=True)
            return Response({
                'status': 'none',
                'message': 'No active subscription.',
                'available_plans': PlanSerializer(plans, many=True).data,
            })

        was_downgraded = False
        if subscription.is_overdue and subscription.status != 'expired':
            was_downgraded = subscription.expire_and_downgrade(
                reason='Inline enforcement on /my-subscription/',
            )

        data = SubscriptionSerializer(subscription).data
        data['was_downgraded'] = was_downgraded
        data['is_downgraded'] = subscription.status == 'expired'
        return Response(data)

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """
        Subscribe to a plan.
        Returns a Paystack authorization_url for the customer to complete payment.
        Body: {"plan_id": "<uuid>", "callback_url": "<optional>"}
        """
        serializer = SubscriptionCreateSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()

        response_data = SubscriptionSerializer(subscription).data
        # Include Paystack payment URL for the client to redirect to
        paystack_data = serializer.context.get('paystack_data', {})
        if paystack_data:
            response_data['paystack'] = paystack_data

        return Response(response_data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def cancel(self, request):
        """Cancel current subscription (also disables on Paystack)."""
        subscription = getattr(request.user, 'subscription', None)
        if subscription is None or subscription.status not in ('active', 'trialing', 'pending', 'past_due'):
            return Response(
                {'error': 'No active subscription to cancel.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from subscriptions.billing import expire_subscription
        expire_subscription(subscription, reason='Subscriber cancelled', force=True, status='cancelled')
        return Response(SubscriptionSerializer(subscription).data)

    @action(detail=False, methods=['get'], url_path='manage-card')
    def manage_card(self, request):
        """Get a Paystack link to update the subscription card."""
        subscription = getattr(request.user, 'subscription', None)
        if not subscription or not subscription.paystack_subscription_code:
            return Response(
                {'error': 'No active Paystack subscription found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from payments.paystack import paystack_api
        result = paystack_api.generate_subscription_link(
            subscription.paystack_subscription_code,
        )

        if not result.get('status'):
            return Response(
                {'error': result.get('message', 'Failed to generate link.')},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({'link': result['data'].get('link', '')})


# ═══════════════════════════════════════════════════════════════
# Admin — Customer Plans & Subscriptions
# ═══════════════════════════════════════════════════════════════

class AdminPlanViewSet(viewsets.ModelViewSet):
    """
    Full CRUD on Plan for platform admins.
    GET    /api/subscriptions/admin/plans/           — list all (incl. inactive)
    POST   /api/subscriptions/admin/plans/           — create plan
    GET    /api/subscriptions/admin/plans/<id>/      — retrieve
    PUT    /api/subscriptions/admin/plans/<id>/      — full update
    PATCH  /api/subscriptions/admin/plans/<id>/      — partial update
    DELETE /api/subscriptions/admin/plans/<id>/      — delete
    POST   /api/subscriptions/admin/plans/<id>/toggle-active/  — toggle is_active
    POST   /api/subscriptions/admin/plans/<id>/sync-paystack/  — sync to Paystack
    """
    serializer_class = AdminPlanSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = Plan.objects.all().order_by('sort_order', 'price')

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        plan = self.get_object()
        plan.is_active = not plan.is_active
        plan.save(update_fields=['is_active', 'updated_at'])
        return Response(AdminPlanSerializer(plan).data)

    @action(detail=True, methods=['post'], url_path='sync-paystack')
    def sync_paystack(self, request, pk=None):
        plan = self.get_object()
        plan = SubscriptionCreateSerializer._sync_plan_to_paystack(plan)
        if plan.paystack_plan_code:
            return Response({
                'message': 'Plan synced to Paystack.',
                'paystack_plan_code': plan.paystack_plan_code,
            })
        return Response(
            {'error': 'Failed to sync plan to Paystack.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AdminSubscriptionViewSet(viewsets.GenericViewSet,
                                viewsets.mixins.ListModelMixin,
                                viewsets.mixins.RetrieveModelMixin):
    """
    Admin view of all customer subscriptions.
    GET  /api/subscriptions/admin/subscriptions/              — list all (filter: ?status=, ?plan=)
    GET  /api/subscriptions/admin/subscriptions/<id>/         — retrieve one
    POST /api/subscriptions/admin/subscriptions/<id>/cancel/  — force cancel
    POST /api/subscriptions/admin/subscriptions/assign/       — assign plan to customer
    """
    serializer_class = AdminSubscriptionSerializer
    permission_classes = [IsPlatformAdmin]

    def get_queryset(self):
        qs = Subscription.objects.select_related(
            'user', 'plan',
        ).order_by('-started_at')
        status_filter = self.request.query_params.get('status')
        plan_filter = self.request.query_params.get('plan')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if plan_filter:
            qs = qs.filter(plan_id=plan_filter)
        return qs

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        sub = self.get_object()
        if sub.status == 'cancelled':
            return Response({'error': 'Already cancelled.'}, status=status.HTTP_400_BAD_REQUEST)
        from subscriptions.billing import expire_subscription
        expire_subscription(sub, reason='Administrator cancelled', force=True, status='cancelled')
        return Response(AdminSubscriptionSerializer(sub).data)

    @action(detail=False, methods=['post'])
    def assign(self, request):
        """Directly assign a plan to a customer (bypass Paystack)."""
        serializer = AdminSubscriptionAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_object_or_404(User, id=serializer.validated_data['user_id'], user_type='customer')
        plan = Plan.objects.get(id=serializer.validated_data['plan_id'])
        sub_status = serializer.validated_data['status']
        now = timezone.now()

        from datetime import timedelta
        if plan.duration_unit == 'months':
            period_end = now + timedelta(days=plan.duration * 30)
        elif plan.duration_unit == 'years':
            period_end = now + timedelta(days=plan.duration * 365)
        else:
            period_end = now + timedelta(days=plan.duration)

        # Detach the customer's BNPL CreditAccount from any old
        # subscriptions before wiping them — CreditAccount.subscription
        # is PROTECT so the delete would otherwise blow up. We re-link
        # to the freshly created subscription below.
        from debit.models import CreditAccount  # local to avoid cycle
        existing_credit = CreditAccount.objects.filter(
            user=user, subscription__user=user,
        ).first()
        if existing_credit is not None:
            existing_credit.subscription = None
            existing_credit.save(update_fields=['subscription', 'updated_at'])

        from .billing import queue_cancellation
        for previous in Subscription.objects.filter(user=user):
            queue_cancellation(previous.paystack_subscription_code, previous.paystack_email_token,
                               'Administrator replaced subscription')
        Subscription.objects.filter(user=user).delete()
        sub = Subscription.objects.create(
            user=user,
            plan=plan,
            status=sub_status,
            current_period_start=now,
            current_period_end=period_end,
        )

        if existing_credit is not None:
            existing_credit.subscription = sub
            existing_credit.credit_limit = plan.credit_limit
            existing_credit.save(update_fields=[
                'subscription', 'credit_limit', 'updated_at',
            ])

        return Response(AdminSubscriptionSerializer(sub).data, status=status.HTTP_201_CREATED)
