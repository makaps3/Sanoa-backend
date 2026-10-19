"""
API for promotions & coupons.

  * Customer   — browse live promotions, apply/remove/validate coupon codes,
                 and read the priced cart summary.
  * Vendor     — CRUD their own promotions & coupons (auto-scoped to them).
  * Admin      — CRUD every promotion & coupon, incl. platform-wide ones.
"""
import logging

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminUser, IsVendor
from orders.models import ShoppingCart
from products.models import Category

from .models import Coupon, OwnerType, Promotion, PromotionBanner
from .serializers import (
    CouponSerializer,
    CouponWriteSerializer,
    PromotionBannerSerializer,
    PromotionBannerWriteSerializer,
    PromotionSerializer,
    PromotionWriteSerializer,
)
from .services import (
    apply_coupon_to_cart,
    build_overview,
    build_rule_analytics,
    compute_cart_pricing,
    remove_coupon_from_cart,
)

log = logging.getLogger('sanoa.promotions')


# ── helpers ──────────────────────────────────────────────────────────

def vendor_profile_for(user):
    """The VendorProfile a user acts for (owner or active employee)."""
    vp = getattr(user, 'vendor_profile', None)
    if vp is not None:
        return vp
    emp = getattr(user, 'vendor_employment', None)
    if emp is not None and getattr(emp, 'is_active', False):
        return emp.vendor
    return None


def _pricing_response(cart, user):
    return Response(compute_cart_pricing(cart, user=user))


def _get_cart(user, vendor_id):
    if not vendor_id:
        return None
    # vendor_id is a UUID column — a malformed value raises rather than
    # returning empty, so guard it and treat "not a real vendor" as no cart.
    try:
        return (ShoppingCart.objects
                .filter(user=user, vendor_id=vendor_id)
                .select_related('vendor').first())
    except (ValueError, ValidationError, TypeError):
        return None


# ── customer ─────────────────────────────────────────────────────────

class PublicPromotionListView(APIView):
    """Live promotions the customer can benefit from (for storefront /
    profile). Optional ?vendor_id= filter; platform promos always included."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        qs = (Promotion.objects
              .filter(is_active=True, start_date__lte=now)
              .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
              .select_related('vendor')
              .prefetch_related('applicable_products', 'applicable_categories'))

        vendor_id = request.query_params.get('vendor_id')
        if vendor_id:
            qs = qs.filter(
                Q(owner_type=OwnerType.PLATFORM) | Q(vendor_id=vendor_id))

        promos = [p for p in qs
                  if p.is_live(now) and p.applies_to_user(request.user)]
        data = PromotionSerializer(promos, many=True).data
        return Response({'count': len(data), 'promotions': data})


class MyPromotionsView(APIView):
    """Promotions grouped for the customer profile: platform-wide first,
    then vendor promotions, with live coupons the customer may still use."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        live = Q(is_active=True, start_date__lte=now) & \
            (Q(end_date__isnull=True) | Q(end_date__gte=now))

        promos = [p for p in Promotion.objects.filter(live)
                  .select_related('vendor')
                  .prefetch_related('applicable_products',
                                    'applicable_categories')
                  if p.is_live(now) and p.applies_to_user(request.user)]
        platform = [p for p in promos if p.is_platform]
        vendor = [p for p in promos if not p.is_platform]

        # Coupons the customer can still use (respecting per-user targeting).
        coupons = []
        for c in Coupon.objects.filter(live).select_related('vendor'):
            if not c.is_live(now):
                continue
            if not c.applies_to_user(request.user):
                continue
            if c.uses_by(request.user) >= c.max_uses_per_user:
                continue
            coupons.append(c)

        return Response({
            'platform_promotions': PromotionSerializer(platform, many=True).data,
            'vendor_promotions': PromotionSerializer(vendor, many=True).data,
            'coupons': CouponSerializer(coupons, many=True).data,
        })


