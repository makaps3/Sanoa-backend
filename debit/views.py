"""
Views for the Credit System (Buy Now, Pay Later).

Suspended users can ONLY access the repay endpoint and view their account/purchases.
All other platform features are blocked by SuspendedUserMiddleware.
"""
from rest_framework import viewsets, generics, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .models import CreditAccount, CreditPurchase, CreditRepayment
from .serializers import (
    CreditAccountSerializer,
    CreditAccountCreateSerializer,
    CreditEligibilitySerializer,
    CreditPurchaseCreateSerializer,
    CreditPurchaseSerializer,
    CreditRepaymentSerializer,
    CreditRepaymentCreateSerializer,
)


class CreditAccountView(generics.RetrieveAPIView):
    """Get the current user's credit account details."""

    serializer_class = CreditAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        try:
            return CreditAccount.objects.select_related(
                'subscription__plan', 'user',
            ).get(user=self.request.user)
        except CreditAccount.DoesNotExist:
            raise NotFound(
                'No credit account found. Create one first via POST /api/debit/account/create/'
            )


class CreditAccountCreateView(generics.CreateAPIView):
    """
    Create a credit account for the authenticated customer.
    Requires an active subscription — credit limit is set from the subscription plan.
    """

    serializer_class = CreditAccountCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = serializer.save()
        return Response(
            CreditAccountSerializer(account).data,
            status=status.HTTP_201_CREATED,
        )


class CreditEligibilityView(generics.GenericAPIView):
    """
    Check if the current user is eligible for credit purchases with a vendor.

    POST body: {"vendor_id": 123}
    """

    serializer_class = CreditEligibilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = serializer.check_eligibility(
            user=request.user,
            vendor=serializer.validated_data['vendor'],
        )
        return Response(result)


class CreditPurchaseViewSet(viewsets.GenericViewSet):
    """ViewSet for credit purchases and repayments."""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'buy_on_credit':
            return CreditPurchaseCreateSerializer
        if self.action == 'repay':
            return CreditRepaymentCreateSerializer
        return CreditPurchaseSerializer

    def get_queryset(self):
        return CreditPurchase.objects.filter(
            credit_account__user=self.request.user,
        ).select_related('vendor', 'credit_account', 'order')

    @action(detail=False, methods=['get'], url_path='my-purchases')
    def my_purchases(self, request):
        """List all credit purchases for the current user."""
        queryset = self.get_queryset()
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        serializer = CreditPurchaseSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def detail_purchase(self, request, pk=None):
        """Get details of a specific credit purchase."""
        try:
            purchase = self.get_queryset().get(pk=pk)
        except CreditPurchase.DoesNotExist:
            raise NotFound('Purchase not found.')
        return Response(CreditPurchaseSerializer(purchase).data)

    @action(detail=False, methods=['post'], url_path='buy-on-credit')
    def buy_on_credit(self, request):
        """
        Create a new credit purchase (buy now, pay later).
        Validates all eligibility: purchase history, follower, subscription,
        deposit %, credit limit, max items on credit.
        Suspended users are blocked from creating new purchases.
        """
        serializer = CreditPurchaseCreateSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        purchase = serializer.save()
        return Response(
            CreditPurchaseSerializer(purchase).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='repay')
    def repay(self, request):
        """
        Make a repayment towards a credit purchase.

        Payments are applied to penalties first, then to the principal.
        If all overdue balances are cleared, the user's suspension is
        lifted IMMEDIATELY and full platform access is restored.
        """
        serializer = CreditRepaymentCreateSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        repayment = serializer.save()

        # Return the repayment AND the updated account status
        account = CreditAccount.objects.select_related('user').get(
            user=request.user,
        )

        return Response({
            'repayment': CreditRepaymentSerializer(repayment).data,
            'account_status': account.status,
            'is_suspended': account.user.is_suspended,
            'current_balance': str(account.current_balance),
            'total_penalties': str(account.total_penalties),
            'message': (
                'Payment received. Your account has been reactivated.'
                if not account.user.is_suspended and account.status == 'active'
                else 'Payment received. Please settle remaining balances to restore access.'
            ),
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='overdue')
    def overdue_purchases(self, request):
        """List only overdue credit purchases for the current user."""
        queryset = self.get_queryset().filter(
            status__in=('active', 'defaulted'),
            due_date__lt=timezone.now().date(),
        )
        # Filter to only truly overdue (not fully paid)
        overdue = [p for p in queryset if p.is_overdue]
        serializer = CreditPurchaseSerializer(overdue, many=True)
        return Response(serializer.data)


# Import timezone at module level for the overdue view
from django.utils import timezone
