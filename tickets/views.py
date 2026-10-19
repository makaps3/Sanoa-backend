"""
REST surface for support tickets.

Customer:
  GET  /api/tickets/                       — my tickets
  POST /api/tickets/                       — open a ticket (first message included)
  GET  /api/tickets/meta/                  — categories / urgencies / targets
  GET  /api/tickets/vendors/?q=            — search vendors to file against

Shared (role-checked — customer / vendor / admin):
  GET  /api/tickets/<id>/                  — ticket header + last 50 messages
  GET  /api/tickets/<id>/messages/         — paginated messages
  POST /api/tickets/<id>/messages/         — reply
  POST /api/tickets/<id>/read/             — mark my side read
  POST /api/tickets/<id>/status/           — change status

Vendor:
  GET  /api/tickets/vendor/                — tickets filed against my store

Admin:
  GET  /api/tickets/admin/                 — every ticket (filters: q, status,
                                             target, urgency, category)
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.service import notify, notify_admins

from .models import Ticket, TicketMessage
from .serializers import TicketMessageSerializer, TicketSerializer
from .ws_broadcast import (
    broadcast_message,
    broadcast_read_marker,
    broadcast_status,
    dismiss_urgent_alert,
    push_urgent_alert,
)


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _is_admin(user):
    return bool(
        user and user.is_authenticated and (
            user.is_staff or user.is_superuser
            or hasattr(user, 'admin_profile')
        )
    )


def _vendor_profile_for(user):
    """The VendorProfile this user acts for (owner or active employee)."""
    vp = getattr(user, 'vendor_profile', None)
    if vp is not None:
        return vp
    emp = getattr(user, 'vendor_employment', None)
    if emp is not None and emp.is_active:
        return emp.vendor
    return None


def _get_ticket_for(user, ticket_id):
    """Return (ticket, role) if `user` may see it, else (None, None)."""
    try:
        ticket = (Ticket.objects
                  .select_related('customer', 'vendor', 'vendor__user')
                  .get(id=ticket_id))
    except (Ticket.DoesNotExist, ValueError):
        return None, None
    role = ticket.role_for(user)
    if role is None:
        return None, None
    return ticket, role


class _MessagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class _IsPlatformAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return _is_admin(request.user)


def _notify_new_ticket(ticket):
    """Notification records + WS pushes for a freshly created ticket."""
    label = dict(Ticket.URGENCY_CHOICES).get(ticket.urgency, ticket.urgency)
    title = f'New {label.lower()}-priority support ticket'
    body = f'{ticket.subject} — {ticket.last_message_preview}'
    data = {
        'ticket_id': str(ticket.id),
        'target_type': ticket.target_type,
        'category': ticket.category,
        'urgency': ticket.urgency,
    }
    try:
        if ticket.target_type == Ticket.TARGET_VENDOR and ticket.vendor:
            notify(
                recipient=ticket.vendor.user,
                notification_type='ticket_created',
                title=title, body=body,
                category='admin', actor=ticket.customer, data=data,
            )
        notify_admins(
            notification_type='ticket_created',
            title=title, body=body,
            actor=ticket.customer, data=data,
        )
    except Exception:  # notification failure must never block the ticket
        pass
    if ticket.needs_alert:
        push_urgent_alert(ticket)


# ────────────────────────────────────────────────────────────────────
# Meta / vendor search
# ────────────────────────────────────────────────────────────────────

class TicketMetaView(APIView):
    """Choice lists so the app never hardcodes them."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        as_pairs = lambda choices: [
            {'value': v, 'label': l} for v, l in choices
        ]
        return Response({
            'targets': as_pairs(Ticket.TARGET_CHOICES),
            'categories': as_pairs(Ticket.CATEGORY_CHOICES),
            'urgencies': as_pairs(Ticket.URGENCY_CHOICES),
            'statuses': as_pairs(Ticket.STATUS_CHOICES),
            'alert_urgencies': list(Ticket.ALERT_URGENCIES),
        })


