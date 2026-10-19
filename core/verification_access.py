"""Current database approval gates operational API access, as in Sanoa Plus."""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny


class VerificationRequired(PermissionDenied):
    default_detail = 'Complete verification and wait for approval before using this feature.'
    default_code = 'verification_required'


def enforce_verification(user, request):
    view = (request.parser_context or {}).get('view')
    action = getattr(view, 'action', None) or request.method.lower()
    if action in getattr(view, 'unverified_actions', ()):
        return
    if request.method in ('GET', 'HEAD', 'OPTIONS') and AllowAny in getattr(view, 'permission_classes', ()):
        return
    if user.is_suspended or not user.is_active:
        raise PermissionDenied('Your account is suspended. Contact support for assistance.')
    if user.is_superuser:
        return
    if user.user_type == 'admin':
        from platform_admin.models import AdminProfile
        if not AdminProfile.objects.filter(user=user, status='active').exists():
            raise PermissionDenied('An active administrator invitation and profile are required.')
    elif user.user_type in ('vendor', 'employee'):
        from business.models import VendorProfile, VendorEmployee
        if user.user_type == 'vendor':
            vendor = VendorProfile.objects.filter(user=user).first()
        else:
            employment = VendorEmployee.objects.select_related('vendor').filter(
                user=user, is_active=True, verification_status='verified').first()
            vendor = employment.vendor if employment else None
        if not user.is_verified or not vendor or not vendor.can_trade:
            raise VerificationRequired()
    elif user.user_type == 'driver':
        from delivery.models import DeliveryDriver
        driver = DeliveryDriver.objects.filter(user=user).first()
        if not user.is_verified or not driver or not driver.is_verified:
            raise VerificationRequired()
