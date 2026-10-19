"""One readiness policy for applicants, reviewers and operational access."""
from django.utils import timezone
from business.models import VendorProfile
from delivery.models import DeliveryDriver

def _vendor_bank_ready(v: VendorProfile) -> bool:
    """Has the vendor SUPPLIED payout bank details?

    Deliberately does not require ``bank_verified``: ZAR accounts can't be
    auto-verified by Paystack, so the bank is confirmed by an admin as part
    of vetting. Requiring verification here would deadlock the vendor —
    they could never complete their own checklist. Providing the details is
    the vendor's job; verifying them is the admin's.
    """
    if getattr(v, 'paystack_subaccount', None) is not None:
        return True
    try:
        from payments.wallet_models import PaystackRecipient
        return PaystackRecipient.objects.filter(
            owner_type='vendor', owner_id=str(v.id),
            archived_at__isnull=True,
        ).exists()
    except Exception:
        return False


def vendor_vetting_checklist(v: VendorProfile, request=None) -> dict:
    """Structured, sectioned vetting checklist for the vendor's profile type.

    Sections: owner (identity of the person), business (registration,
    address & trading docs) and bank (payout subaccount + proof of bank).
    Every REQUIRED item across the three sections must be provided for the
    application to be submittable, and admin-approved to become verified.

    File-backed items carry a ``url`` so the app can preview the uploaded
    document in-app.
    """
    individual = v.profile_type == 'individual'

    def _url(value):
        """Absolute URL for an uploaded file (None for plain text values)."""
        try:
            raw = value.url
        except (AttributeError, ValueError):
            return None
        return request.build_absolute_uri(raw) if request is not None else raw

    def it(code, label, provided, section, required=True, hint=''):
        return {
            'code': code, 'label': label, 'section': section,
            'provided': bool(provided), 'required': required, 'hint': hint,
            'url': _url(provided) if provided else None,
        }

    items = []
    if individual:
        items += [
            it('id_number', 'ID number', v.id_number, 'owner'),
            it('id_document', 'ID document', v.id_document, 'owner'),
            it('selfie_with_id', 'Selfie with ID', v.selfie_with_id, 'owner'),
            it('proof_of_address', 'Proof of address', v.proof_of_address,
               'business'),
            it('cipc_document', 'CIPC document (optional)', v.cipc_document,
               'business', required=False, hint='Optional for individual vendors'),
        ]
    else:
        items += [
            it('owner_full_name', 'Owner full name', v.owner_full_name, 'owner'),
            it('owner_id_number', 'Owner ID number', v.owner_id_number, 'owner'),
            it('owner_id_document', 'Owner ID document', v.owner_id_document,
               'owner'),
            it('cipc_registration_number', 'CIPC registration number',
               v.cipc_registration_number, 'business'),
            it('cipc_document', 'CIPC document', v.cipc_document, 'business'),
            it('owner_proof_of_address', 'Proof of address',
               v.owner_proof_of_address, 'business'),
            it('tax_clearance_certificate', 'Tax clearance certificate',
               v.tax_clearance_certificate, 'business', required=False,
               hint='Recommended — speeds up approval'),
        ]

    items += [
        it('name', 'Trading name', v.name, 'business'),
        it('subaccount', 'Bank account for payouts', _vendor_bank_ready(v),
           'bank', hint='Add your bank in the Bank Account screen'),
        it('proof_of_bank', 'Proof of bank account', v.proof_of_bank, 'bank',
           hint='Bank confirmation letter or stamped statement'),
    ]

    meta = [
        ('owner', 'Owner verification',
         'Confirm the identity of the person behind the store'),
        ('business', 'Business documents',
         'Registration, address and trading details'),
        ('bank', 'Bank account',
         'Where your payouts are sent'),
    ]
    sections = []
    for key, title, subtitle in meta:
        sec = [i for i in items if i['section'] == key]
        req = [i for i in sec if i['required']]
        sections.append({
            'key': key, 'title': title, 'subtitle': subtitle, 'items': sec,
            'complete': all(i['provided'] for i in req) if req else True,
            'provided_count': sum(1 for i in req if i['provided']),
            'required_count': len(req),
        })
    missing = [{'label': i['label'], 'code': i['code']}
               for i in items if i['required'] and not i['provided']]
    return {'sections': sections, 'missing': missing,
            'complete': len(missing) == 0}


def _vendor_missing_documents(v: VendorProfile) -> list:
    """Flat list of missing required items — drives the "missing documents"
    panel + the self-submit blocker. Derived from the sectioned checklist."""
    return vendor_vetting_checklist(v)['missing']


def _driver_missing_documents(d: DeliveryDriver) -> list:
    missing = []

    def need(value, label, code):
        if not value:
            missing.append({'label': label, 'code': code})

    need(d.national_id_document, 'National ID document',
         'national_id_document')
    need(d.driver_license_document, "Driver's licence",
         'driver_license_document')
    need(d.license_number, 'Licence number', 'license_number')
    need(d.license_expiry_date and d.license_expiry_date >= timezone.localdate(), 'Valid licence expiry date',
         'license_expiry_date')
    need(d.vehicle_registration, 'Vehicle registration',
         'vehicle_registration')
    need(d.insurance_document, 'Insurance document',
         'insurance_document')
    need(d.vehicle_photo_front, 'Vehicle photo (front)',
         'vehicle_photo_front')
    need(d.terms_accepted, 'Terms accepted', 'terms_accepted')
    if d.vehicle_license_expiry and d.vehicle_license_expiry < timezone.localdate():
        missing.append({'label': 'Current vehicle licence', 'code': 'vehicle_license_expiry'})
    return missing


