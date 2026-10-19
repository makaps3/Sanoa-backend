"""Endpoints for vendor-employee management.

Flow:
  Manager fills the "Add employee" form on the vendor app. We
  create a `User` (user_type='vendor') with a randomly-generated
  temporary password, attach a `VendorEmployee` record, and return
  the temp password back to the manager ONCE so they can share it
  out-of-band with the new hire. The new hire signs in with that
  password; their `must_change_password=True` flag forces a
  password reset before they can do anything else.

Audiences:

  • **Vendor manager** (the CEO/founder, auto-tagged
    `is_manager=True` by ``business.signals``) manages their team:
    list, add, vet (verify / reject / suspend), remove, reset
    password.
    Manager can only vet other employees once they themselves are
    `verified` by a platform admin.

  • **Platform admin** (`manage_vendors` permission) cross-vendor
    list + override actions for stuck cases.

  • **Employee themselves** uses the standard login + a dedicated
    "change password on first use" endpoint exposed here.
"""
from __future__ import annotations

import secrets
import string

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import VendorProfile, VendorEmployee

User = get_user_model()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _admin_profile(request):
    return getattr(request.user, 'admin_profile', None)


def _can_manage_vendors(request) -> bool:
    profile = _admin_profile(request)
    if profile is None:
        return False
    if profile.is_super_admin:
        return True
    return bool(profile.has_permission('manage_vendors'))


def _vendor_for(request):
    """Return the VendorProfile the caller acts on, whether they are
    the profile owner OR an employee on that profile."""
    user = request.user
    profile = getattr(user, 'vendor_profile', None)
    if profile is not None:
        return profile
    emp = getattr(user, 'vendor_employment', None)
    if emp is not None:
        return emp.vendor
    return None


def _manager_employee(user):
    """Return this user's manager VendorEmployee row, or None."""
    emp = getattr(user, 'vendor_employment', None)
    if emp is None or not emp.is_manager:
        return None
    return emp


def _can_manage_employees(user) -> bool:
    """True if the caller can add / remove / verify employees:
    the vendor profile owner OR a VendorEmployee with is_manager=True.
    """
    if getattr(user, 'vendor_profile', None) is not None:
        return True
    return _manager_employee(user) is not None


def _generate_temp_password(length: int = 12) -> str:
    """Generate a human-typable temporary password.

    Avoids look-alike chars (0/O, 1/l/I) so the manager can read it
    aloud / type it into a chat without mistakes.
    """
    alphabet = (
        string.ascii_uppercase.replace('O', '').replace('I', '')
        + string.ascii_lowercase.replace('l', '').replace('o', '')
        + string.digits.replace('0', '').replace('1', '')
        + '!@#$%&*'
    )
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _coerce_permissions(raw, *, is_manager: bool) -> dict:
    """Filter the manager's submitted permissions dict down to the
    canonical keys, coerce values to bool, and short-circuit to "all
    True" for the manager seat.
    """
    if is_manager:
        return VendorEmployee.default_permissions_for(is_manager=True)
    seed = VendorEmployee.default_permissions_for(is_manager=False)
    if isinstance(raw, dict):
        valid_keys = {k for k, _ in VendorEmployee.PERMISSION_KEYS}
        for k, v in raw.items():
            if k in valid_keys:
                seed[k] = bool(v)
    return seed


def _serialise_permissions(emp: VendorEmployee):
    perms = emp.permissions or {}
    return [
        {
            'key': key,
            'label': label,
            'granted': bool(perms.get(key, False)) or emp.is_manager,
        }
        for key, label in VendorEmployee.PERMISSION_KEYS
    ]


