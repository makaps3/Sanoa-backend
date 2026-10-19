"""
Custom permission classes for the API
"""
from rest_framework import permissions


class IsVendor(permissions.BasePermission):
    """Permission for vendor owners AND their employees."""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ('vendor', 'employee')
        )


class IsVerifiedVendor(permissions.BasePermission):
    """Vendor owner with a verified profile, OR an employee whose
    employer's vendor profile is verified."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated
                and user.user_type in ('vendor', 'employee')):
            return False
        from business.models import VendorProfile, VendorEmployee
        if user.user_type == 'vendor':
            profile = VendorProfile.objects.filter(user=user).first()
        else:
            employee = VendorEmployee.objects.select_related('vendor').filter(
                user=user, is_active=True, verification_status='verified').first()
            profile = employee.vendor if employee else None
        return bool(profile and profile.can_trade)



class IsCustomer(permissions.BasePermission):
    """Permission to check if user is a customer"""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.user_type == 'customer'
        )


class IsAdminUser(permissions.BasePermission):
    """Permission to check if user is admin"""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.is_staff or request.user.is_superuser)
        )


class IsVendorOrAdmin(permissions.BasePermission):
    """Permission for vendor owners, their employees, or platform admin."""

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.user_type in ('vendor', 'employee')
             or request.user.is_staff)
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    """Permission to check if user is owner of object or admin"""

    def has_object_permission(self, request, view, obj):
        if request.user and (
            request.user.is_staff
            or request.user.is_superuser
            or hasattr(request.user, 'admin_profile')
        ):
            return True
        return obj.user == request.user


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Permission to check if user is owner or only allow read"""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


class IsVendorOrReadOnly(permissions.BasePermission):
    """Permission to check if user is vendor owner or only allow read"""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.vendor == request.user


class IsPlatformAdmin(permissions.BasePermission):
    """Allow access only to users who have an AdminProfile (platform_admin app)."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        profile = getattr(request.user, 'admin_profile', None)
        return bool(profile and profile.status == 'active')
