from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.pagination import StandardPagination
from .models import (
    RestaurantCart, RestaurantCartItem,
    RestaurantOrder, RestaurantOrderItem,
    KitchenTicket, RestaurantOrderTrackingEvent,
)
from .serializers import (
    RestaurantCartSerializer, RestaurantCartItemSerializer,
    RestaurantOrderListSerializer, RestaurantOrderDetailSerializer,
    RestaurantOrderCreateSerializer,
    KitchenTicketSerializer,
    RestaurantOrderTrackingEventSerializer,
)


def _push_tracking_event(order, event_type, message, metadata=None):
    """Create a tracking event and broadcast it over WebSocket."""
    event = RestaurantOrderTrackingEvent.objects.create(
        order=order,
        event_type=event_type,
        message=message,
        metadata=metadata or {},
    )
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        group_name = f"restaurant_order_{order.id}"
        async_to_sync(channel_layer.group_send)(group_name, {
            'type': 'order_update',
            'event_type': event_type,
            'message': message,
            'metadata': metadata or {},
            'order_status': order.status,
            'created_at': event.created_at.isoformat(),
        })
    except Exception:
        pass
    return event


def _push_vendor_kitchen_event(order, *, event_type):
    """
    Push an order event to the vendor's kitchen WebSocket group so the
    queue + alert UI updates in real time.

    Event types:
      ``new_order``       — a brand-new pending order arrived. Frontend pops
                            an alert.
      ``status_changed``  — an order moved between queue statuses. Frontend
                            refreshes the queue columns.
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        group_name = f"kitchen_vendor_{order.vendor_id}"
        payload = {
            'type': event_type,  # channels routes to method of this name
            'event_type': event_type,
            'order_id': str(order.id),
            'order_number': order.order_number,
            'status': order.status,
            'payment_status': order.payment_status,
            'fulfillment_type': order.fulfillment_type,
            'items_count': order.items.count() if order.pk else 0,
            # `total_amount` is the customer-paid gross. The kitchen
            # cards show `subtotal` (items only) so service +
            # delivery fees don't appear as part of "the order
            # price". `vendor_payout` is the after-commission
            # take-home.
            'total_amount': str(order.total_amount),
            'subtotal': str(order.subtotal),
            'vendor_payout': str(order.vendor_payout),
            'created_at': order.created_at.isoformat() if order.created_at else None,
            'updated_at': order.updated_at.isoformat() if order.updated_at else None,
        }
        async_to_sync(channel_layer.group_send)(group_name, payload)
    except Exception:
        # Real-time push is best-effort — the polling fallback covers gaps.
        pass


class RestaurantCartViewSet(viewsets.GenericViewSet):
    """
    Restaurant cart endpoints.

    One cart per vendor per customer, capped at MAX_CARTS_PER_USER
    (3) total carts per user — mirrors the retail ShoppingCart rule
    so customers don't accumulate stale half-built orders. The cap is
    enforced by `add_item` when the user tries to open a cart at a
    vendor they aren't already shopping with.
    """
    serializer_class = RestaurantCartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RestaurantCart.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='my-carts')
    def my_carts(self, request):
        carts = RestaurantCart.objects.filter(user=request.user).prefetch_related(
            'items__product', 'items__product_variant'
        ).select_related('vendor')
        return Response(
            RestaurantCartSerializer(
                carts, many=True, context={'request': request},
            ).data
        )

    # Method name avoids `detail` — DRF's router passes `detail=True`
    # into `as_view`, which `View.__init__` setattrs onto the instance.
    # That overwrites the bound method with a bool and dispatch then
    # crashes with "'bool' object is not callable". Keep the public
    # URL by setting `url_path='detail'`.
    @action(detail=True, methods=['get'], url_path='detail')
    def cart_detail(self, request, pk=None):
        cart = RestaurantCart.objects.prefetch_related(
            'items__product', 'items__product_variant'
        ).select_related('vendor').get(pk=pk, user=request.user)
        return Response(RestaurantCartSerializer(cart, context={'request': request}).data)

    @action(detail=False, methods=['post'], url_path='add-item')
    def add_item(self, request):
        serializer = RestaurantCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = serializer.validated_data['product']
        variant = serializer.validated_data.get('product_variant')
        quantity = serializer.validated_data.get('quantity', 1)
        instructions = serializer.validated_data.get('special_instructions', '')
        addons = serializer.validated_data.get('selected_addons') or []
        product_vendor = product.vendor

        # Cap at MAX_CARTS_PER_USER (3). The cap only applies when
        # opening a NEW cart at a vendor the user isn't already shopping
        # with — adding items to an existing cart is always allowed.
        existing_cart = RestaurantCart.objects.filter(
            user=request.user, vendor=product_vendor,
        ).first()
        if existing_cart is None:
            current_count = RestaurantCart.objects.filter(
                user=request.user,
            ).count()
            if current_count >= RestaurantCart.MAX_CARTS_PER_USER:
                return Response(
                    {
                        'error': (
                            f"You already have {RestaurantCart.MAX_CARTS_PER_USER} "
                            "restaurant carts open. Check out or clear one before "
                            "starting a new order."
                        ),
                        'code': 'cart_limit_reached',
                        'limit': RestaurantCart.MAX_CARTS_PER_USER,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        cart, _ = RestaurantCart.objects.get_or_create(
            user=request.user, vendor=product_vendor,
        )

        # Same product+variant+addons signature = same line; otherwise new line
        existing_item = None
        if not addons and not instructions:
            existing_item = RestaurantCartItem.objects.filter(
                cart=cart, product=product, product_variant=variant,
                selected_addons=[],
                special_instructions='',
            ).first()

        if existing_item:
            existing_item.quantity += quantity
            existing_item.save()
            created = False
        else:
            existing_item = RestaurantCartItem.objects.create(
                cart=cart,
                product=product,
                product_variant=variant,
                quantity=quantity,
                special_instructions=instructions,
                selected_addons=addons,
            )
            created = True

        return Response(
            RestaurantCartSerializer(cart, context={'request': request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'], url_path='increment-item/(?P<item_id>[^/.]+)')
    def increment_item(self, request, pk=None, item_id=None):
        cart = RestaurantCart.objects.get(pk=pk, user=request.user)
        try:
            item = RestaurantCartItem.objects.get(cart=cart, id=item_id)
        except RestaurantCartItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)
        item.quantity += 1
        item.save()
        return Response(RestaurantCartSerializer(cart, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='decrement-item/(?P<item_id>[^/.]+)')
    def decrement_item(self, request, pk=None, item_id=None):
        cart = RestaurantCart.objects.get(pk=pk, user=request.user)
        try:
            item = RestaurantCartItem.objects.get(cart=cart, id=item_id)
        except RestaurantCartItem.DoesNotExist:
            return Response({'error': 'Item not found.'}, status=status.HTTP_404_NOT_FOUND)
        if item.quantity <= 1:
            item.delete()
            if not cart.items.exists():
                cart.delete()
                return Response({'status': 'cart_deleted'})
        else:
            item.quantity -= 1
            item.save()
        return Response(RestaurantCartSerializer(cart, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='remove-item/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        cart = RestaurantCart.objects.get(pk=pk, user=request.user)
        RestaurantCartItem.objects.filter(cart=cart, id=item_id).delete()
        if not cart.items.exists():
            cart.delete()
            return Response({'status': 'cart_deleted'})
        return Response(RestaurantCartSerializer(cart, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        cart = RestaurantCart.objects.get(pk=pk, user=request.user)
        cart.delete()
        return Response({'status': 'cart_deleted'})


class RestaurantOrderViewSet(viewsets.ModelViewSet):
    """Customer-facing restaurant order CRUD."""
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = RestaurantOrder.objects.select_related('user', 'vendor').prefetch_related(
            'items', 'tracking_events',
        )
        if self.request.user.is_staff:
            qs = qs
        elif getattr(self.request.user, 'user_type', None) == 'vendor':
            from business.models import VendorProfile
            try:
                vp = VendorProfile.objects.get(user=self.request.user)
                qs = qs.filter(vendor=vp)
            except VendorProfile.DoesNotExist:
                return qs.none()
        else:
            qs = qs.filter(user=self.request.user)
        # Apply the same analytics-style date filters used by the marketplace
        # orders endpoint (?period= / ?from= / ?to= / status / payment_status).
        if self.action == 'list':
            from orders.views import apply_order_date_filter
            qp = self.request.query_params
            status_filter = qp.get('status')
            if status_filter:
                qs = qs.filter(status=status_filter)
            payment_status = qp.get('payment_status')
            if payment_status:
                qs = qs.filter(payment_status=payment_status)
            qs = apply_order_date_filter(qs, self.request)
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return RestaurantOrderListSerializer
        if self.action == 'create':
            return RestaurantOrderCreateSerializer
        return RestaurantOrderDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart_id = serializer.validated_data.pop('cart_id')
        try:
            cart = RestaurantCart.objects.select_related('vendor').prefetch_related(
                'items__product', 'items__product_variant', 'items__negotiation',
            ).get(id=cart_id, user=request.user)
        except RestaurantCart.DoesNotExist:
            # A bare 404 here is impossible to diagnose. The usual cause is a
            # RETAIL cart id posted to the restaurant checkout — which happens
            # when a vendor's `business_category` doesn't match the storefront
            # the customer shopped in. Say so explicitly.
            from orders.models import ShoppingCart
            retail = ShoppingCart.objects.select_related('vendor').filter(
                id=cart_id, user=request.user).first()
            if retail is not None:
                return Response({
                    'detail': (
                        f"This basket is from {retail.vendor.name or 'a store'}, "
                        'which checks out through the shop — not the restaurant '
                        'flow. Please complete this order from your cart.'
                    ),
                    'code': 'wrong_checkout_for_cart',
                    'business_category': retail.vendor.business_category,
                }, status=status.HTTP_400_BAD_REQUEST)
            return Response(
                {'detail': "We couldn't find that basket. It may have already "
                           'been checked out — please add your items again.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        cart_items = list(cart.items.all())
        if not cart_items:
            return Response(
                {'error': 'Cannot checkout an empty cart.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mirror the retail orders gate: block checkout when any item is
        # tied to a negotiation room that hasn't been finalized by the
        # vendor — `pending_vendor`, `expired`, `cancelled` all fail.
        pending_items = []
        for item in cart_items:
            neg = item.negotiation
            if not neg:
                continue
            if neg.status == 'expired' or (
                neg.offer_expires_at and neg.offer_expires_at < timezone.now()
                and neg.status != 'agreed'
            ):
                pending_items.append({
                    'product': item.product.name,
                    'negotiation_id': str(neg.id),
                    'negotiation_status': 'expired',
                })
            elif neg.status != 'agreed':
                pending_items.append({
                    'product': item.product.name,
                    'negotiation_id': str(neg.id),
                    'negotiation_status': neg.status,
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
            order = serializer.save(user=request.user, vendor=cart.vendor)

            for item in cart_items:
                addons_total = item.addons_total
                unit_price = item.price_at_time or Decimal('0.00')
                total_price = item.quantity * (unit_price + addons_total)
                RestaurantOrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_variant=item.product_variant,
                    product_name=item.product.name,
                    product_sku=item.product.sku,
                    variant_name=item.product_variant.name if item.product_variant else '',
                    quantity=item.quantity,
                    unit_price=unit_price,
                    addons_total=addons_total,
                    total_price=total_price,
                    special_instructions=item.special_instructions,
                    selected_addons=item.selected_addons or [],
                    vendor=cart.vendor,
                )

            # Auto-calculate delivery fee using the same FareRate logic
            # as POST /api/delivery/calculate-fare/
            if order.fulfillment_type == 'delivery' and order.shipping_address:
                from delivery.services import compute_delivery_fare
                order.delivery_fee = compute_delivery_fare(
                    cart.vendor,
                    order.shipping_address,
                    'restaurant',
                )

            order.calculate_totals()
            cart.delete()

            _push_tracking_event(order, 'order_placed', 'Your order has been placed.')

        # Real-time push to the vendor's queue/alert WebSocket so they're
        # notified the moment a customer checks out.
        _push_vendor_kitchen_event(order, event_type='new_order')

        return Response(
            RestaurantOrderDetailSerializer(order).data,
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
        order.status = 'cancelled'
        order.save(update_fields=['status', 'updated_at'])
        _push_tracking_event(order, 'cancelled', 'Order has been cancelled.')
        _push_vendor_kitchen_event(order, event_type='status_changed')
        return Response(RestaurantOrderDetailSerializer(order).data)

    @action(detail=True, methods=['post'], url_path='update-status',
            permission_classes=[permissions.IsAuthenticated])
    def update_status(self, request, pk=None):
        """
        Admin or vendor: move order through the status flow.

        Vendor flow (must own the order):
          pending → confirmed → preparing → ready → out_for_delivery → delivered → completed

        Admin can set any valid status including cancelled / refunded.
        """
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

        # Vendor ownership + status restriction
        if not is_admin:
            vp = getattr(user, 'vendor_profile', None)
            if vp is None:
                return Response(
                    {'error': 'Vendor profile not found.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if order.vendor != vp:
                return Response(
                    {'error': 'You do not own this order.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Vendors move orders through fulfillment stages only
            vendor_allowed = ['confirmed', 'preparing', 'ready', 'out_for_delivery', 'delivered', 'completed']
            if new_status not in vendor_allowed:
                return Response(
                    {'error': f'Vendors can only set status to: {vendor_allowed}'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        valid = [s[0] for s in RestaurantOrder.STATUS_CHOICES]
        if new_status not in valid:
            return Response(
                {'error': f'Invalid status. Must be one of: {valid}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = order.status
        order.status = new_status
        now = timezone.now()

        if new_status == 'confirmed':
            order.confirmed_at = now
            # Create kitchen ticket if not already present
            KitchenTicket.objects.get_or_create(order=order)
        elif new_status == 'ready':
            order.ready_at = now
        elif new_status == 'delivered':
            order.delivered_at = now

        order.save()
        _push_tracking_event(order, new_status, comment or f'Order is now {new_status}.')
        _push_vendor_kitchen_event(order, event_type='status_changed')

        # Auto-create a delivery job when the order goes out for delivery and payment is confirmed
        if (new_status == 'out_for_delivery'
                and getattr(order, 'fulfillment_type', '') == 'delivery'
                and order.payment_status == 'paid'):
            from delivery.services import create_delivery_job_for_order
            create_delivery_job_for_order(order, 'restaurant')

        return Response(RestaurantOrderDetailSerializer(order).data)

    @action(detail=True, methods=['get'])
    def tracking(self, request, pk=None):
        """Customer: get all tracking events for an order."""
        order = self.get_object()
        events = order.tracking_events.order_by('created_at')
        return Response(RestaurantOrderTrackingEventSerializer(events, many=True).data)

    # ── Queue + alerts (vendor-facing) ─────────────────────────────────

    # Statuses considered "in the queue" — orders the kitchen actively works on.
    QUEUE_STATUSES = ('pending', 'confirmed', 'preparing', 'ready')

    # Urgency thresholds (minutes since order was placed).
    URGENCY_NORMAL_LIMIT_MIN = 20      # 0–20 min → normal
    URGENCY_WARNING_LIMIT_MIN = 40     # 20–40 min → warning
    # 40+ min → urgent (red); we cap the urgent window at 60 min for alerts.
    URGENT_ALERT_WINDOW_MIN = 60

    # Live-queue retention window. Orders older than this are dropped from
    # the queue view automatically — they remain in the full orders screen,
    # but the kitchen UI only ever shows what's actionable *right now*.
    QUEUE_MAX_AGE_HOURS = 24

    def _vendor_for_request(self, request):
        """Resolve the authenticated vendor profile, or ``None``."""
        from business.models import VendorProfile
        user = request.user
        if user.is_staff or getattr(user, 'user_type', '') == 'admin':
            return None  # admin sees everything via queryset filter
        try:
            return VendorProfile.objects.get(user=user)
        except VendorProfile.DoesNotExist:
            return None

    @staticmethod
    def _urgency_for(order, now):
        """
        Categorise an order by how long it has been waiting in the queue.
        Returns ``(label, minutes_waiting)``.
        """
        elapsed = (now - order.created_at).total_seconds() / 60.0
        if elapsed < RestaurantOrderViewSet.URGENCY_NORMAL_LIMIT_MIN:
            label = 'normal'
        elif elapsed < RestaurantOrderViewSet.URGENCY_WARNING_LIMIT_MIN:
            label = 'warning'
        else:
            label = 'urgent'
        return label, round(elapsed, 1)

    @action(
        detail=False, methods=['get'], url_path='queue',
        permission_classes=[permissions.IsAuthenticated],
    )
    def queue(self, request):
        """
        Vendor order queue — every in-flight restaurant order grouped by
        kitchen status (``pending``, ``confirmed``, ``preparing``, ``ready``).

        Each order is annotated with an ``urgency`` flag based on how long it
        has been sitting in the queue, so the UI can highlight stale orders.

        Optional query params:
          ?status=pending|confirmed|preparing|ready  — narrow to one column.
          ?fulfillment=delivery|pickup               — filter pickup vs. delivery.
        """
        vp = self._vendor_for_request(request)
        qs = RestaurantOrder.objects.select_related(
            'user', 'vendor',
        ).prefetch_related('items', 'kitchen_ticket')

        if vp is not None:
            qs = qs.filter(vendor=vp)

        statuses = list(self.QUEUE_STATUSES)
        status_filter = request.query_params.get('status')
        if status_filter and status_filter in self.QUEUE_STATUSES:
            statuses = [status_filter]

        qs = qs.filter(status__in=statuses)

        # Drop orders older than QUEUE_MAX_AGE_HOURS from the queue view.
        # They stay in the full orders screen — this is just a visibility cap.
        from datetime import timedelta
        now = timezone.now()
        age_cutoff = now - timedelta(hours=self.QUEUE_MAX_AGE_HOURS)
        qs = qs.filter(created_at__gte=age_cutoff)

        fulfillment = request.query_params.get('fulfillment')
        if fulfillment in ('delivery', 'pickup'):
            qs = qs.filter(fulfillment_type=fulfillment)

        qs = qs.order_by('created_at')  # oldest first — they're the most urgent

        columns = {s: [] for s in self.QUEUE_STATUSES}
        urgent_count = 0
        for order in qs:
            data = RestaurantOrderListSerializer(order).data
            urgency_label, minutes = self._urgency_for(order, now)
            data['urgency'] = urgency_label
            data['minutes_waiting'] = minutes
            if urgency_label == 'urgent':
                urgent_count += 1
            columns[order.status].append(data)

        return Response({
            'columns': [
                {
                    'status': s,
                    'label': dict(RestaurantOrder.STATUS_CHOICES).get(s, s),
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

    @action(
        detail=False, methods=['get'], url_path='pending-alerts',
        permission_classes=[permissions.IsAuthenticated],
    )
    def pending_alerts(self, request):
        """
        Returns brand-new ``pending`` orders the vendor should acknowledge.

        The UI polls this endpoint and pops a bottom-sheet alert for each new
        pending order. An order is included when it's been pending for less
        than ``URGENT_ALERT_WINDOW_MIN`` (60 minutes) — anything older has
        already been escalated through the queue's "urgent" view.
        """
        vp = self._vendor_for_request(request)
        if vp is None and not (request.user.is_staff or getattr(request.user, 'user_type', '') == 'admin'):
            return Response({'alerts': [], 'count': 0})

        from datetime import timedelta
        now = timezone.now()
        cutoff = now - timedelta(minutes=self.URGENT_ALERT_WINDOW_MIN)

        qs = RestaurantOrder.objects.select_related('user', 'vendor').prefetch_related('items')
        qs = qs.filter(status='pending', created_at__gte=cutoff)
        if vp is not None:
            qs = qs.filter(vendor=vp)
        qs = qs.order_by('-created_at')

        # Optional ``?since=<ISO datetime>`` so the client only gets orders
        # placed after its last poll — perfect for live alerts.
        since = request.query_params.get('since')
        if since:
            try:
                from django.utils.dateparse import parse_datetime
                since_dt = parse_datetime(since)
                if since_dt is not None:
                    qs = qs.filter(created_at__gt=since_dt)
            except (TypeError, ValueError):
                pass

        alerts = []
        for order in qs:
            data = RestaurantOrderListSerializer(order).data
            urgency_label, minutes = self._urgency_for(order, now)
            data['urgency'] = urgency_label
            data['minutes_waiting'] = minutes
            # Inline an item summary so the alert sheet can show what was
            # ordered without a second round-trip. Cap at 8 lines — beyond
            # that we expose `extra` so the UI can render "+N more".
            items = list(order.items.all()[:8])
            data['items_preview'] = [
                {
                    'name': it.product_name,
                    'variant': it.variant_name or '',
                    'quantity': it.quantity,
                    'special_instructions': it.special_instructions or '',
                }
                for it in items
            ]
            data['items_extra'] = max(0, order.items.count() - len(items))
            alerts.append(data)

        return Response({
            'alerts': alerts,
            'count': len(alerts),
            'now': now.isoformat(),
        })


class KitchenTicketViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Vendor kitchen dashboard.
    Vendors see their own tickets; admins see all.
    """
    serializer_class = KitchenTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = KitchenTicket.objects.select_related(
            'order__vendor', 'order__user',
        ).prefetch_related('order__items')

        user = self.request.user
        if user.is_staff:
            return qs
        if getattr(user, 'user_type', None) == 'vendor':
            from business.models import VendorProfile
            try:
                vp = VendorProfile.objects.get(user=user)
                return qs.filter(order__vendor=vp)
            except VendorProfile.DoesNotExist:
                return qs.none()
        return qs.none()

    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        ticket = self.get_object()
        if ticket.status != 'new':
            return Response({'error': 'Ticket already acknowledged.'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        ticket.status = 'acknowledged'
        ticket.acknowledged_at = now
        ticket.save(update_fields=['status', 'acknowledged_at', 'updated_at'])
        return Response(KitchenTicketSerializer(ticket).data)

    @action(detail=True, methods=['post'], url_path='start-preparing')
    def start_preparing(self, request, pk=None):
        ticket = self.get_object()
        if ticket.status not in ('new', 'acknowledged'):
            return Response({'error': 'Ticket is not in a preparable state.'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        ticket.status = 'preparing'
        ticket.started_at = now
        ticket.save(update_fields=['status', 'started_at', 'updated_at'])

        order = ticket.order
        order.status = 'preparing'
        order.save(update_fields=['status', 'updated_at'])
        _push_tracking_event(order, 'preparing', 'The kitchen is preparing your order.')
        _push_vendor_kitchen_event(order, event_type='status_changed')
        return Response(KitchenTicketSerializer(ticket).data)

    @action(detail=True, methods=['post'], url_path='mark-ready')
    def mark_ready(self, request, pk=None):
        ticket = self.get_object()
        if ticket.status != 'preparing':
            return Response({'error': 'Ticket is not in preparing state.'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        ticket.status = 'ready'
        ticket.ready_at = now
        ticket.save(update_fields=['status', 'ready_at', 'updated_at'])

        order = ticket.order
        order.status = 'ready'
        order.ready_at = now
        order.save(update_fields=['status', 'ready_at', 'updated_at'])

        msg = 'Your order is ready for pickup!' if order.fulfillment_type == 'pickup' else 'Your order is ready and waiting for a driver.'
        _push_tracking_event(order, 'ready', msg)
        _push_vendor_kitchen_event(order, event_type='status_changed')
        return Response(KitchenTicketSerializer(ticket).data)

    @action(detail=True, methods=['post'], url_path='hand-off')
    def hand_off(self, request, pk=None):
        """Mark food as handed to driver / customer for pickup."""
        ticket = self.get_object()
        if ticket.status != 'ready':
            return Response({'error': 'Ticket is not ready yet.'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        ticket.status = 'handed_off'
        ticket.handed_off_at = now
        ticket.save(update_fields=['status', 'handed_off_at', 'updated_at'])

        order = ticket.order
        if order.fulfillment_type == 'delivery':
            order.status = 'out_for_delivery'
            _push_tracking_event(order, 'out_for_delivery', 'Your order is on its way!')
        else:
            # pickup: customer collects
            order.status = 'completed'
            order.delivered_at = now
            _push_tracking_event(order, 'completed', 'Order ready for pickup. Enjoy!')
        order.save(update_fields=['status', 'delivered_at', 'updated_at'])
        _push_vendor_kitchen_event(order, event_type='status_changed')
        return Response(KitchenTicketSerializer(ticket).data)