class TicketVendorSearchView(APIView):
    """Search vendors a customer can file a ticket against."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from business.models import VendorProfile
        qs = VendorProfile.objects.filter(
            verification_status__in=['owner_verified', 'verified'],
        ).order_by('name')
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q) | Q(trading_name__icontains=q))
        return Response({'vendors': [
            {
                'id': str(v.id),
                'name': v.name,
                'business_category': v.business_category,
            }
            for v in qs[:20]
        ]})


# ────────────────────────────────────────────────────────────────────
# Customer — my tickets / create
# ────────────────────────────────────────────────────────────────────

class MyTicketsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = (Ticket.objects
              .select_related('customer', 'vendor', 'vendor__user')
              .filter(customer=request.user))
        st = request.query_params.get('status')
        if st in dict(Ticket.STATUS_CHOICES):
            qs = qs.filter(status=st)
        data = TicketSerializer(
            qs, many=True, context={'request': request}).data
        return Response({'tickets': data})

    def post(self, request):
        target_type = (request.data.get('target_type') or '').strip()
        if target_type not in dict(Ticket.TARGET_CHOICES):
            return Response({'error': "Invalid 'target_type'."},
                            status=status.HTTP_400_BAD_REQUEST)

        category = (request.data.get('category') or '').strip()
        if category not in dict(Ticket.CATEGORY_CHOICES):
            return Response({'error': "Invalid 'category'."},
                            status=status.HTTP_400_BAD_REQUEST)

        urgency = (request.data.get('urgency')
                   or Ticket.URGENCY_NORMAL).strip()
        if urgency not in dict(Ticket.URGENCY_CHOICES):
            return Response({'error': "Invalid 'urgency'."},
                            status=status.HTTP_400_BAD_REQUEST)

        subject = (request.data.get('subject') or '').strip()
        message = (request.data.get('message') or '').strip()
        if not subject:
            return Response({'error': "'subject' is required."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not message:
            return Response({'error': "'message' is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        vendor = None
        if target_type == Ticket.TARGET_VENDOR:
            from business.models import VendorProfile
            vendor_id = request.data.get('vendor_id')
            if not vendor_id:
                return Response(
                    {'error': "'vendor_id' is required for vendor tickets."},
                    status=status.HTTP_400_BAD_REQUEST)
            try:
                vendor = VendorProfile.objects.get(id=vendor_id)
            except (VendorProfile.DoesNotExist, ValueError):
                return Response({'error': 'Vendor not found.'},
                                status=status.HTTP_404_NOT_FOUND)

        ticket = Ticket.objects.create(
            customer=request.user,
            target_type=target_type,
            vendor=vendor,
            category=category,
            urgency=urgency,
            subject=subject[:200],
        )
        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_role='customer',
            kind=TicketMessage.KIND_TEXT,
            body=message[:4000],
        )
        ticket.last_message_at = msg.created_at
        ticket.last_message_preview = message[:140]
        ticket.customer_read_at = msg.created_at
        ticket.save(update_fields=[
            'last_message_at', 'last_message_preview', 'customer_read_at',
        ])

        _notify_new_ticket(ticket)

        return Response(
            TicketSerializer(ticket, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


# ────────────────────────────────────────────────────────────────────
# Vendor — tickets filed against my store
# ────────────────────────────────────────────────────────────────────

class VendorTicketsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        vp = _vendor_profile_for(request.user)
        if vp is None:
            return Response({'error': 'No vendor profile.'},
                            status=status.HTTP_403_FORBIDDEN)
        qs = (Ticket.objects
              .select_related('customer', 'vendor', 'vendor__user')
              .filter(vendor=vp))
        st = request.query_params.get('status')
        if st in dict(Ticket.STATUS_CHOICES):
            qs = qs.filter(status=st)
        data = TicketSerializer(
            qs, many=True, context={'request': request}).data
        return Response({'tickets': data})


# ────────────────────────────────────────────────────────────────────
# Admin — every ticket
# ────────────────────────────────────────────────────────────────────

class AdminTicketsView(APIView):
    permission_classes = [permissions.IsAuthenticated, _IsPlatformAdmin]

    def get(self, request):
        qs = (Ticket.objects
              .select_related('customer', 'vendor', 'vendor__user'))
        params = request.query_params
        q = (params.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(subject__icontains=q)
                | Q(customer__email__icontains=q)
                | Q(vendor__name__icontains=q)
                | Q(last_message_preview__icontains=q)
            )
        for field in ('status', 'target_type', 'urgency', 'category'):
            value = params.get(
                'target' if field == 'target_type' else field)
            if value:
                qs = qs.filter(**{field: value})
        data = TicketSerializer(
            qs[:200], many=True, context={'request': request}).data
        return Response({'tickets': data})


# ────────────────────────────────────────────────────────────────────
# Shared — detail / messages / read / status (role-checked)
# ────────────────────────────────────────────────────────────────────

class TicketDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ticket_id):
        ticket, _role = _get_ticket_for(request.user, ticket_id)
        if ticket is None:
            return Response({'error': 'Ticket not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        messages_qs = (ticket.messages
                       .filter(is_deleted=False)
                       .select_related('sender')
                       .order_by('-created_at')[:50])
        return Response({
            'ticket': TicketSerializer(
                ticket, context={'request': request}).data,
            'messages': TicketMessageSerializer(
                list(reversed(messages_qs)), many=True).data,
        })


class TicketMessagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ticket_id):
        ticket, _role = _get_ticket_for(request.user, ticket_id)
        if ticket is None:
            return Response({'error': 'Ticket not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        qs = (ticket.messages
              .filter(is_deleted=False)
              .select_related('sender')
              .order_by('created_at'))
        paginator = _MessagePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            TicketMessageSerializer(page, many=True).data)

    def post(self, request, ticket_id):
        ticket, role = _get_ticket_for(request.user, ticket_id)
        if ticket is None:
            return Response({'error': 'Ticket not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if ticket.status == Ticket.STATUS_CLOSED:
            return Response({'error': 'This ticket is closed.'},
                            status=status.HTTP_409_CONFLICT)

        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'error': "'body' is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_role=role,
            kind=TicketMessage.KIND_TEXT,
            body=body[:4000],
        )

        ticket.last_message_at = msg.created_at
        ticket.last_message_preview = body[:140]
        fields = ['last_message_at', 'last_message_preview']

        marker = ticket.read_marker_field(role)
        if marker:
            setattr(ticket, marker, msg.created_at)
            fields.append(marker)

        first_response = role != 'customer' \
            and ticket.first_response_at is None
        if first_response:
            ticket.first_response_at = msg.created_at
            fields.append('first_response_at')
            if ticket.status == Ticket.STATUS_OPEN:
                ticket.status = Ticket.STATUS_IN_PROGRESS
                fields.append('status')

        ticket.save(update_fields=fields)

        payload = TicketMessageSerializer(msg).data
        broadcast_message(ticket, payload)

        if first_response:
            # Stop the ringtone on every vendor/admin device.
            dismiss_urgent_alert(ticket)
            broadcast_status(ticket)

        # Tell the customer a response landed (best-effort).
        if role != 'customer':
            try:
                notify(
                    recipient=ticket.customer,
                    notification_type='ticket_reply',
                    title=f'Reply on: {ticket.subject}',
                    body=body[:140],
                    category='account',
                    actor=request.user,
                    data={'ticket_id': str(ticket.id)},
                )
            except Exception:
                pass

        return Response(payload, status=status.HTTP_201_CREATED)


class TicketMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, ticket_id):
        ticket, role = _get_ticket_for(request.user, ticket_id)
        if ticket is None:
            return Response({'error': 'Ticket not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        field = ticket.read_marker_field(role)
        if field is None:
            return Response({'error': 'Not a participant.'},
                            status=status.HTTP_403_FORBIDDEN)
        now = timezone.now()
        setattr(ticket, field, now)
        ticket.save(update_fields=[field])
        broadcast_read_marker(ticket, role, now)
        return Response({'read_at': now.isoformat(), 'role': role})


class TicketStatusView(APIView):
    """Change ticket status.

    customer — may close their own ticket or reopen it.
    vendor / admin — may mark in_progress / resolved / closed.
    """
    permission_classes = [permissions.IsAuthenticated]

    ALLOWED = {
        'customer': {Ticket.STATUS_CLOSED, Ticket.STATUS_OPEN},
        'vendor': {Ticket.STATUS_IN_PROGRESS, Ticket.STATUS_RESOLVED,
                   Ticket.STATUS_CLOSED},
        'admin': {Ticket.STATUS_OPEN, Ticket.STATUS_IN_PROGRESS,
                  Ticket.STATUS_RESOLVED, Ticket.STATUS_CLOSED},
    }

    def post(self, request, ticket_id):
        ticket, role = _get_ticket_for(request.user, ticket_id)
        if ticket is None:
            return Response({'error': 'Ticket not found.'},
                            status=status.HTTP_404_NOT_FOUND)

        new_status = (request.data.get('status') or '').strip()
        if new_status not in dict(Ticket.STATUS_CHOICES):
            return Response({'error': "Invalid 'status'."},
                            status=status.HTTP_400_BAD_REQUEST)
        if new_status not in self.ALLOWED.get(role, set()):
            return Response({'error': 'Not allowed for your role.'},
                            status=status.HTTP_403_FORBIDDEN)
        if new_status == ticket.status:
            return Response(TicketSerializer(
                ticket, context={'request': request}).data)

        ticket.status = new_status
        fields = ['status']
        if new_status == Ticket.STATUS_CLOSED:
            ticket.closed_at = timezone.now()
            fields.append('closed_at')
        elif ticket.closed_at is not None:
            ticket.closed_at = None
            fields.append('closed_at')
        ticket.save(update_fields=fields)

        label = dict(Ticket.STATUS_CHOICES)[new_status]
        TicketMessage.objects.create(
            ticket=ticket,
            sender=request.user,
            sender_role='system',
            kind=TicketMessage.KIND_SYSTEM,
            body=f'Ticket marked as {label.lower()} by {role}.',
        )
        broadcast_status(ticket)
        if ticket.first_response_at is None:
            # Resolving/closing an unanswered urgent ticket also
            # silences the alert.
            dismiss_urgent_alert(ticket)

        return Response(TicketSerializer(
            ticket, context={'request': request}).data)
