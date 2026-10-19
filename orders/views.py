import datetime
import logging

from rest_framework import viewsets, permissions, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, Count
from django.utils import timezone

from .models import (
    ShippingAddress, ShoppingCart, CartItem, Order, OrderItem,
    OrderStatusHistory, Coupon,
)
from negotiations.models import NegotiationRoom
from .serializers import (
    ShippingAddressSerializer,
    ShoppingCartSerializer, CartItemSerializer,
    OrderListSerializer, OrderDetailSerializer, OrderCreateSerializer,
    CouponSerializer,
)
from core.permissions import IsOwnerOrAdmin, IsAdminUser, IsVendorOrAdmin
from core.filters import OrderFilter
from core.pagination import StandardPagination

logger = logging.getLogger('sanoa.orders')


# ── Date-range helper (mirrors the analytics endpoint style) ──────────────────
# Accepts ``?period=today|week|month|year`` or ``?from=YYYY-MM-DD&to=YYYY-MM-DD``.
# Returns the queryset filtered by Order.created_at. All keys are optional —
# when none are supplied the queryset is returned unchanged.

def _parse_iso_date(value):
    if not value:
        return None
    try:
        # Accept both plain dates and ISO datetimes
        return datetime.datetime.fromisoformat(value).replace(
            tzinfo=datetime.timezone.utc,
        )
    except (TypeError, ValueError):
        return None


