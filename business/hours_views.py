"""
Vendor-facing endpoints for managing the store's operating hours and its
open/closed state. All endpoints act on the authenticated user's own
``VendorProfile`` — there is no id in the path.

    GET    /api/business/me/operating-hours/          → list Mon–Sun hours
    PUT    /api/business/me/operating-hours/          → replace all 7 days
    PATCH  /api/business/me/operating-hours/<day>/    → set one day
    DELETE /api/business/me/operating-hours/<day>/    → mark one day closed

    GET    /api/business/me/store-status/             → open/closed state
    PATCH  /api/business/me/store-status/             → toggle manual close
"""
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VendorProfile
from .store_ops import (
    HoursError, build_opening_hours, serialize_hours, set_day, sync_open_state,
)


def _get_profile(request):
    """The caller's own vendor profile, or ``None``."""
    return VendorProfile.objects.filter(user=request.user).first()


def _no_profile_response():
    return Response(
        {'detail': 'No vendor profile for this user.'},
        status=status.HTTP_404_NOT_FOUND,
    )


def _hours_payload(profile):
    return {
        'operating_hours': serialize_hours(profile.opening_hours),
        'is_temporarily_closed': profile.is_temporarily_closed,
        'is_open_now': profile.is_open_now,
    }


class OperatingHoursView(APIView):
    """List and bulk-replace the vendor's weekly operating hours."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = _get_profile(request)
        if not profile:
            return _no_profile_response()
        return Response(_hours_payload(profile))

    def put(self, request):
        profile = _get_profile(request)
        if not profile:
            return _no_profile_response()
        days = request.data.get('operating_hours', request.data)
        try:
            profile.opening_hours = build_opening_hours(days)
        except HoursError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        profile.save(update_fields=['opening_hours', 'updated_at'])
        sync_open_state(profile)
        return Response(_hours_payload(profile))


class OperatingHoursDayView(APIView):
    """Create/update (PATCH) or clear (DELETE) a single day's hours."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, day):
        profile = _get_profile(request)
        if not profile:
            return _no_profile_response()
        data = request.data
        try:
            profile.opening_hours = set_day(
                profile.opening_hours, day,
                is_closed=bool(data.get('is_closed')),
                open_t=data.get('open'),
                close_t=data.get('close'),
            )
        except HoursError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        profile.save(update_fields=['opening_hours', 'updated_at'])
        sync_open_state(profile)
        return Response(_hours_payload(profile))

    def delete(self, request, day):
        profile = _get_profile(request)
        if not profile:
            return _no_profile_response()
        try:
            profile.opening_hours = set_day(profile.opening_hours, day, is_closed=True)
        except HoursError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        profile.save(update_fields=['opening_hours', 'updated_at'])
        sync_open_state(profile)
        return Response(_hours_payload(profile))


class StoreStatusView(APIView):
    """Read and toggle the store's open/closed state.

    ``is_temporarily_closed`` is the manual override the vendor flips from the
    dashboard app-bar. ``is_open_now`` is the computed truth (override AND the
    configured hours). ``store_active`` is the harder on/off switch for the
    whole storefront.
    """
    permission_classes = [permissions.IsAuthenticated]

    def _payload(self, profile):
        return {
            'is_temporarily_closed': profile.is_temporarily_closed,
            'is_open_now': profile.is_open_now,
            'store_active': profile.store_active,
        }

    def get(self, request):
        profile = _get_profile(request)
        if not profile:
            return _no_profile_response()
        return Response(self._payload(profile))

    def patch(self, request):
        profile = _get_profile(request)
        if not profile:
            return _no_profile_response()

        update_fields = []
        data = request.data

        if 'is_temporarily_closed' in data:
            profile.is_temporarily_closed = _as_bool(data.get('is_temporarily_closed'))
            update_fields.append('is_temporarily_closed')
        # Convenience alias: {"is_open": true} sets is_temporarily_closed=False.
        elif 'is_open' in data:
            profile.is_temporarily_closed = not _as_bool(data.get('is_open'))
            update_fields.append('is_temporarily_closed')

        if 'store_active' in data:
            profile.store_active = _as_bool(data.get('store_active'))
            update_fields.append('store_active')

        if not update_fields:
            return Response(
                {'detail': 'Provide "is_temporarily_closed", "is_open" or "store_active".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_fields.append('updated_at')
        profile.save(update_fields=update_fields)
        sync_open_state(profile)
        return Response(self._payload(profile))

    # POST behaves the same as PATCH so either verb works from the client.
    post = patch


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')
