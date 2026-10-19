"""
REST surface for the chat module.

  GET  /api/chat/conversations/                — my conversations
  GET  /api/chat/conversations/<id>/            — one conversation + last messages
  GET  /api/chat/conversations/<id>/messages/   — paginated messages
  POST /api/chat/conversations/<id>/messages/   — send a message
  POST /api/chat/conversations/<id>/read/       — mark this side read

Admin (platform_admin staff or admin_profile):
  GET  /api/chat/admin/conversations/            — every conversation
  GET  /api/chat/admin/conversations/<id>/       — read-only inspection
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from .ws_broadcast import broadcast_message, broadcast_read_marker


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


def _get_conversation_for(user, conv_id, *, admin_ok=True):
    """Return the conversation if `user` may see it, else None."""
    try:
        conv = (Conversation.objects
                .select_related('customer', 'driver', 'delivery_job')
                .get(id=conv_id))
    except Conversation.DoesNotExist:
        return None
    if conv.customer_id == user.id or conv.driver_id == user.id:
        return conv
    if admin_ok and _is_admin(user):
        return conv
    return None


class _MessagePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


# ────────────────────────────────────────────────────────────────────
# Customer / driver — own conversations
# ────────────────────────────────────────────────────────────────────

class MyConversationsView(APIView):
    """List the caller's conversations."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        qs = (Conversation.objects
              .select_related('customer', 'driver', 'delivery_job')
              .filter(Q(customer=user) | Q(driver=user))
              .order_by('-last_message_at', '-created_at'))
        data = ConversationSerializer(
            qs, many=True, context={'request': request}).data
        return Response({'conversations': data})


class ConversationByDeliveryJobView(APIView):
    """Resolve the chat for a delivery job — opened from the active
    job / active delivery sheets in the app. The caller must be the
    customer, the driver, or a platform admin.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        try:
            conv = (Conversation.objects
                    .select_related('customer', 'driver', 'delivery_job')
                    .get(delivery_job_id=job_id))
        except Conversation.DoesNotExist:
            return Response(
                {'error': 'No chat exists for this delivery yet.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if conv.customer_id != request.user.id \
                and conv.driver_id != request.user.id \
                and not _is_admin(request.user):
            return Response({'error': 'Forbidden.'},
                            status=status.HTTP_403_FORBIDDEN)
        return Response({
            'conversation': ConversationSerializer(
                conv, context={'request': request}).data,
        })


class ConversationDetailView(APIView):
    """One conversation header + its last 50 messages."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, conv_id):
        conv = _get_conversation_for(request.user, conv_id)
        if conv is None:
            return Response({'error': 'Conversation not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        messages_qs = (conv.messages
                       .filter(is_deleted=False)
                       .select_related('sender')
                       .order_by('-created_at')[:50])
        return Response({
            'conversation': ConversationSerializer(
                conv, context={'request': request}).data,
            'messages': MessageSerializer(
                list(reversed(messages_qs)), many=True).data,
        })


class ConversationMessagesView(APIView):
    """Paginated messages, oldest→newest by default. POST to send."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, conv_id):
        conv = _get_conversation_for(request.user, conv_id)
        if conv is None:
            return Response({'error': 'Conversation not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        qs = (conv.messages
              .filter(is_deleted=False)
              .select_related('sender')
              .order_by('created_at'))
        paginator = _MessagePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            MessageSerializer(page, many=True).data)

    def post(self, request, conv_id):
        conv = _get_conversation_for(request.user, conv_id, admin_ok=False)
        if conv is None:
            return Response({'error': 'Conversation not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if conv.status == Conversation.STATUS_CLOSED:
            return Response(
                {'error': 'This conversation is closed.'},
                status=status.HTTP_409_CONFLICT,
            )

        kind = (request.data.get('kind') or Message.KIND_TEXT).strip()
        if kind not in dict(Message.KIND_CHOICES):
            return Response({'error': "Unknown 'kind'."},
                            status=status.HTTP_400_BAD_REQUEST)

        body = (request.data.get('body') or '').strip()
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')

        if kind == Message.KIND_TEXT and not body:
            return Response({'error': "'body' is required for text."},
                            status=status.HTTP_400_BAD_REQUEST)
        if kind == Message.KIND_LOCATION and (lat is None or lng is None):
            return Response(
                {'error': "'latitude' and 'longitude' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        msg = Message.objects.create(
            conversation=conv,
            sender=request.user,
            kind=kind,
            body=body[:4000],
            latitude=lat,
            longitude=lng,
        )

        # Update conversation header + reset other side's read marker.
        conv.last_message_at = msg.created_at
        conv.last_message_preview = (
            body[:140] if kind == Message.KIND_TEXT
            else f'[{kind}]'
        )
        fields = ['last_message_at', 'last_message_preview']
        # Mark sender's own side as read up to this message.
        if conv.customer_id == request.user.id:
            conv.customer_read_at = msg.created_at
            fields.append('customer_read_at')
        elif conv.driver_id == request.user.id:
            conv.driver_read_at = msg.created_at
            fields.append('driver_read_at')
        conv.save(update_fields=fields)

        payload = MessageSerializer(msg).data
        broadcast_message(conv, payload)
        return Response(payload, status=status.HTTP_201_CREATED)


class ConversationMarkReadView(APIView):
    """Stamp the caller's side as read up to *now*."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, conv_id):
        conv = _get_conversation_for(request.user, conv_id, admin_ok=False)
        if conv is None:
            return Response({'error': 'Conversation not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        now = timezone.now()
        if conv.customer_id == request.user.id:
            conv.customer_read_at = now
            conv.save(update_fields=['customer_read_at'])
            role = 'customer'
        elif conv.driver_id == request.user.id:
            conv.driver_read_at = now
            conv.save(update_fields=['driver_read_at'])
            role = 'driver'
        else:
            return Response({'error': 'Not a participant.'},
                            status=status.HTTP_403_FORBIDDEN)
        broadcast_read_marker(conv, role, now)
        return Response({'read_at': now.isoformat(), 'role': role})


# ────────────────────────────────────────────────────────────────────
# Platform admin — read-only oversight
# ────────────────────────────────────────────────────────────────────

class _IsPlatformAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return _is_admin(request.user)


class AdminConversationsListView(APIView):
    permission_classes = [permissions.IsAuthenticated, _IsPlatformAdmin]

    def get(self, request):
        qs = (Conversation.objects
              .select_related('customer', 'driver', 'delivery_job')
              .order_by('-last_message_at', '-created_at'))
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(customer__email__icontains=q)
                | Q(driver__email__icontains=q)
                | Q(last_message_preview__icontains=q)
            )
        st = request.query_params.get('status')
        if st in {Conversation.STATUS_OPEN, Conversation.STATUS_CLOSED}:
            qs = qs.filter(status=st)
        data = ConversationSerializer(
            qs[:200], many=True, context={'request': request}).data
        return Response({'conversations': data})


class AdminConversationDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, _IsPlatformAdmin]

    def get(self, request, conv_id):
        conv = get_object_or_404(
            Conversation.objects.select_related(
                'customer', 'driver', 'delivery_job'),
            id=conv_id,
        )
        qs = (conv.messages.select_related('sender')
              .order_by('created_at'))
        paginator = _MessagePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        body = paginator.get_paginated_response(
            MessageSerializer(page, many=True).data).data
        body['conversation'] = ConversationSerializer(
            conv, context={'request': request}).data
        return Response(body)