def _push_vendor_order_event(order, *, event_type, vendor_ids=None):
    """
    Push a retail order event to each affected vendor's WebSocket group so
    the queue + alert UI updates in real time.

    Event types:
      ``new_order``       — a brand-new pending order arrived; UI pops alert.
      ``status_changed``  — an order moved between queue statuses; UI refreshes.

    ``vendor_ids`` may be supplied when the caller already knows which
    vendors have items in this order — otherwise we resolve them from the
    order's items.
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        if vendor_ids is None:
            vendor_ids = list(
                order.items.filter(vendor__isnull=False)
                .values_list('vendor_id', flat=True)
                .distinct()
            )

        if not vendor_ids:
            return

        payload = {
            'type': event_type,
            'event_type': event_type,
            'order_id': str(order.id),
            'order_number': order.order_number,
            'status': order.status,
            'payment_status': order.payment_status,
            'fulfillment_type': getattr(order, 'fulfillment_type', '') or '',
            'items_count': order.items.count() if order.pk else 0,
            # `total_amount` is the customer-paid gross. Vendor cards
            # render `subtotal` (items only) so service + delivery
            # fees never appear as part of "the order price". Keep
            # `vendor_payout` on the payload too so the alert sheet
            # can preview the take-home if useful.
            'total_amount': str(order.total_amount),
            'subtotal': str(order.subtotal),
            'vendor_payout': str(order.vendor_payout),
            'created_at': order.created_at.isoformat() if order.created_at else None,
            'updated_at': order.updated_at.isoformat() if order.updated_at else None,
        }
        for vid in vendor_ids:
            async_to_sync(channel_layer.group_send)(
                f"vendor_orders_{vid}", payload,
            )
    except Exception:
        # Real-time push is best-effort — polling fallback covers gaps.
        pass


def apply_order_date_filter(qs, request):
    """Filter an Order queryset by ``period`` / ``from`` / ``to``.

    Honoured query params (in this order of precedence):
      1. Legacy ``created_date_from`` / ``created_date_to`` (kept for old clients).
      2. Analytics-style ``from`` / ``to`` (preferred — matches the analytics API).
      3. Analytics-style ``period`` shortcut (``today``/``week``/``month``/``year``).
    """
    qp = request.query_params

    # Legacy keys take precedence so old clients keep working unchanged.
    start = (
        _parse_iso_date(qp.get('created_date_from'))
        or _parse_iso_date(qp.get('from'))
    )
    end = (
        _parse_iso_date(qp.get('created_date_to'))
        or _parse_iso_date(qp.get('to'))
    )

    period = (qp.get('period') or '').strip().lower()
    now = timezone.now()
    if not start and period:
        if period == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start = now - datetime.timedelta(days=7)
        elif period == 'year':
            start = now - datetime.timedelta(days=365)
        elif period == 'month':
            start = now - datetime.timedelta(days=30)

    if start is not None:
        qs = qs.filter(created_at__gte=start)
    if end is not None:
        # If the caller passes a plain date, treat it as inclusive of that whole day.
        if end.hour == 0 and end.minute == 0 and end.second == 0:
            end = end + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
        qs = qs.filter(created_at__lte=end)
    return qs


class ShippingAddressViewSet(viewsets.ModelViewSet):
    serializer_class = ShippingAddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        is_admin = (
            user.is_staff
            or hasattr(user, 'admin_profile')
            or getattr(user, 'user_type', '') == 'admin'
        )
        if is_admin:
            return ShippingAddress.objects.all().select_related('user')
        return ShippingAddress.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        address = self.get_object()
        address.is_default = True
        address.save()
        return Response(ShippingAddressSerializer(address).data)


class ShoppingCartViewSet(viewsets.GenericViewSet):
    """
    Retail shopping cart.
    Rules: 1 cart per vendor, max 3 carts per user.
    """
    serializer_class = ShoppingCartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ShoppingCart.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='my-carts')
    def my_carts(self, request):
        carts = ShoppingCart.objects.filter(
            user=request.user
        ).prefetch_related(
            'items__product', 'items__product_variant', 'items__negotiation'
        ).select_related('vendor')
        return Response(ShoppingCartSerializer(carts, many=True).data)

    @action(detail=True, methods=['get'], url_path='detail')
    def cart_detail(self, request, pk=None):
        cart = ShoppingCart.objects.prefetch_related(
            'items__product', 'items__product_variant'
        ).select_related('vendor').get(pk=pk, user=request.user)
        return Response(ShoppingCartSerializer(cart).data)

    @action(detail=False, methods=['post'], url_path='add-item')
    def add_item(self, request):
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data['product']
        variant = serializer.validated_data.get('product_variant')
        quantity = serializer.validated_data.get('quantity', 1)
        negotiation_id = serializer.validated_data.get('negotiation_id')
        product_vendor = product.vendor

        negotiation = None
        if negotiation_id:
            try:
                negotiation = NegotiationRoom.objects.get(
                    id=negotiation_id,
                    buyer=request.user,
                    product=product,
                    status='agreed',
                )
            except NegotiationRoom.DoesNotExist:
                return Response(
                    {'error': 'Invalid or non-agreed negotiation for this product.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        cart = ShoppingCart.objects.filter(
            user=request.user, vendor=product_vendor
        ).first()

        if cart is None:
            current_cart_count = ShoppingCart.objects.filter(user=request.user).count()
            if current_cart_count >= ShoppingCart.MAX_CARTS_PER_USER:
                return Response(
                    {
                        'error': (
                            f'You can only have {ShoppingCart.MAX_CARTS_PER_USER} active carts. '
                            'Please clear or checkout an existing cart before adding items from a new vendor.'
                        ),
                        'current_carts': current_cart_count,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cart = ShoppingCart.objects.create(
                user=request.user,
                vendor=product_vendor,
            )

        defaults = {'quantity': quantity}
        if negotiation:
            defaults['negotiation'] = negotiation
            defaults['price_at_time'] = negotiation.agreed_price

        existing_item = CartItem.objects.filter(
            cart=cart, product=product, product_variant=variant,
        ).first()

        if existing_item:
            existing_item.quantity += quantity
            if negotiation:
                existing_item.negotiation = negotiation
                existing_item.price_at_time = negotiation.agreed_price
            existing_item.save()
            created = False
        else:
            existing_item = CartItem.objects.create(
                cart=cart, product=product, product_variant=variant, **defaults
            )
            created = True

        return Response(
            ShoppingCartSerializer(cart).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='increment-item/(?P<item_id>[^/.]+)')
    def increment_item(self, request, pk=None, item_id=None):
        cart = ShoppingCart.objects.get(pk=pk, user=request.user)
        try:
            cart_item = CartItem.objects.get(cart=cart, id=item_id)
        except CartItem.DoesNotExist:
            return Response({'error': 'Item not found in cart.'}, status=status.HTTP_404_NOT_FOUND)
        cart_item.quantity += 1
        cart_item.save()
        return Response(ShoppingCartSerializer(cart).data)

    @action(detail=True, methods=['post'], url_path='decrement-item/(?P<item_id>[^/.]+)')
    def decrement_item(self, request, pk=None, item_id=None):
        cart = ShoppingCart.objects.get(pk=pk, user=request.user)
        try:
            cart_item = CartItem.objects.get(cart=cart, id=item_id)
        except CartItem.DoesNotExist:
            return Response({'error': 'Item not found in cart.'}, status=status.HTTP_404_NOT_FOUND)
        if cart_item.quantity <= 1:
            cart_item.delete()
            if not cart.items.exists():
                cart.delete()
                return Response({'status': 'cart_deleted', 'message': 'Last item removed. Cart deleted.'})
        else:
            cart_item.quantity -= 1
            cart_item.save()
        return Response(ShoppingCartSerializer(cart).data)

    @action(detail=True, methods=['post'], url_path='remove-item/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        cart = ShoppingCart.objects.get(pk=pk, user=request.user)
        CartItem.objects.filter(cart=cart, id=item_id).delete()
        if not cart.items.exists():
            cart.delete()
            return Response({'status': 'cart_deleted', 'message': 'Cart was empty and has been removed.'})
        return Response(ShoppingCartSerializer(cart).data)

    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        cart = ShoppingCart.objects.get(pk=pk, user=request.user)
        cart.delete()
        return Response({'status': 'cart_deleted'})


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination
    filterset_class = OrderFilter
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Order.objects.select_related('user').prefetch_related(
            'items__product__category',
            'items__vendor',
        )
        user = self.request.user
        is_admin = (
            user.is_staff
            or hasattr(user, 'admin_profile')
            or getattr(user, 'user_type', '') == 'admin'
        )
        if is_admin:
            queryset = queryset.order_by('-created_at')
        else:
            vp = getattr(user, 'vendor_profile', None)
            if vp is not None:
                queryset = queryset.filter(items__vendor=vp).distinct()
            else:
                queryset = queryset.filter(user=user)
        # Apply analytics-style ?period= / ?from= / ?to= filters in addition to
        # the existing OrderFilter (which already supports created_date_from /
        # created_date_to). Both styles are honoured so old clients keep working.
        if self.action == 'list':
            queryset = apply_order_date_filter(queryset, self.request)
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart_id = serializer.validated_data.pop('cart_id')

        try:
            cart = ShoppingCart.objects.select_related(
                'vendor', 'vendor__user'
            ).prefetch_related(
                'items__product', 'items__product_variant', 'items__negotiation'
            ).get(id=cart_id, user=request.user)
        except ShoppingCart.DoesNotExist:
            return Response(
                {'error': 'Cart not found or does not belong to you.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        cart_items = list(cart.items.all())
        if not cart_items:
            return Response(
                {'error': 'Cannot checkout an empty cart.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pending_items = []
        for item in cart_items:
            if item.negotiation and item.negotiation.status == 'expired':
                pending_items.append({
                    'product': item.product.name,
                    'negotiation_id': str(item.negotiation.id),
                    'negotiation_status': 'expired',
                })
            elif item.negotiation and item.negotiation.status != 'agreed':
                pending_items.append({
                    'product': item.product.name,
                    'negotiation_id': str(item.negotiation.id),
                    'negotiation_status': item.negotiation.status,
                })
            elif item.negotiation and item.negotiation.offer_expires_at and item.negotiation.offer_expires_at < timezone.now():
                pending_items.append({
                    'product': item.product.name,
                    'negotiation_id': str(item.negotiation.id),
                    'negotiation_status': 'expired',
                })

        if pending_items:
            return Response(
                {
                    'error': 'Cannot checkout. Some items have negotiations that are not accepted.',
                    'pending_negotiations': pending_items,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            order = serializer.save(user=request.user)

            for item in cart_items:
                unit_price = item.price_at_time or item.original_price
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_variant=item.product_variant,
                    product_name=item.product.name,
                    product_sku=item.product.sku,
                    variant_name=item.product_variant.name if item.product_variant else '',
                    quantity=item.quantity,
                    unit_price=unit_price,
                    total_price=item.quantity * unit_price,
                    vendor=cart.vendor,
                )

            # Auto-calculate delivery fee using the same FareRate logic
            # as POST /api/delivery/calculate-fare/
            if order.fulfillment_type == 'delivery' and order.shipping_address:
                from delivery.services import compute_delivery_fare
                order.shipping_cost = compute_delivery_fare(
                    cart.vendor,
                    order.shipping_address,
                    'retail',
                )

            # Apply promotions + coupon: record redemptions, stamp the
            # discount + coupon code on the order. Guarded so a promotions
            # hiccup can never block a checkout.
            try:
                from promotions.services import commit_cart_discounts
                pricing = commit_cart_discounts(cart, order, request.user)
                order.discount_amount = pricing['total_discount']
                order.vendor_funded_discount = pricing['vendor_funded_discount']
                order.platform_funded_discount = \
                    pricing['platform_funded_discount']
                coupon_info = pricing.get('coupon')
                if coupon_info and not pricing.get('coupon_error'):
                    order.coupon_code = coupon_info['code']
                # Free shipping: the customer pays no delivery, but the driver
                # still earns the fare — the promo/coupon funder absorbs it.
                # Keep shipping_cost (the driver's earnings), discount the fare
                # off the customer total, and charge it to the funder's bucket.
                if pricing.get('free_shipping') \
                        and order.fulfillment_type == 'delivery' \
                        and order.shipping_cost:
                    fare = order.shipping_cost
                    order.discount_amount = order.discount_amount + fare
                    if pricing.get('free_shipping_funder') == 'platform':
                        order.platform_funded_discount = \
                            order.platform_funded_discount + fare
                    else:
                        order.vendor_funded_discount = \
                            order.vendor_funded_discount + fare
            except Exception:
                logger.exception('Promotion application failed for order %s',
                                 getattr(order, 'id', None))

            order.calculate_totals()
            cart.delete()

        # Real-time push so every vendor with items in this order gets the
        # alert + queue refresh the moment checkout completes.
        _push_vendor_order_event(order, event_type='new_order')

        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if not order.can_be_cancelled:
            return Response(
                {'error': 'This order cannot be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        old_status = order.status
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        OrderStatusHistory.objects.create(
            order=order,
            previous_status=old_status,
            new_status='cancelled',
            changed_by=request.user,
            comment='Cancelled by customer',
        )
        _push_vendor_order_event(order, event_type='status_changed')
        return Response(OrderDetailSerializer(order).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsVendorOrAdmin])
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        comment = request.data.get('comment', '')

        user = request.user
        is_admin = (
            user.is_staff
            or user.is_superuser
            or hasattr(user, 'admin_profile')
            or getattr(user, 'user_type', '') == 'admin'
        )

        # Vendors may only update orders that contain their products
        if not is_admin:
            vp = getattr(user, 'vendor_profile', None)
            if vp is None:
                return Response(
                    {'error': 'Vendor profile not found.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not order.items.filter(vendor=vp).exists():
                return Response(
                    {'error': 'You do not have items in this order.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Vendors can only move orders through fulfillment stages
            vendor_allowed = ['confirmed', 'processing', 'shipped', 'delivered']
            if new_status not in vendor_allowed:
                return Response(
                    {'error': f'Vendors can only set status to: {vendor_allowed}'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        valid_statuses = [s[0] for s in Order.ORDER_STATUS_CHOICES]
        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Must be one of: {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = order.status
        order.status = new_status

        if new_status == 'shipped':
            order.shipped_at = timezone.now()
        elif new_status == 'delivered':
            order.delivered_at = timezone.now()

        order.save()
        OrderStatusHistory.objects.create(
            order=order,
            previous_status=old_status,
            new_status=new_status,
            changed_by=request.user,
            comment=comment,
        )

        # Auto-create a delivery job when the order ships and payment is confirmed
        if (new_status == 'shipped'
                and getattr(order, 'fulfillment_type', '') == 'delivery'
                and order.payment_status == 'paid'):
            from delivery.services import create_delivery_job_for_order
            create_delivery_job_for_order(order, 'retail')

        _push_vendor_order_event(order, event_type='status_changed')
        return Response(OrderDetailSerializer(order).data)

    @action(
        detail=True, methods=['post'], url_path='dispatch-delivery',
        permission_classes=[permissions.IsAuthenticated, IsVendorOrAdmin],
    )
    def dispatch_delivery(self, request, pk=None):
        """
        Manually create and dispatch a DeliveryJob for an already-confirmed
        delivery order. Useful when the order was confirmed before the
        auto-dispatch code was deployed.
        """
        order = self.get_object()
        if order.fulfillment_type != 'delivery':
            return Response(
                {'error': 'This order does not require delivery.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from delivery.models import DeliveryJob
        from delivery.services import create_delivery_job_for_order, dispatch_job_to_nearby_drivers
        existing = DeliveryJob.objects.filter(retail_order=order).first()
        if existing:
            # Job already exists — just re-dispatch to any drivers who haven't seen it
            dispatched = dispatch_job_to_nearby_drivers(existing)
            return Response({
                'job_id': str(existing.job_id if hasattr(existing, 'job_id') else existing.id),
                'status': existing.status,
                'drivers_notified': dispatched,
                'detail': 'Job already existed — re-dispatched.',
            })
        job = create_delivery_job_for_order(order, 'retail')
        if job is None:
            return Response(
                {'error': 'Could not create delivery job. Check server logs for details.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            'job_id': str(job.id),
            'status': job.status,
            'distance_km': str(job.distance_km),
            'fare_amount': str(job.fare_amount),
            'detail': 'Delivery job created and dispatched to nearby drivers.',
        }, status=status.HTTP_201_CREATED)


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
    user = request.user
    is_admin = (
        user.is_staff
        or hasattr(user, 'admin_profile')
        or getattr(user, 'user_type', '') == 'admin'
    )
    if not is_admin:
        user_vp = getattr(user, 'vendor_profile', None)
        if user_vp != vp:
            return None, Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
    return vp, None


# ── Retail vendor queue helpers ──────────────────────────────────────────────
#
# Mirrors the restaurant queue (pending → confirmed → processing → shipped):
#   pending:    new orders waiting for vendor acknowledgement
#   confirmed:  vendor has accepted, not yet picked
#   processing: order being packed
#   shipped:    handed over to delivery

RETAIL_QUEUE_STATUSES = ('pending', 'confirmed', 'processing', 'shipped')

# Same urgency model as the restaurant view: 0–20 min normal, 20–40 warning, 40+ urgent.
RETAIL_URGENCY_NORMAL_LIMIT_MIN = 20
RETAIL_URGENCY_WARNING_LIMIT_MIN = 40
RETAIL_URGENT_ALERT_WINDOW_MIN = 60

# Live-queue retention window. Orders older than this are dropped from the
# queue view automatically — they remain in the full orders screen, but the
# vendor's queue UI only ever shows what's actionable right now.
RETAIL_QUEUE_MAX_AGE_HOURS = 24


def _retail_urgency_for(order, now):
    elapsed = (now - order.created_at).total_seconds() / 60.0
    if elapsed < RETAIL_URGENCY_NORMAL_LIMIT_MIN:
        return 'normal', round(elapsed, 1)
    if elapsed < RETAIL_URGENCY_WARNING_LIMIT_MIN:
        return 'warning', round(elapsed, 1)
    return 'urgent', round(elapsed, 1)


class VendorOrderQueueView(generics.GenericAPIView):
    """
    GET /api/orders/vendor/<vendor_uuid>/queue/

    Returns this vendor's retail order queue grouped into kanban-style columns:
    ``pending`` · ``confirmed`` · ``processing`` · ``shipped``. Each order is
    annotated with an ``urgency`` flag (``normal``/``warning``/``urgent``) based
    on how long it has been waiting since it was placed.

    Optional filters:
      ?status=pending|confirmed|processing|shipped  — narrow to one column.
    """
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get(self, request, vendor_uuid):
        vp, err = _resolve_vendor(request, vendor_uuid)
        if err:
            return err

        # Drop orders older than RETAIL_QUEUE_MAX_AGE_HOURS — they're still
        # available in the orders screen, just not in the live queue view.
        now = timezone.now()
        age_cutoff = now - datetime.timedelta(hours=RETAIL_QUEUE_MAX_AGE_HOURS)

        qs = (
            Order.objects
            .filter(
                items__vendor=vp,
                status__in=RETAIL_QUEUE_STATUSES,
                created_at__gte=age_cutoff,
            )
            .distinct()
            .select_related('user')
            .prefetch_related('items__product', 'items__vendor')
            .order_by('created_at')  # oldest first → most urgent
        )

        status_filter = request.query_params.get('status')
        statuses = list(RETAIL_QUEUE_STATUSES)
        if status_filter and status_filter in RETAIL_QUEUE_STATUSES:
            qs = qs.filter(status=status_filter)
            statuses = [status_filter]

        columns = {s: [] for s in statuses}
        urgent_count = 0
        for order in qs:
            data = OrderListSerializer(order).data
            urgency_label, minutes = _retail_urgency_for(order, now)
            data['urgency'] = urgency_label
            data['minutes_waiting'] = minutes
            if urgency_label == 'urgent':
                urgent_count += 1
            columns[order.status].append(data)

        status_labels = dict(Order.ORDER_STATUS_CHOICES) if hasattr(Order, 'ORDER_STATUS_CHOICES') else {}

        return Response({
            'columns': [
                {
                    'status': s,
                    'label': status_labels.get(s, s.replace('_', ' ').title()),
                    'orders': columns[s],
                    'count': len(columns[s]),
                }
                for s in statuses
            ],
            'totals': {
                'in_queue': sum(len(v) for v in columns.values()),
                'urgent': urgent_count,
            },
        })


class VendorOrderPendingAlertsView(generics.GenericAPIView):
    """
    GET /api/orders/vendor/<vendor_uuid>/pending-alerts/

    Returns brand-new ``pending`` retail orders the vendor should acknowledge.
    The UI polls this and pops a bottom-sheet alert for each new order.

    Accepts ``?since=<ISO datetime>`` to fetch only orders placed after the
    client's last poll — perfect for live alerts.
    """
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get(self, request, vendor_uuid):
        vp, err = _resolve_vendor(request, vendor_uuid)
        if err:
            return err

        import datetime as _dt
        now = timezone.now()
        cutoff = now - _dt.timedelta(minutes=RETAIL_URGENT_ALERT_WINDOW_MIN)

        qs = (
            Order.objects
            .filter(
                items__vendor=vp,
                status='pending',
                created_at__gte=cutoff,
            )
            .distinct()
            .select_related('user')
            .prefetch_related('items__product', 'items__vendor')
            .order_by('-created_at')
        )

        since = request.query_params.get('since')
        if since:
            from django.utils.dateparse import parse_datetime
            since_dt = parse_datetime(since)
            if since_dt is not None:
                qs = qs.filter(created_at__gt=since_dt)

        alerts = []
        # Only this vendor's items appear in `items_preview` — we don't leak
        # other vendors' lines that happen to share the same order.
        for order in qs:
            data = OrderListSerializer(order).data
            urgency_label, minutes = _retail_urgency_for(order, now)
            data['urgency'] = urgency_label
            data['minutes_waiting'] = minutes
            vendor_items = list(order.items.filter(vendor=vp)[:8])
            data['items_preview'] = [
                {
                    'name': it.product_name,
                    'variant': it.variant_name or '',
                    'quantity': it.quantity,
                    'special_instructions': '',
                }
                for it in vendor_items
            ]
            data['items_extra'] = max(
                0,
                order.items.filter(vendor=vp).count() - len(vendor_items),
            )
            alerts.append(data)

        return Response({
            'alerts': alerts,
            'count': len(alerts),
            'now': now.isoformat(),
        })


class VendorOrderListView(generics.ListAPIView):
    """
    GET /api/orders/vendor/<vendor_uuid>/orders/

    Supports the same date filtering as the analytics endpoints:
      ?period=today|week|month|year
      ?from=YYYY-MM-DD&to=YYYY-MM-DD
    Plus existing ``?status=`` and ``?payment_status=``.
    """
    serializer_class = OrderListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        vp, err = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if err:
            return Order.objects.none()
        qp = self.request.query_params
        qs = (
            Order.objects
            .filter(items__vendor=vp)
            .distinct()
            .select_related('user')
            .prefetch_related('items__product', 'items__vendor')
            .order_by('-created_at')
        )
        status_filter = qp.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        payment_status = qp.get('payment_status')
        if payment_status:
            qs = qs.filter(payment_status=payment_status)
        qs = apply_order_date_filter(qs, self.request)
        return qs

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)


class VendorDashboardView(generics.GenericAPIView):
    """GET /api/orders/vendor/<vendor_uuid>/dashboard/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, vendor_uuid):
        vp, err = _resolve_vendor(request, vendor_uuid)
        if err:
            return err
        items_qs = OrderItem.objects.filter(vendor=vp)
        stats = items_qs.aggregate(
            total_revenue=Sum('total_price'),
            total_orders=Count('order', distinct=True),
            total_items_sold=Sum('quantity'),
        )
        pending_orders = (
            Order.objects
            .filter(items__vendor=vp, status='pending')
            .distinct().count()
        )
        processing_orders = (
            Order.objects
            .filter(items__vendor=vp, status='processing')
            .distinct().count()
        )
        return Response({
            'vendor_uuid': str(vp.id),
            'total_revenue': stats['total_revenue'] or '0.00',
            'total_orders': stats['total_orders'] or 0,
            'total_items_sold': stats['total_items_sold'] or 0,
            'pending_orders': pending_orders,
            'processing_orders': processing_orders,
        })


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]
    search_fields = ['code', 'name']

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def validate(self, request):
        code = request.data.get('code', '')
        order_amount = request.data.get('order_amount')
        try:
            coupon = Coupon.objects.get(code__iexact=code)
        except Coupon.DoesNotExist:
            return Response(
                {'valid': False, 'message': 'Coupon not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        from decimal import Decimal
        amount = Decimal(str(order_amount)) if order_amount else None
        is_valid, message = coupon.is_valid(user=request.user, order_amount=amount)
        response_data = {'valid': is_valid, 'message': message}
        if is_valid:
            response_data['coupon'] = CouponSerializer(coupon).data
            if amount:
                response_data['discount_amount'] = str(coupon.calculate_discount(amount))
        return Response(response_data)