def _serialise_employee(emp: VendorEmployee, *, detailed: bool = False):
    user = emp.user
    out = {
        'id': str(emp.id),
        'vendor_id': str(emp.vendor_id),
        'is_manager': emp.is_manager,
        'role_title': emp.role_title,
        'department': emp.department,
        'department_label': emp.get_department_display(),
        'verification_status': emp.verification_status,
        'verification_status_label': emp.get_verification_status_display(),
        'rejection_reason': emp.rejection_reason,
        'verified_at': emp.verified_at.isoformat() if emp.verified_at else None,
        'is_active': emp.is_active,
        'permissions': _serialise_permissions(emp),
        'created_at': emp.created_at.isoformat(),
        'user': {
            'id': user.id,
            'email': user.email,
            'full_name': (f'{user.first_name} {user.last_name}').strip()
                or user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'is_verified': user.is_verified,
            'is_suspended': user.is_suspended,
            'must_change_password': user.must_change_password,
            'last_login_at': (
                user.last_login.isoformat() if user.last_login else None
            ),
        },
    }
    if detailed and emp.verified_by_id:
        out['verified_by_email'] = emp.verified_by.email
    return out


# ═════════════════════════════════════════════════════════════════════════════
# MANAGER-FACING — the vendor managing their own team
# ═════════════════════════════════════════════════════════════════════════════

