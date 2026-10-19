"""Verification transitions shared by the current and legacy APIs."""
from django.utils import timezone

VENDOR_EVIDENCE_FIELDS = {
    'profile_type', 'name', 'trading_name', 'id_number', 'id_document',
    'selfie_with_id', 'proof_of_address', 'cipc_registration_number',
    'cipc_document', 'owner_full_name', 'owner_id_number', 'owner_id_document',
    'owner_proof_of_address', 'proof_of_bank', 'bank_name', 'bank_account_number',
    'bank_branch_code', 'bank_account_holder', 'tax_clearance_certificate',
    'street_address', 'city', 'province', 'postal_code',
}


def evidence_changed(instance, values):
    return any(key in VENDOR_EVIDENCE_FIELDS and value != getattr(instance, key, None)
               for key, value in values.items())


def invalidate_vendor(vendor):
    """Replacing evidence cannot retain a previous approval or lift suspension."""
    if vendor.verification_status != 'suspended':
        vendor.verification_status = 'pending'
    vendor.store_active = False
    vendor.owner_vetting_passed = False
    vendor.business_vetting_passed = False
    vendor.verified_at = None
    vendor.verified_by = None


def record_decision(subject, actor, action, previous, current, reason=''):
    from audit.models import AuditLog
    AuditLog.objects.create(
        user=actor, user_email=actor.email, category='admin',
        action=action if action in ('approve', 'reject') else 'status_change',
        target_model=subject._meta.label, target_id=str(subject.pk),
        description=f'Verification {action}: {previous} → {current}',
        changes={'verification_status': {'old': previous, 'new': current}},
        extra_data={'reason': reason, 'decision': action},
    )


def sync_review_state(vendor):
    """The unified profile is the authority; legacy records are projections."""
    from .models import IndividualVendorProfile, BusinessVendorProfile, VettingApplication, VendorEmployee
    common = dict(verification_status=vendor.verification_status,
                  rejection_reason=vendor.rejection_reason,
                  verified_at=vendor.verified_at, verified_by=vendor.verified_by,
                  store_active=vendor.store_active)
    IndividualVendorProfile.objects.filter(user=vendor.user).update(**common)
    BusinessVendorProfile.objects.filter(user=vendor.user).update(
        **common, owner_vetting_passed=vendor.owner_vetting_passed,
        business_vetting_passed=vendor.business_vetting_passed)
    VendorEmployee.objects.filter(user=vendor.user, vendor=vendor, is_manager=True).update(
        verification_status=vendor.verification_status,
        verified_at=vendor.verified_at, verified_by=vendor.verified_by,
        is_active=vendor.verification_status != 'suspended')
    from django.db.models import Q
    apps = VettingApplication.objects.filter(
        Q(individual_vendor__user=vendor.user) | Q(business_vendor__user=vendor.user))
    state = {'verified': 'passed', 'under_review': 'under_review',
             'rejected': 'failed', 'suspended': 'failed'}.get(vendor.verification_status, 'pending')
    approved = state == 'passed'
    apps.update(status=state, id_verified=approved, address_verified=approved,
                selfie_verified=approved and vendor.profile_type == 'individual',
                cipc_verified=approved and vendor.profile_type == 'business',
                # Payout verification is independent of identity review.
                tax_verified=False, bank_verified=False,
                reviewed_at=vendor.verified_at, completed_at=vendor.verified_at,
                rejection_reason=vendor.rejection_reason)