class CartSummaryView(APIView):
    """Priced summary of the customer's cart with a given vendor —
    automatic promotions + any applied coupon."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart = _get_cart(request.user, request.query_params.get('vendor_id'))
        if cart is None:
            return Response({'detail': 'Cart not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        return _pricing_response(cart, request.user)


class ApplyCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code')
        vendor_id = request.data.get('vendor_id')
        cart = _get_cart(request.user, vendor_id)
        if cart is None:
            return Response({'detail': 'Cart not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            pricing, error = apply_coupon_to_cart(cart, code, request.user)
        except Exception:
            log.exception('Coupon apply failed for cart %s', cart.id)
            return Response(
                {'detail': 'Could not apply this coupon. Please try again.'},
                status=status.HTTP_400_BAD_REQUEST)
        if error:
            return Response({'detail': error},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(pricing)


class RemoveCouponView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        cart = _get_cart(request.user, request.data.get('vendor_id'))
        if cart is None:
            return Response({'detail': 'Cart not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        remove_coupon_from_cart(cart)
        return _pricing_response(cart, request.user)


class ValidateCouponView(APIView):
    """Check a code without attaching it — returns the discount it *would*
    apply to the current cart."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = (request.data.get('code') or '').strip().upper()
        vendor_id = request.data.get('vendor_id')
        cart = _get_cart(request.user, vendor_id)
        if cart is None:
            return Response({'detail': 'Cart not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return Response({'valid': False,
                             'detail': 'That coupon code is not valid.'},
                            status=status.HTTP_200_OK)
        pricing = compute_cart_pricing(cart, user=request.user, coupon=coupon)
        if pricing.get('coupon_error'):
            return Response({'valid': False,
                             'detail': pricing['coupon_error']})
        return Response({
            'valid': True,
            'code': coupon.code,
            'discount': pricing['coupon_discount'],
            'detail': 'Coupon is valid.',
        })


class VendorAnalyticsOverviewView(APIView):
    """Aggregate promotion + coupon analytics for the signed-in vendor."""
    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request):
        vp = vendor_profile_for(request.user)
        if vp is None:
            promos = Promotion.objects.none()
            coupons = Coupon.objects.none()
        else:
            promos = Promotion.objects.filter(vendor_id=vp.id)
            coupons = Coupon.objects.filter(vendor_id=vp.id)
        return Response(build_overview(promos, coupons))


class AdminAnalyticsOverviewView(APIView):
    """Aggregate promotion + coupon analytics across the whole platform."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return Response(build_overview(
            Promotion.objects.all(), Coupon.objects.all()))


class PublicBannerListView(APIView):
    """Live promotion banners for the customer home carousel."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        qs = (PromotionBanner.objects
              .filter(is_active=True)
              .filter(Q(start_date__isnull=True) | Q(start_date__lte=now))
              .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
              .select_related('vendor', 'promotion', 'category')
              .order_by('sort_order', '-created_at'))
        vendor_id = request.query_params.get('vendor_id')
        if vendor_id:
            qs = qs.filter(
                Q(owner_type=OwnerType.PLATFORM) | Q(vendor_id=vendor_id))
        data = PromotionBannerSerializer(
            qs[:12], many=True, context={'request': request}).data
        return Response({'count': len(data), 'banners': data})


class TargetCategoriesView(APIView):
    """Categories a vendor/admin can target a promotion or coupon at.

    Vendor → categories their own products use, plus any custom categories
    they own. Admin → every active category (optionally ?vendor_id=)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = user.is_staff or user.is_superuser or \
            hasattr(user, 'admin_profile')

        if is_admin:
            qs = Category.objects.filter(is_active=True)
            vendor_id = request.query_params.get('vendor_id')
            if vendor_id:
                qs = qs.filter(
                    Q(products__vendor_id=vendor_id) | Q(vendor_id=vendor_id))
        else:
            vp = vendor_profile_for(user)
            if vp is None:
                return Response({'categories': []})
            qs = Category.objects.filter(
                Q(products__vendor=vp) | Q(vendor=vp), is_active=True)

        qs = qs.distinct().order_by('name')
        data = [{
            'id': c.id,
            'name': c.name,
            'business_category': c.business_category,
        } for c in qs]
        return Response({'count': len(data), 'categories': data})


# ── vendor / admin CRUD ──────────────────────────────────────────────

class _BaseRuleViewSet(viewsets.ModelViewSet):
    """Shared list/search + read-vs-write serializer switching."""
    read_serializer = None
    write_serializer = None

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return self.write_serializer
        return self.read_serializer

    def _read_response(self, instance, code):
        data = self.read_serializer(instance, context=self.get_serializer_context()).data
        return Response(data, status=code)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return self._read_response(serializer.instance, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return self._read_response(serializer.instance, status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Usage analysis: redemptions, total discount given, per-customer
        breakdown (who used it and how much they saved), and recent uses."""
        return Response(build_rule_analytics(self.get_object()))


class VendorPromotionViewSet(_BaseRuleViewSet):
    permission_classes = [IsAuthenticated, IsVendor]
    read_serializer = PromotionSerializer
    write_serializer = PromotionWriteSerializer

    def get_queryset(self):
        vp = vendor_profile_for(self.request.user)
        if vp is None:
            return Promotion.objects.none()
        return (Promotion.objects.filter(vendor_id=vp.id)
                .prefetch_related('applicable_products',
                                  'applicable_categories'))

    def perform_create(self, serializer):
        vp = vendor_profile_for(self.request.user)
        serializer.save(vendor=vp, owner_type=OwnerType.VENDOR,
                        created_by=self.request.user)

    def perform_update(self, serializer):
        # Vendors can never reassign ownership.
        vp = vendor_profile_for(self.request.user)
        serializer.save(vendor=vp, owner_type=OwnerType.VENDOR)


