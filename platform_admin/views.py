from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from decimal import Decimal

from django.utils import timezone
from accounts.models import CustomerProfile
from debit.models import CreditAccount, CreditPurchase, CreditRepayment
from rest_framework import serializers as drf_serializers
from debit.serializers import (
    CreditAccountSerializer,
    CreditPurchaseSerializer,
    CreditRepaymentSerializer,
)
from .models import AdminProfile, AdminInvitation, PlatformFee
from .serializers import (
    AdminProfileSerializer,
    AdminProfileCreateSerializer,
    AdminProfileUpdateSerializer,
    AdminPermissionOverrideSerializer,
    AdminInvitationSerializer,
    SendInvitationSerializer,
    AcceptInvitationSerializer,
    PlatformFeeSerializer,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_admin_profile(request):
    """Return the caller's AdminProfile or raise 403."""
    try:
        return request.user.admin_profile
    except AdminProfile.DoesNotExist:
        return None


def _require_super_admin(profile):
    """Return True if super_admin, False otherwise."""
    return profile and profile.is_super_admin


# ── My Profile ────────────────────────────────────────────────────────────────

class AdminProfileView(APIView):
    unverified_actions = ('get', 'post', 'patch', 'put')
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_admin_profile(request)
        if not profile:
            return Response({'detail': 'Admin profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(AdminProfileSerializer(profile).data)

    def post(self, request):
        serializer = AdminProfileCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(AdminProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        profile = _get_admin_profile(request)
        if not profile:
            return Response({'detail': 'Admin profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminProfileUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminProfileSerializer(profile).data)

    def put(self, request):
        return self.patch(request)


# ── Team listing (Super Admin only) ───────────────────────────────────────────

class AdminTeamListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Only Super Admins can view the team.'}, status=status.HTTP_403_FORBIDDEN)
        team = AdminProfile.objects.select_related('user', 'invited_by__user').all()
        return Response(AdminProfileSerializer(team, many=True).data)


# ── Admin detail (Super Admin only) ───────────────────────────────────────────

class AdminDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_target(self, pk):
        return get_object_or_404(AdminProfile, pk=pk)

    def get(self, request, pk):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        target = self._get_target(pk)
        return Response(AdminProfileSerializer(target).data)

    def patch(self, request, pk):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        target = self._get_target(pk)
        serializer = AdminProfileUpdateSerializer(target, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminProfileSerializer(target).data)

    def delete(self, request, pk):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        target = self._get_target(pk)
        if target == profile:
            return Response({'detail': 'You cannot delete your own profile.'}, status=status.HTTP_400_BAD_REQUEST)
        target.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Suspend / Activate (Super Admin only) ─────────────────────────────────────

class AdminSuspendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        target = get_object_or_404(AdminProfile, pk=pk)
        if target == profile:
            return Response({'detail': 'You cannot suspend yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        target.status = 'suspended'
        target.save(update_fields=['status'])
        return Response(AdminProfileSerializer(target).data)


class AdminActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        target = get_object_or_404(AdminProfile, pk=pk)
        target.status = 'active'
        target.save(update_fields=['status'])
        return Response(AdminProfileSerializer(target).data)


# ── Permissions override (Super Admin only) ────────────────────────────────────

class AdminPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        target = get_object_or_404(AdminProfile, pk=pk)
        serializer = AdminPermissionOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(target, serializer.validated_data)
        return Response(AdminProfileSerializer(target).data)

    def post(self, request, pk):
        """Reset permissions to role defaults."""
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        target = get_object_or_404(AdminProfile, pk=pk)
        target.seed_permissions()
        target.save(update_fields=['permissions'])
        return Response(AdminProfileSerializer(target).data)


# ── Invitations ───────────────────────────────────────────────────────────────

class SendInvitationView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Only Super Admins can send invitations.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SendInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = AdminInvitation.objects.create(
            invited_by=profile,
            email=serializer.validated_data['email'],
            role=serializer.validated_data['role'],
            department=serializer.validated_data['department'],
        )
        from core.email import send_branded_email
        delivered = send_branded_email(
            subject='Your Sanoa administrator invitation', to=[invitation.email],
            template='emails/admin_invitation.html',
            context={'invitation': invitation},
        )
        if not delivered:
            transaction.set_rollback(True)
            return Response({'detail': 'The invitation email could not be sent. Please retry.'}, status=503)
        return Response(AdminInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class InvitationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        invitations = AdminInvitation.objects.select_related(
            'invited_by__user', 'accepted_by__user',
        ).all()
        return Response(AdminInvitationSerializer(invitations, many=True).data)


class InvitationDetailView(APIView):
    unverified_actions = ('get',)
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        invitation = get_object_or_404(AdminInvitation, token=token)
        if invitation.email.casefold() != request.user.email.casefold():
            return Response({'detail': 'Invitation not found.'}, status=404)
        return Response(AdminInvitationSerializer(invitation).data)


class AcceptInvitationView(APIView):
    unverified_actions = ('post',)
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, token):
        invitation = get_object_or_404(AdminInvitation.objects.select_for_update(), token=token)

        if not invitation.is_valid:
            return Response(
                {'detail': 'This invitation is no longer valid (expired, accepted, or revoked).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        if not user.is_verified:
            return Response({'detail': 'Verify your email before accepting this invitation.'}, status=403)
        if user.user_type != 'admin':
            return Response(
                {'detail': 'Only users with admin account type can accept an admin invitation.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if user.email.casefold() != invitation.email.casefold():
            return Response(
                {'detail': 'This invitation was not sent to your email address.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if AdminProfile.objects.filter(user=user).exists():
            return Response(
                {'detail': 'You already have an admin profile.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = AdminProfile(
            user=user,
            role=invitation.role,
            department=invitation.department,
            invited_by=invitation.invited_by,
            work_email=serializer.validated_data['work_email'],
            role_title=serializer.validated_data.get('role_title', ''),
        )
        if serializer.validated_data.get('profile_photo'):
            profile.profile_photo = serializer.validated_data['profile_photo']
        profile.seed_permissions()
        profile.save()

        invitation.status = 'accepted'
        invitation.accepted_by = profile
        invitation.save(update_fields=['status', 'accepted_by'])

        return Response(AdminProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class RevokeInvitationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_admin_profile(request)
        if not _require_super_admin(profile):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        invitation = get_object_or_404(AdminInvitation, pk=pk)
        if invitation.status != 'pending':
            return Response(
                {'detail': 'Only pending invitations can be revoked.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invitation.status = 'revoked'
        invitation.save(update_fields=['status'])
        return Response(AdminInvitationSerializer(invitation).data)


# ── Admin Customer Management ────────────────────────────────────────────────

class AdminCustomerProfileSerializer(drf_serializers.ModelSerializer):
    id = drf_serializers.IntegerField(source='user.id', read_only=True)
    email = drf_serializers.EmailField(source='user.email', read_only=True)
    first_name = drf_serializers.CharField(source='user.first_name', read_only=True)
    last_name = drf_serializers.CharField(source='user.last_name', read_only=True)
    phone_number = drf_serializers.CharField(source='user.phone_number', read_only=True)
    is_verified = drf_serializers.BooleanField(source='user.is_verified', read_only=True)
    is_suspended = drf_serializers.BooleanField(source='user.is_suspended', read_only=True)
    suspended_at = drf_serializers.DateTimeField(source='user.suspended_at', read_only=True)
    suspension_reason = drf_serializers.CharField(source='user.suspension_reason', read_only=True)
    date_joined = drf_serializers.DateTimeField(source='user.date_joined', read_only=True)

    class Meta:
        model = CustomerProfile
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone_number',
            'is_verified', 'is_suspended', 'suspended_at', 'suspension_reason',
            'avatar', 'gender', 'bio', 'latitude', 'longitude',
            'preferred_language', 'newsletter_subscription',
            'sms_notifications', 'email_notifications',
            'loyalty_points', 'member_since', 'date_joined',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class AdminCustomerListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profiles = CustomerProfile.objects.select_related('user').order_by('-created_at')

        is_suspended = request.query_params.get('is_suspended')
        if is_suspended is not None:
            profiles = profiles.filter(user__is_suspended=is_suspended.lower() == 'true')

        is_verified = request.query_params.get('is_verified')
        if is_verified is not None:
            profiles = profiles.filter(user__is_verified=is_verified.lower() == 'true')

        search = request.query_params.get('search')
        if search:
            profiles = profiles.filter(
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__phone_number__icontains=search)
            )

        return Response(AdminCustomerProfileSerializer(profiles, many=True, context={'request': request}).data)


class AdminCustomerDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profile = get_object_or_404(
            CustomerProfile.objects.select_related('user'),
            user__id=pk,
        )
        return Response(AdminCustomerProfileSerializer(profile, context={'request': request}).data)

    def patch(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profile = get_object_or_404(
            CustomerProfile.objects.select_related('user'),
            user__id=pk,
        )
        user = profile.user
        user_fields = ('first_name', 'last_name', 'phone_number', 'date_of_birth')
        user_data = {k: v for k, v in request.data.items() if k in user_fields}
        profile_fields = ('gender', 'bio', 'latitude', 'longitude', 'preferred_language',
                          'newsletter_subscription', 'sms_notifications', 'email_notifications',
                          'loyalty_points')
        profile_data = {k: v for k, v in request.data.items() if k in profile_fields}

        if user_data:
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save(update_fields=list(user_data.keys()) + ['updated_at'])

        if profile_data:
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save(update_fields=list(profile_data.keys()) + ['updated_at'])

        return Response(AdminCustomerProfileSerializer(profile, context={'request': request}).data)

    def delete(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profile = get_object_or_404(CustomerProfile.objects.select_related('user'), user__id=pk)
        profile.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCustomerSuspendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profile = get_object_or_404(CustomerProfile.objects.select_related('user'), user__id=pk)
        user = profile.user
        if user.is_suspended:
            return Response({'detail': 'Customer is already suspended.'}, status=status.HTTP_400_BAD_REQUEST)
        user.is_suspended = True
        user.suspended_at = timezone.now()
        user.suspension_reason = request.data.get('reason', 'Suspended by platform admin.')
        user.save(update_fields=['is_suspended', 'suspended_at', 'suspension_reason', 'updated_at'])
        return Response(AdminCustomerProfileSerializer(profile, context={'request': request}).data)


class AdminCustomerUnsuspendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profile = get_object_or_404(CustomerProfile.objects.select_related('user'), user__id=pk)
        user = profile.user
        if not user.is_suspended:
            return Response({'detail': 'Customer is not suspended.'}, status=status.HTTP_400_BAD_REQUEST)
        user.is_suspended = False
        user.suspended_at = None
        user.suspension_reason = ''
        user.save(update_fields=['is_suspended', 'suspended_at', 'suspension_reason', 'updated_at'])
        return Response(AdminCustomerProfileSerializer(profile, context={'request': request}).data)


class AdminCustomerVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profile = get_object_or_404(CustomerProfile.objects.select_related('user'), user__id=pk)
        user = profile.user
        if user.is_verified:
            return Response({'detail': 'Customer is already verified.'}, status=status.HTTP_400_BAD_REQUEST)
        user.is_verified = True
        user.save(update_fields=['is_verified', 'updated_at'])
        return Response(AdminCustomerProfileSerializer(profile, context={'request': request}).data)


class AdminCustomerUnverifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profile = get_object_or_404(CustomerProfile.objects.select_related('user'), user__id=pk)
        user = profile.user
        if not user.is_verified:
            return Response({'detail': 'Customer is not verified.'}, status=status.HTTP_400_BAD_REQUEST)
        user.is_verified = False
        user.save(update_fields=['is_verified', 'updated_at'])
        return Response(AdminCustomerProfileSerializer(profile, context={'request': request}).data)


class AdminCustomerAdjustLoyaltyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        profile = get_object_or_404(CustomerProfile.objects.select_related('user'), user__id=pk)
        try:
            points = int(request.data.get('points', ''))
        except (TypeError, ValueError):
            return Response({'detail': 'A valid integer value for points is required.'}, status=status.HTTP_400_BAD_REQUEST)
        profile.loyalty_points = max(0, profile.loyalty_points + points)
        profile.save(update_fields=['loyalty_points', 'updated_at'])
        return Response({
            'loyalty_points': profile.loyalty_points,
            'adjusted_by': points,
        })


# ── Admin Debit Management ────────────────────────────────────────────────────

def _require_admin(request):
    """Return AdminProfile or None; also accepts is_staff / user_type='admin'."""
    user = request.user
    if user.is_staff or getattr(user, 'user_type', '') == 'admin':
        return True
    return _get_admin_profile(request) is not None


class AdminDebitAccountListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        accounts = CreditAccount.objects.select_related(
            'user', 'subscription__plan',
        ).order_by('-created_at')
        return Response(CreditAccountSerializer(accounts, many=True).data)


class AdminDebitAccountDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        account = get_object_or_404(
            CreditAccount.objects.select_related('user', 'subscription__plan'),
            pk=pk,
        )
        return Response(CreditAccountSerializer(account).data)


class AdminDebitAccountSuspendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        account = get_object_or_404(CreditAccount, pk=pk)
        if account.status == 'suspended':
            return Response({'detail': 'Account is already suspended.'}, status=status.HTTP_400_BAD_REQUEST)
        account.suspend()
        return Response(CreditAccountSerializer(account).data)


class AdminDebitAccountUnsuspendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        account = get_object_or_404(CreditAccount, pk=pk)
        if account.status != 'suspended':
            return Response({'detail': 'Account is not suspended.'}, status=status.HTTP_400_BAD_REQUEST)
        account.unsuspend()
        return Response(CreditAccountSerializer(account).data)


class AdminDebitPurchaseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        purchases = CreditPurchase.objects.select_related(
            'credit_account__user', 'vendor', 'order',
        ).order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            purchases = purchases.filter(status=status_filter)
        return Response(CreditPurchaseSerializer(purchases, many=True, context={'request': request}).data)


class AdminDebitPurchaseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        purchase = get_object_or_404(
            CreditPurchase.objects.select_related('credit_account__user', 'vendor', 'order'),
            pk=pk,
        )
        return Response(CreditPurchaseSerializer(purchase, context={'request': request}).data)


class AdminDebitAccountPurchasesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        account = get_object_or_404(CreditAccount, pk=pk)
        purchases = CreditPurchase.objects.filter(
            credit_account=account,
        ).select_related('vendor', 'order').order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            purchases = purchases.filter(status=status_filter)
        return Response(CreditPurchaseSerializer(purchases, many=True, context={'request': request}).data)


class AdminDebitPurchaseRepayView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        purchase = get_object_or_404(
            CreditPurchase.objects.select_related('credit_account__user'),
            pk=pk,
        )

        if purchase.is_fully_paid:
            return Response({'detail': 'This purchase is already fully paid.'}, status=status.HTTP_400_BAD_REQUEST)

        if purchase.status not in ('active', 'defaulted'):
            return Response({'detail': 'Cannot make repayments on this purchase.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(request.data.get('amount', '')))
        except Exception:
            return Response({'detail': 'A valid amount is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'detail': 'Amount must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount > purchase.total_outstanding:
            return Response(
                {'detail': f'Amount exceeds total outstanding of R{purchase.total_outstanding:.2f}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_method = request.data.get('payment_method', 'card')
        reference = request.data.get('reference', '')
        paystack_transaction_id = request.data.get('paystack_transaction_id', '')

        # Apply to penalties first, then principal
        remaining = amount
        penalty_portion = Decimal('0.00')
        principal_portion = Decimal('0.00')

        if purchase.outstanding_penalty > 0:
            penalty_payment = min(remaining, purchase.outstanding_penalty)
            penalty_portion = penalty_payment
            remaining -= penalty_payment

        if remaining > 0:
            principal_portion = min(remaining, purchase.outstanding_balance)

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
            payment_method=payment_method,
            repayment_type=repayment_type,
            reference=reference,
            paystack_transaction_id=paystack_transaction_id,
        )

        purchase.amount_paid += principal_portion
        purchase.penalty_paid += penalty_portion
        if purchase.is_fully_paid:
            purchase.status = 'paid'
            purchase.paid_at = timezone.now()
        purchase.save(update_fields=['amount_paid', 'penalty_paid', 'status', 'paid_at', 'updated_at'])

        account = purchase.credit_account
        account.current_balance = max(Decimal('0.00'), account.current_balance - principal_portion)
        account.total_penalties = max(Decimal('0.00'), account.total_penalties - penalty_portion)
        account.save(update_fields=['current_balance', 'total_penalties', 'updated_at'])

        if account.user.is_suspended:
            account.unsuspend()

        return Response({
            'repayment': CreditRepaymentSerializer(repayment).data,
            'purchase_status': purchase.status,
            'account_status': account.status,
            'current_balance': str(account.current_balance),
            'total_penalties': str(account.total_penalties),
        }, status=status.HTTP_201_CREATED)


class AdminDebitRepaymentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _require_admin(request):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)
        repayments = CreditRepayment.objects.select_related(
            'purchase__credit_account__user',
        ).order_by('-created_at')
        return Response(CreditRepaymentSerializer(repayments, many=True).data)


# ── Platform Fees ─────────────────────────────────────────────────────────────
#
# Read: any authenticated admin. Write: super_admin or admin with
# `financial_access` (finance_admin role by default). Edits stamp
# `updated_by` so we have an audit trail without a full audit log.

def _can_manage_platform_fees(profile):
    if profile is None:
        return False
    if profile.is_super_admin:
        return True
    return bool(profile.has_permission('financial_access'))


class PlatformFeeListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_admin_profile(request)
        if profile is None:
            return Response(
                {'detail': 'Admin profile required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        active_only = request.query_params.get('active') == 'true'
        qs = PlatformFee.objects.select_related('updated_by__user').all()
        if active_only:
            qs = qs.filter(is_active=True)
        return Response(PlatformFeeSerializer(qs, many=True).data)

    def post(self, request):
        profile = _get_admin_profile(request)
        if not _can_manage_platform_fees(profile):
            return Response(
                {'detail': 'Only Super Admins or Finance Admins can edit platform fees.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = PlatformFeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fee = serializer.save(updated_by=profile)
        return Response(
            PlatformFeeSerializer(fee).data,
            status=status.HTTP_201_CREATED,
        )


class PlatformFeeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile = _get_admin_profile(request)
        if profile is None:
            return Response(
                {'detail': 'Admin profile required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        fee = get_object_or_404(
            PlatformFee.objects.select_related('updated_by__user'), pk=pk,
        )
        return Response(PlatformFeeSerializer(fee).data)

    def patch(self, request, pk):
        profile = _get_admin_profile(request)
        if not _can_manage_platform_fees(profile):
            return Response(
                {'detail': 'Only Super Admins or Finance Admins can edit platform fees.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        fee = get_object_or_404(PlatformFee, pk=pk)
        serializer = PlatformFeeSerializer(fee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=profile)
        return Response(PlatformFeeSerializer(fee).data)

    def put(self, request, pk):
        return self.patch(request, pk)

    def delete(self, request, pk):
        profile = _get_admin_profile(request)
        if not (profile and profile.is_super_admin):
            return Response(
                {'detail': 'Only Super Admins can delete platform fee rows.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        fee = get_object_or_404(PlatformFee, pk=pk)
        fee.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Platform Fee — public lookup (customer + vendor) ──────────────────────────
#
# Returns the applied customer service-fee + merchant commission for a
# given business type. Authenticated only (any role), no admin gate —
# customer apps need this to render checkout markup and vendor apps
# can preview the commission they'll be charged.

class PlatformFeeLookupView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bt = (request.query_params.get('business_type') or '').strip().lower()
        # Accept the vendor.business_category vocabulary verbatim, plus a
        # couple of friendly aliases the frontend sometimes sends.
        aliases = {
            'ecommerce':   PlatformFee.BUSINESS_TYPE_RETAIL,
            'e-commerce':  PlatformFee.BUSINESS_TYPE_RETAIL,
            'grocery':     PlatformFee.BUSINESS_TYPE_RETAIL,
            'shopping':    PlatformFee.BUSINESS_TYPE_RETAIL,
            'food':        PlatformFee.BUSINESS_TYPE_RESTAURANT,
            'restaurant_delivery': PlatformFee.BUSINESS_TYPE_RESTAURANT,
        }
        bt = aliases.get(bt, bt)
        if bt not in dict(PlatformFee.BUSINESS_TYPE_CHOICES):
            return Response(
                {
                    'error': 'Unknown business_type.',
                    'allowed': [k for k, _ in PlatformFee.BUSINESS_TYPE_CHOICES],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        fee = PlatformFee.for_business_category(bt)
        if fee is None:
            return Response(
                {'error': f'No active platform fee row for {bt!r}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({
            'business_type': fee.business_type,
            'business_type_display': fee.get_business_type_display(),
            'customer_service_fee_percent': str(fee.customer_service_fee_percent),
            'customer_service_fee_range': fee.customer_service_fee_range,
            'merchant_commission_percent': str(fee.merchant_commission_percent),
            'merchant_commission_range': fee.merchant_commission_range,
            'delivery_fee_percent': str(fee.delivery_fee_percent),
            'delivery_fee_range': fee.delivery_fee_range,
        })


# ── Platform settings — convenience aggregate ─────────────────────────────────
#
# Front-end "Settings" pages on the platform admin app usually want
# every fee row alongside the unified options in one fetch. Keeps the
# dashboard responsive without firing N endpoints.

class PlatformSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_admin_profile(request)
        if profile is None:
            return Response(
                {'detail': 'Admin profile required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        fees = PlatformFee.objects.select_related('updated_by__user').order_by('business_type')
        return Response({
            'platform_fees': PlatformFeeSerializer(fees, many=True).data,
            'business_types': [
                {'value': k, 'label': v} for k, v in PlatformFee.BUSINESS_TYPE_CHOICES
            ],
            'can_edit': _can_manage_platform_fees(profile),
        })