class VendorEmployeePermissionCatalogView(APIView):
    """Static catalogue of permission keys + their friendly labels.

    The vendor app reads this once and renders the toggle list,
    so backend stays the single source of truth — adding a key in
    `VendorEmployee.PERMISSION_KEYS` automatically surfaces in the
    UI without any frontend change.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            'permissions': [
                {'key': k, 'label': label}
                for k, label in VendorEmployee.PERMISSION_KEYS
            ],
            'departments': [
                {'code': c, 'label': label}
                for c, label in VendorEmployee.DEPARTMENT_CHOICES
            ],
            'defaults': {
                'manager':
                    VendorEmployee.default_permissions_for(is_manager=True),
                'employee':
                    VendorEmployee.default_permissions_for(is_manager=False),
            },
        })


class MyVendorEmployeesView(APIView):
    """List employees + add a new one (manager only).

    GET → employees, headcount cap, and whether the manager is
          verified yet.
    POST → mint a User + VendorEmployee in one shot. Body:
        ``{ "email", "first_name", "last_name", "phone_number",
            "role_title", "department" }``
    Response includes ``temporary_password`` — shown ONCE to the
    manager so they can pass it on to the new hire.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        vendor = _vendor_for(request)
        if vendor is None:
            return Response({'error': 'No vendor profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        employees = vendor.employees.select_related('user').all()
        return Response({
            'vendor': {
                'id': str(vendor.id),
                'name': vendor.name,
                'profile_type': vendor.profile_type,
                'employee_cap': vendor.employee_cap,
                'employee_count': employees.count(),
                'manager_is_verified': any(
                    e.is_manager and e.is_verified for e in employees
                ),
            },
            'employees': [
                _serialise_employee(e, detailed=True) for e in employees
            ],
        })

    @transaction.atomic
    def post(self, request):
        vendor = _vendor_for(request)
        if vendor is None:
            return Response({'error': 'No vendor profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        if not _can_manage_employees(request.user):
            return Response(
                {'error': 'Only the vendor owner or a manager can add '
                          'employees.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        email = (request.data.get('email') or '').strip().lower()
        first_name = (request.data.get('first_name') or '').strip()
        last_name = (request.data.get('last_name') or '').strip()
        phone_number = (request.data.get('phone_number') or '').strip()
        role_title = (request.data.get('role_title') or '').strip()
        department = (request.data.get('department') or 'operations').strip()

        if not email:
            return Response({'error': "'email' is required."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not first_name or not last_name:
            return Response(
                {'error': "Both 'first_name' and 'last_name' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not role_title:
            return Response({'error': "'role_title' is required."},
                            status=status.HTTP_400_BAD_REQUEST)
        if department not in dict(VendorEmployee.DEPARTMENT_CHOICES):
            return Response({'error': "Unknown 'department'."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Cap check — the existing employees + this new one mustn't
        # exceed the per-profile-type cap.
        if vendor.employees.count() >= vendor.employee_cap:
            return Response(
                {
                    'error': f'Headcount cap reached '
                             f'({vendor.employee_cap}). Remove an '
                             'existing employee first.',
                    'cap': vendor.employee_cap,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Refuse duplicates — both an existing user with the same
        # email AND an existing employee with that email on this
        # vendor would conflict.
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {'error': 'A user with that email already exists.'},
                status=status.HTTP_409_CONFLICT,
            )

        temp_password = _generate_temp_password()
        username = email.split('@')[0][:30]
        # Ensure username is unique by appending random suffix when
        # taken — `username` is required by AbstractUser even though
        # we authenticate by email.
        base = username
        n = 1
        while User.objects.filter(username=username).exists():
            n += 1
            suffix = secrets.token_hex(3)
            username = f'{base}-{suffix}'[:30]
            if n > 5:
                username = secrets.token_hex(8)
                break

        try:
            new_user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name[:30],
                last_name=last_name[:150],
                password=temp_password,
                user_type='employee',
            )
        except IntegrityError as exc:
            return Response({'error': f'Could not create user: {exc}'},
                            status=status.HTTP_409_CONFLICT)

        if phone_number:
            new_user.phone_number = phone_number[:17]
        new_user.must_change_password = True
        new_user.save(update_fields=[
            'phone_number', 'must_change_password', 'updated_at',
        ])

        emp = VendorEmployee.objects.create(
            vendor=vendor,
            user=new_user,
            role_title=role_title[:100],
            department=department,
            is_manager=False,
            verification_status='under_review',
            permissions=_coerce_permissions(
                request.data.get('permissions'), is_manager=False,
            ),
        )

        payload = _serialise_employee(emp, detailed=True)
        # The temporary password is returned ONCE here — the
        # frontend MUST surface it immediately so the manager can
        # share it; we don't store the plain-text anywhere.
        payload['temporary_password'] = temp_password
        return Response(payload, status=status.HTTP_201_CREATED)


class MyVendorEmployeeDetailView(APIView):
    """GET / DELETE / PATCH a single employee on the caller's vendor."""
    permission_classes = [permissions.IsAuthenticated]

    def _resolve(self, request, employee_id):
        vendor = _vendor_for(request)
        if vendor is None:
            return None, None, Response(
                {'error': 'No vendor profile on this account.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            emp = vendor.employees.select_related('user').get(id=employee_id)
        except VendorEmployee.DoesNotExist:
            return None, None, Response(
                {'error': 'Employee not found on this vendor profile.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return vendor, emp, None

    def get(self, request, employee_id):
        _, emp, err = self._resolve(request, employee_id)
        if err is not None:
            return err
        return Response(_serialise_employee(emp, detailed=True))

    def patch(self, request, employee_id):
        vendor, emp, err = self._resolve(request, employee_id)
        if err is not None:
            return err
        if not _can_manage_employees(request.user):
            return Response(
                {'error': 'Only the vendor owner or a manager can edit '
                          'employees.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        dirty = []
        if 'role_title' in request.data:
            value = (request.data.get('role_title') or '').strip()
            if not value:
                return Response({'error': "'role_title' cannot be empty."},
                                status=status.HTTP_400_BAD_REQUEST)
            emp.role_title = value[:100]
            dirty.append('role_title')
        if 'department' in request.data:
            value = (request.data.get('department') or '').strip()
            if value not in dict(VendorEmployee.DEPARTMENT_CHOICES):
                return Response({'error': "Unknown 'department'."},
                                status=status.HTTP_400_BAD_REQUEST)
            emp.department = value
            dirty.append('department')
        if 'permissions' in request.data:
            # The manager seat is always all-true; refuse the
            # downgrade. For other employees, replace the dict
            # wholesale with the coerced submission.
            if emp.is_manager:
                return Response(
                    {'error': "The manager's permissions cannot be "
                              'narrowed.'},
                    status=status.HTTP_409_CONFLICT,
                )
            emp.permissions = _coerce_permissions(
                request.data.get('permissions'), is_manager=False,
            )
            dirty.append('permissions')
        if not dirty:
            return Response({'error': 'Nothing to update.'},
                            status=status.HTTP_400_BAD_REQUEST)
        dirty.append('updated_at')
        emp.save(update_fields=dirty)
        return Response(_serialise_employee(emp, detailed=True))

    def delete(self, request, employee_id):
        vendor, emp, err = self._resolve(request, employee_id)
        if err is not None:
            return err
        if emp.is_manager:
            return Response(
                {'error': 'The vendor manager cannot be removed. '
                          'Transfer ownership first.'},
                status=status.HTTP_409_CONFLICT,
            )
        if not _can_manage_employees(request.user):
            return Response(
                {'error': 'Only the vendor owner or a manager can remove '
                          'employees.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        emp.user.delete()  # cascades the employee row
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyVendorEmployeeActionView(APIView):
    """Manager-side vetting actions on an employee.

    Body:
      ``{ "action": "approve" | "reject" | "review" | "request_info"
                    | "suspend" | "unsuspend",
          "reason": "<text>" }``
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, employee_id):
        vendor = _vendor_for(request)
        if vendor is None:
            return Response({'error': 'No vendor profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        manager = _manager_employee(request.user)
        if manager is None:
            return Response(
                {'error': 'Only the vendor manager can vet employees.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not manager.is_verified:
            return Response(
                {'error': 'You need to be verified by platform admin '
                          'before you can vet employees.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            emp = vendor.employees.select_related('user').get(id=employee_id)
        except VendorEmployee.DoesNotExist:
            return Response({'error': 'Employee not found on this vendor profile.'},
                            status=status.HTTP_404_NOT_FOUND)
        if emp.is_manager:
            return Response(
                {'error': "The manager's verification is handled by "
                          'platform admin, not from this endpoint.'},
                status=status.HTTP_409_CONFLICT,
            )
        return _apply_employee_action(emp, request, actor=request.user)


class MyVendorEmployeeResetPasswordView(APIView):
    """Manager regenerates an employee's temporary password.

    Used when an employee forgets the original temp password or
    never reset theirs. Mints a fresh random password, flips
    `must_change_password=True`, and returns it once. The old
    password is invalidated immediately.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, employee_id):
        vendor = _vendor_for(request)
        if vendor is None:
            return Response({'error': 'No vendor profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        if not _can_manage_employees(request.user):
            return Response(
                {'error': 'Only the vendor owner or a manager can reset '
                          'employee passwords.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            emp = vendor.employees.select_related('user').get(id=employee_id)
        except VendorEmployee.DoesNotExist:
            return Response({'error': 'Employee not found on this vendor profile.'},
                            status=status.HTTP_404_NOT_FOUND)
        if emp.is_manager:
            return Response(
                {'error': 'Managers reset their own passwords via the '
                          'standard "forgot password" flow.'},
                status=status.HTTP_409_CONFLICT,
            )

        temp_password = _generate_temp_password()
        emp.user.set_password(temp_password)
        emp.user.must_change_password = True
        emp.user.save(update_fields=[
            'password', 'must_change_password', 'updated_at',
        ])
        payload = _serialise_employee(emp, detailed=True)
        payload['temporary_password'] = temp_password
        return Response(payload)


def _apply_employee_action(emp: VendorEmployee, request, *, actor):
    """Shared verify/reject/suspend logic for manager + admin."""
    action = (request.data.get('action') or '').lower()
    reason = (request.data.get('reason') or '').strip()
    if action == 'approve':
        emp.verification_status = 'verified'
        emp.rejection_reason = ''
        emp.verified_at = timezone.now()
        emp.verified_by = actor
        emp.is_active = True
    elif action == 'review':
        emp.verification_status = 'under_review'
    elif action == 'request_info':
        if not reason:
            return Response(
                {'error': "'reason' is required when requesting info."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        emp.verification_status = 'pending'
        emp.rejection_reason = reason[:2000]
    elif action == 'reject':
        if not reason:
            return Response({'error': "'reason' is required to reject."},
                            status=status.HTTP_400_BAD_REQUEST)
        emp.verification_status = 'rejected'
        emp.rejection_reason = reason[:2000]
        emp.is_active = False
    elif action == 'suspend':
        if not reason:
            return Response({'error': "'reason' is required to suspend."},
                            status=status.HTTP_400_BAD_REQUEST)
        emp.verification_status = 'suspended'
        emp.rejection_reason = reason[:2000]
        emp.is_active = False
    elif action == 'unsuspend':
        emp.verification_status = 'pending'
        emp.is_active = True
        emp.rejection_reason = ''
    else:
        return Response(
            {'error': "'action' must be approve / review / request_info / "
                      'reject / suspend / unsuspend.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    emp.save()
    return Response(_serialise_employee(emp, detailed=True))


# ═════════════════════════════════════════════════════════════════════════════
# EMPLOYEE-FACING — change password on first login
# ═════════════════════════════════════════════════════════════════════════════

class ChangeTemporaryPasswordView(APIView):
    unverified_actions = ('post',)
    """Employee replaces the temporary password chosen by their manager.

    Body:
      ``{ "current_password": "<temp pw>", "new_password": "<chosen pw>" }``
    Verifies the current password, sets the new one, and clears
    `must_change_password`. Returns the new auth state.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        current = request.data.get('current_password') or ''
        new = request.data.get('new_password') or ''
        if not user.check_password(current):
            return Response({'error': 'Current password is incorrect.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if len(new) < 8:
            return Response(
                {'error': 'Choose a password with at least 8 characters.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new == current:
            return Response(
                {'error': 'New password must differ from the temporary one.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new)
        user.must_change_password = False
        user.save(update_fields=[
            'password', 'must_change_password', 'updated_at',
        ])
        return Response({
            'email': user.email,
            'must_change_password': user.must_change_password,
        })


# ═════════════════════════════════════════════════════════════════════════════
# PLATFORM-ADMIN-FACING
# ═════════════════════════════════════════════════════════════════════════════

class AdminEmployeeListView(APIView):
    """List employees across vendors."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not _can_manage_vendors(request):
            return Response({'error': 'Forbidden.'},
                            status=status.HTTP_403_FORBIDDEN)
        from django.db.models import Q

        qs = (
            VendorEmployee.objects
            .select_related('user', 'vendor')
            .all()
        )
        target = (request.query_params.get('status') or 'all').lower()
        if target != 'all':
            qs = qs.filter(verification_status=target)
        vendor_id = request.query_params.get('vendor_id')
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(role_title__icontains=search)
                | Q(vendor__name__icontains=search)
                | Q(vendor__trading_name__icontains=search),
            )
        qs = qs.order_by('-is_manager', '-created_at')[:300]
        return Response({
            'results': [
                {
                    **_serialise_employee(e, detailed=True),
                    'vendor': {
                        'id': str(e.vendor_id),
                        'name': e.vendor.name,
                        'trading_name': e.vendor.trading_name,
                        'profile_type': e.vendor.profile_type,
                    },
                }
                for e in qs
            ],
        })


class AdminEmployeeDetailView(APIView):
    """GET / DELETE a single employee from the admin side."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id):
        if not _can_manage_vendors(request):
            return Response({'error': 'Forbidden.'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            emp = VendorEmployee.objects.select_related(
                'user', 'vendor',
            ).get(id=employee_id)
        except VendorEmployee.DoesNotExist:
            return Response({'error': 'Employee not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response({
            **_serialise_employee(emp, detailed=True),
            'vendor': {
                'id': str(emp.vendor_id),
                'name': emp.vendor.name,
                'trading_name': emp.vendor.trading_name,
                'profile_type': emp.vendor.profile_type,
            },
        })

    def delete(self, request, employee_id):
        if not _can_manage_vendors(request):
            return Response({'error': 'Forbidden.'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            emp = VendorEmployee.objects.select_related('user').get(
                id=employee_id,
            )
        except VendorEmployee.DoesNotExist:
            return Response({'error': 'Employee not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        if emp.is_manager:
            return Response(
                {'error': 'Cannot delete the vendor manager directly. '
                          'Delete the vendor profile instead.'},
                status=status.HTTP_409_CONFLICT,
            )
        emp.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminEmployeeActionView(APIView):
    """Platform-admin override of any employee's vetting status."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, employee_id):
        if not _can_manage_vendors(request):
            return Response({'error': 'Forbidden.'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            emp = VendorEmployee.objects.select_related('user').get(
                id=employee_id,
            )
        except VendorEmployee.DoesNotExist:
            return Response({'error': 'Employee not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        return _apply_employee_action(emp, request, actor=request.user)