class VendorCouponViewSet(_BaseRuleViewSet):
    permission_classes = [IsAuthenticated, IsVendor]
    read_serializer = CouponSerializer
    write_serializer = CouponWriteSerializer

    def get_queryset(self):
        vp = vendor_profile_for(self.request.user)
        if vp is None:
            return Coupon.objects.none()
        return Coupon.objects.filter(vendor_id=vp.id)

    def perform_create(self, serializer):
        vp = vendor_profile_for(self.request.user)
        serializer.save(vendor=vp, owner_type=OwnerType.VENDOR,
                        created_by=self.request.user)

    def perform_update(self, serializer):
        vp = vendor_profile_for(self.request.user)
        serializer.save(vendor=vp, owner_type=OwnerType.VENDOR)


class AdminPromotionViewSet(_BaseRuleViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    read_serializer = PromotionSerializer
    write_serializer = PromotionWriteSerializer

    def get_queryset(self):
        qs = (Promotion.objects.select_related('vendor')
              .prefetch_related('applicable_products',
                                'applicable_categories'))
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        owner = self.request.query_params.get('owner_type')
        if owner:
            qs = qs.filter(owner_type=owner)
        return qs

    def perform_create(self, serializer):
        owner_type = serializer.validated_data.get('owner_type')
        vendor = serializer.validated_data.get('vendor')
        if not vendor:
            owner_type = OwnerType.PLATFORM
        serializer.save(owner_type=owner_type or OwnerType.PLATFORM,
                        created_by=self.request.user)


class AdminCouponViewSet(_BaseRuleViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]
    read_serializer = CouponSerializer
    write_serializer = CouponWriteSerializer

    def get_queryset(self):
        qs = Coupon.objects.select_related('vendor')
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        owner = self.request.query_params.get('owner_type')
        if owner:
            qs = qs.filter(owner_type=owner)
        return qs

    def perform_create(self, serializer):
        owner_type = serializer.validated_data.get('owner_type')
        vendor = serializer.validated_data.get('vendor')
        if not vendor:
            owner_type = OwnerType.PLATFORM
        serializer.save(owner_type=owner_type or OwnerType.PLATFORM,
                        created_by=self.request.user)


# ── promotion banners (image carousel) ───────────────────────────────

class _BaseBannerViewSet(viewsets.ModelViewSet):
    """Image-upload CRUD; read vs write serializer switching."""
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return PromotionBannerWriteSerializer
        return PromotionBannerSerializer

    def _read_response(self, instance, code):
        data = PromotionBannerSerializer(
            instance, context=self.get_serializer_context()).data
        return Response(data, status=code)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return self._read_response(serializer.instance, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data,
                                         partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return self._read_response(serializer.instance, status.HTTP_200_OK)


class VendorBannerViewSet(_BaseBannerViewSet):
    permission_classes = [IsAuthenticated, IsVendor]

    def get_queryset(self):
        vp = vendor_profile_for(self.request.user)
        if vp is None:
            return PromotionBanner.objects.none()
        return PromotionBanner.objects.filter(vendor_id=vp.id) \
            .select_related('vendor', 'promotion', 'category')

    def _own_promotion(self, serializer, vp):
        """A vendor may only link a banner to their OWN promotion."""
        promo = serializer.validated_data.get('promotion')
        if promo is not None and str(promo.vendor_id) != str(vp.id):
            return None
        return promo

    def perform_create(self, serializer):
        vp = vendor_profile_for(self.request.user)
        serializer.save(vendor=vp, owner_type=OwnerType.VENDOR,
                        promotion=self._own_promotion(serializer, vp),
                        created_by=self.request.user)

    def perform_update(self, serializer):
        vp = vendor_profile_for(self.request.user)
        serializer.save(vendor=vp, owner_type=OwnerType.VENDOR,
                        promotion=self._own_promotion(serializer, vp))


class AdminBannerViewSet(_BaseBannerViewSet):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        qs = PromotionBanner.objects.select_related(
            'vendor', 'promotion', 'category')
        owner = self.request.query_params.get('owner_type')
        if owner:
            qs = qs.filter(owner_type=owner)
        vendor_id = self.request.query_params.get('vendor_id')
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        return qs

    def perform_create(self, serializer):
        vendor = serializer.validated_data.get('vendor')
        owner_type = serializer.validated_data.get('owner_type')
        if not vendor:
            owner_type = OwnerType.PLATFORM
        serializer.save(owner_type=owner_type or OwnerType.PLATFORM,
                        created_by=self.request.user)
