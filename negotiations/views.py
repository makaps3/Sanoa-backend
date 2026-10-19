import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


def _resolve_vendor(request, vendor_uuid):
    """
    Look up VendorProfile by UUID and verify ownership.
    Returns (vendor_profile, None) on success or (None, error Response) on failure.
    """
    from business.models import VendorProfile
    try:
        vp = VendorProfile.objects.get(id=vendor_uuid)
    except VendorProfile.DoesNotExist:
        return None, Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not request.user.is_staff:
        user_vp = getattr(request.user, 'vendor_profile', None)
        if user_vp != vp:
            return None, Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
    return vp, None

from .models import NegotiationMessage, NegotiationOffer, NegotiationRoom, PricePolicy
from .serializers import (
    NegotiationMessageSerializer,
    NegotiationOfferSerializer,
    NegotiationRoomCreateSerializer,
    NegotiationRoomSerializer,
    PricePolicyCreateUpdateSerializer,
    PricePolicySerializer,
)

logger = logging.getLogger('sanoa.negotiations')


class StartNegotiationView(generics.CreateAPIView):
    """
    POST /api/negotiations/start/
    Body: {"product_id": "<uuid>", "mode": "ai"|"manual"}

    Creates a new NegotiationRoom (or returns the existing open one).
    The frontend should then open the WebSocket:
        ws://<host>/ws/negotiations/<room_id>/?token=<JWT>
    """
    serializer_class = NegotiationRoomCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if getattr(request.user, 'user_type', None) != 'customer':
            return Response(
                {'error': 'Only customers can start negotiations.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from products.models import Product
        product_id = serializer.validated_data['product_id']
        mode = serializer.validated_data.get('mode', 'ai')

        try:
            product = Product.objects.select_related('vendor').get(
                id=product_id, status='active'
            )
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found or not active.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        vendor = product.vendor
        from tiers.entitlements import negotiation_allowed
        if not negotiation_allowed(vendor):
            return Response({'detail': 'This vendor does not have an active negotiation subscription.'},
                            status=status.HTTP_403_FORBIDDEN)

        # Return existing open room instead of creating a duplicate
        existing = NegotiationRoom.objects.filter(
            product=product, buyer=request.user, vendor=vendor, status='open',
        ).first()
        if existing:
            return Response(
                NegotiationRoomSerializer(existing, context={'request': request}).data,
                status=status.HTTP_200_OK,
            )

        room = NegotiationRoom.objects.create(
            product=product, buyer=request.user, vendor=vendor, mode=mode,
        )
        return Response(
            NegotiationRoomSerializer(room, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class NegotiationRoomDetailView(generics.RetrieveAPIView):
    """GET /api/negotiations/rooms/<uuid>/"""
    serializer_class = NegotiationRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        user = self.request.user
        vendor_profile = getattr(user, 'vendor_profile', None)
        q = Q(buyer=user)
        if vendor_profile:
            q |= Q(vendor=vendor_profile)
        return generics.get_object_or_404(
            NegotiationRoom.objects.filter(q).select_related('product', 'buyer', 'vendor'),
            id=self.kwargs['pk'],
        )


class MyNegotiationRoomsView(generics.ListAPIView):
    """GET /api/negotiations/rooms/  — buyer's own rooms"""
    serializer_class = NegotiationRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        qs = NegotiationRoom.objects.filter(
            buyer=self.request.user
        ).select_related('product', 'vendor').order_by('-created_at')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class VendorNegotiationRoomsView(generics.ListAPIView):
    """GET /api/negotiations/vendor/<vendor_uuid>/rooms/"""
    serializer_class = NegotiationRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        vp, _ = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if vp is None:
            return NegotiationRoom.objects.none()
        status_filter = self.request.query_params.get('status')
        qs = NegotiationRoom.objects.filter(
            vendor=vp
        ).select_related('product', 'buyer').order_by('-created_at')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)


class SwitchModeView(generics.GenericAPIView):
    """
    POST /api/negotiations/rooms/<uuid>/switch-mode/
    Vendor toggles between AI and manual mode.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        vendor_profile = getattr(request.user, 'vendor_profile', None)
        if vendor_profile is None:
            return Response(
                {'error': 'No vendor profile found.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        room = generics.get_object_or_404(
            NegotiationRoom,
            id=pk,
            vendor=vendor_profile,
            status='open',
        )
        new_mode = 'manual' if room.mode == 'ai' else 'ai'
        room.mode = new_mode
        room.save(update_fields=['mode', 'updated_at'])
        return Response({'room_id': str(room.id), 'mode': new_mode})


class RoomMessagesView(generics.ListAPIView):
    """GET /api/negotiations/rooms/<uuid>/messages/"""
    serializer_class = NegotiationMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        vendor_profile = getattr(user, 'vendor_profile', None)
        q = Q(buyer=user)
        if vendor_profile:
            q |= Q(vendor=vendor_profile)
        room = generics.get_object_or_404(
            NegotiationRoom.objects.filter(q),
            id=self.kwargs['pk'],
        )
        return room.messages.order_by('created_at').select_related('sender')


class PricePolicyViewSet(viewsets.GenericViewSet):
    """Vendor price policy management."""
    permission_classes = [permissions.IsAuthenticated]

    def _require_vendor(self, user):
        if getattr(user, 'user_type', None) != 'vendor':
            return Response(
                {'error': 'Only vendors can manage price policies.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if getattr(user, 'vendor_profile', None) is None:
            return Response(
                {'error': 'Vendor profile required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def list(self, request):
        """
        GET /api/negotiations/policy/
        Admin → all price policies platform-wide.
        Vendor → own policy only (same as my-policy).
        """
        user = request.user
        is_admin = (
            user.is_staff
            or hasattr(user, 'admin_profile')
            or getattr(user, 'user_type', '') == 'admin'
        )
        if is_admin:
            policies = PricePolicy.objects.select_related('vendor__user').all()
            return Response(PricePolicySerializer(policies, many=True).data)

        err = self._require_vendor(user)
        if err:
            return err
        try:
            policy = PricePolicy.objects.get(vendor=user.vendor_profile)
            return Response(PricePolicySerializer(policy).data)
        except PricePolicy.DoesNotExist:
            return Response([])

    @action(detail=False, methods=['get'], url_path='my-policy')
    def my_policy(self, request):
        err = self._require_vendor(request.user)
        if err:
            return err
        try:
            policy = PricePolicy.objects.get(vendor=request.user.vendor_profile)
            return Response(PricePolicySerializer(policy).data)
        except PricePolicy.DoesNotExist:
            return Response({
                'status': 'none',
                'message': 'No policy set. Defaults apply.',
                'defaults': {
                    'max_markup_percent': '15.00',
                    'max_discount_percent': '10.00',
                    'min_floor_percent': '5.00',
                    'auto_negotiate': True,
                },
            })

    @action(detail=False, methods=['post'], url_path='set-policy')
    def set_policy(self, request):
        err = self._require_vendor(request.user)
        if err:
            return err
        serializer = PricePolicyCreateUpdateSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        policy = serializer.save()
        return Response(PricePolicySerializer(policy).data)


# ---------------------------------------------------------------------------
# Offers history per room
# ---------------------------------------------------------------------------

class RoomOffersView(generics.ListAPIView):
    """
    GET /api/negotiations/rooms/<uuid>/offers/
    All offers (price proposals) for a room in chronological order.
    Accessible to the buyer or vendor of that room.
    """
    serializer_class = NegotiationOfferSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        vendor_profile = getattr(user, 'vendor_profile', None)
        q = Q(buyer=user)
        if vendor_profile:
            q |= Q(vendor=vendor_profile)
        room = generics.get_object_or_404(
            NegotiationRoom.objects.filter(q),
            id=self.kwargs['pk'],
        )
        return room.offers.order_by('created_at').select_related('message')


# ---------------------------------------------------------------------------
# Active deals — agreed rooms whose checkout window has not yet closed
# ---------------------------------------------------------------------------

class ActiveNegotiationsView(generics.ListAPIView):
    """
    GET /api/negotiations/active/
    Buyer's rooms that are status='agreed' and offer_expires_at > now.
    Includes time_remaining_seconds for the checkout countdown.
    """
    serializer_class = NegotiationRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Buyers should see `pending_vendor` rooms here too — the deal
        # is alive but held for the vendor's 24 h confirmation, and the
        # countdown driving the UI lives on the same field.
        return (
            NegotiationRoom.objects
            .filter(
                buyer=self.request.user,
                status__in=['agreed', 'pending_vendor'],
                offer_expires_at__gt=timezone.now(),
            )
            .select_related('product', 'vendor')
            .order_by('offer_expires_at')  # most urgent first
        )


class VendorActiveNegotiationsView(generics.ListAPIView):
    """GET /api/negotiations/vendor/<vendor_uuid>/active/"""
    serializer_class = NegotiationRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        vp, _ = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if vp is None:
            return NegotiationRoom.objects.none()
        return (
            NegotiationRoom.objects
            .filter(
                vendor=vp,
                status__in=['agreed', 'pending_vendor'],
                offer_expires_at__gt=timezone.now(),
            )
            .select_related('product', 'buyer')
            .order_by('offer_expires_at')
        )

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# History — all non-open rooms (expired, cancelled, agreed past window)
# ---------------------------------------------------------------------------

class AllNegotiationsView(generics.ListAPIView):
    """
    GET /api/negotiations/
    - Admin  → all rooms platform-wide
    - Vendor → their vendor rooms
    - Buyer  → their buyer rooms
    Supports ?status= and ?search= (buyer email / product name) for admin.
    """
    serializer_class = NegotiationRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        is_admin = (
            user.is_staff
            or hasattr(user, 'admin_profile')
            or getattr(user, 'user_type', '') == 'admin'
        )
        status_filter = self.request.query_params.get('status')

        if is_admin:
            qs = NegotiationRoom.objects.select_related(
                'product', 'buyer', 'vendor'
            ).order_by('-created_at')
            search = self.request.query_params.get('search')
            if search:
                qs = qs.filter(
                    Q(buyer__email__icontains=search) |
                    Q(product__name__icontains=search)
                )
        else:
            vendor_profile = getattr(user, 'vendor_profile', None)
            if vendor_profile:
                qs = NegotiationRoom.objects.filter(
                    vendor=vendor_profile
                ).select_related('product', 'buyer').order_by('-created_at')
            else:
                qs = NegotiationRoom.objects.filter(
                    buyer=user
                ).select_related('product', 'vendor').order_by('-created_at')

        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class NegotiationHistoryView(generics.ListAPIView):
    """
    GET /api/negotiations/history/
    GET /api/negotiations/history/?status=expired
    GET /api/negotiations/history/?status=agreed
    GET /api/negotiations/history/?status=cancelled

    Buyer's completed/past negotiations. Excludes open rooms.
    Default: all non-open statuses returned together.
    """
    serializer_class = NegotiationRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        # `open` and `pending_vendor` are both still-live phases — keep
        # them off the history list so the customer only sees finalised
        # rooms here.
        qs = NegotiationRoom.objects.filter(
            buyer=self.request.user,
        ).exclude(status__in=['open', 'pending_vendor']).select_related(
            'product', 'vendor',
        ).order_by('-updated_at')
        if status_filter and status_filter not in ('open', 'pending_vendor'):
            qs = qs.filter(status=status_filter)
        return qs


class VendorNegotiationHistoryView(generics.ListAPIView):
    """GET /api/negotiations/vendor/<vendor_uuid>/history/?status=expired|agreed|cancelled"""
    serializer_class = NegotiationRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        vp, _ = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if vp is None:
            return NegotiationRoom.objects.none()
        status_filter = self.request.query_params.get('status')
        qs = (
            NegotiationRoom.objects
            .filter(vendor=vp)
            .exclude(status__in=['open', 'pending_vendor'])
            .select_related('product', 'buyer')
            .order_by('-updated_at')
        )
        if status_filter and status_filter not in ('open', 'pending_vendor'):
            qs = qs.filter(status=status_filter)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)
