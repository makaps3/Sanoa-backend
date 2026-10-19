"""Bank account verification + Paystack Transfer Recipient management.

Implements the spec from
``docs/payments/Bank Account Verification and Paystack Recipient Management``.

Flow per vendor / driver:

    1. capture (bank_code, account_number, claimed_name)
    2. resolve via Paystack `/bank/resolve` → real account holder name
    3. fuzzy-compare claimed_name vs resolved_name
         match    → status = VERIFIED
         mismatch → status = MANUAL_REVIEW (admin must approve)
    4. on VERIFIED, create `/transferrecipient` → store RCP_xxx code
    5. set payout_enabled=True

Updating bank details archives the existing recipient and creates a
fresh one so we never silently transfer to a stale account.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from django.db import transaction

from .paystack import paystack_api
from .wallet_models import PaystackRecipient


# Threshold at which we treat names as "matching". 0.85 = roughly 1
# character / 7 different, which catches typos but flags obvious
# mismatches (Jane Smith vs John Doe).
NAME_MATCH_THRESHOLD = 0.85


@dataclass
class VerificationResult:
    recipient: PaystackRecipient
    verified: bool
    similarity: float
    resolved_name: str
    error: Optional[str] = None


def _normalise(name: str) -> str:
    """Lowercase + strip non-alphanum so 'Restaurant ABC (Pty) Ltd' and
    'restaurant abc pty ltd' compare equal."""
    return ''.join(ch for ch in name.lower() if ch.isalnum() or ch.isspace()).strip()


def names_match(claimed: str, resolved: str) -> tuple[bool, float]:
    a = _normalise(claimed or '')
    b = _normalise(resolved or '')
    if not a or not b:
        return False, 0.0
    if a == b or a in b or b in a:
        return True, 1.0
    similarity = SequenceMatcher(None, a, b).ratio()
    return similarity >= NAME_MATCH_THRESHOLD, similarity


# Currencies Paystack supports for Transfer Recipients. Mirrors what the
# frontend dropdown offers; first entry is the default.
SUPPORTED_CURRENCIES = ('ZAR', 'NGN', 'GHS', 'KES', 'USD')

# Currencies for which Paystack's `/bank/resolve` endpoint is available.
# ZAR (South Africa) is intentionally absent — Paystack does not auto-
# verify South African bank accounts via the resolve endpoint, so we
# route ZAR submissions straight to manual admin review.
AUTO_RESOLVABLE_CURRENCIES = ('NGN', 'GHS', 'KES', 'USD')


def verify_and_register(
    *,
    owner_type: str,            # 'vendor' | 'driver'
    owner_id: str,
    business_name: str,         # what the user typed as their name
    bank_code: str,
    bank_name: str,
    account_number: str,
    currency: str = 'ZAR',
) -> VerificationResult:
    """Run the full verification + recipient creation flow.

    Returns a `VerificationResult`. On a hard failure (Paystack
    `resolve` rejected the account) the row is created with
    `verification_status=failed` so the user gets a record they can
    fix; nothing is created on the Paystack side.
    """
    with transaction.atomic():
        # Archive any existing active recipient — bank-detail changes
        # always mean a fresh RCP code, never an in-place edit.
        for previous in PaystackRecipient.objects.filter(
            owner_type=owner_type, owner_id=str(owner_id),
            archived_at__isnull=True,
        ):
            previous.archive(reason='Replaced by new bank details.')

        recipient = PaystackRecipient.objects.create(
            owner_type=owner_type,
            owner_id=str(owner_id),
            business_name=business_name,
            bank_code=bank_code,
            bank_name=bank_name,
            account_number=account_number,
            submitted_account_name=business_name,
        )

    # Paystack only auto-resolves NGN / GHS / KES / USD accounts. ZAR
    # (and anything else we ever add) skips the resolve API and lands
    # in the manual admin review queue — admins approve via
    # `/marketplace/admin/recipients/<id>/approve/`, which uses the
    # submitted business name to create the transfer recipient.
    currency_uc = (currency or 'ZAR').upper()
    if currency_uc not in AUTO_RESOLVABLE_CURRENCIES:
        recipient.verification_status = PaystackRecipient.VERIFICATION_MANUAL_REVIEW
        recipient.bank_verified = False
        recipient.payout_enabled = False
        recipient.notes = (
            f'{currency_uc} accounts cannot be auto-verified by Paystack. '
            'Awaiting admin review before payouts unlock.'
        )
        recipient.paystack_response = {'skipped_resolve': True,
                                       'currency': currency_uc}
        recipient.save()
        return VerificationResult(
            recipient=recipient,
            verified=False,
            similarity=0.0,
            resolved_name='',
            error=recipient.notes,
        )

    # Outside the atomic block — the Paystack call is the slow part.
    resolve = paystack_api.resolve_account_number(
        account_number, bank_code, currency=currency_uc,
    )
    if not resolve.get('status'):
        recipient.verification_status = PaystackRecipient.VERIFICATION_FAILED
        recipient.bank_verified = False
        recipient.payout_enabled = False
        recipient.notes = (resolve.get('message') or 'Paystack rejected the account.')
        recipient.paystack_response = resolve
        recipient.save(update_fields=[
            'verification_status', 'bank_verified', 'payout_enabled',
            'notes', 'paystack_response', 'updated_at',
        ])
        return VerificationResult(
            recipient=recipient,
            verified=False,
            similarity=0.0,
            resolved_name='',
            error=resolve.get('message') or 'Account resolution failed.',
        )

    data = resolve.get('data') or {}
    resolved_name = (data.get('account_name') or '').strip()
    matched, similarity = names_match(business_name, resolved_name)

    recipient.resolved_account_name = resolved_name
    recipient.paystack_response = resolve

    if matched:
        # Names line up — create the transfer recipient and unlock payouts.
        recipient.verification_status = PaystackRecipient.VERIFICATION_VERIFIED
        recipient.bank_verified = True
        rcp_result = paystack_api.create_transfer_recipient(
            name=resolved_name or business_name,
            account_number=account_number,
            bank_code=bank_code,
            currency=currency,
        )
        if rcp_result.get('status') and rcp_result.get('data'):
            rcp_data = rcp_result['data']
            recipient.recipient_code = rcp_data.get('recipient_code', '')
            recipient.paystack_recipient_id = rcp_data.get('id')
            recipient.payout_enabled = True
            recipient.paystack_response = {
                'resolve': resolve, 'recipient': rcp_result,
            }
        else:
            # Resolve worked but recipient creation failed — keep the
            # row but flag it so support can investigate.
            recipient.payout_enabled = False
            recipient.notes = (
                rcp_result.get('message') or 'Transfer recipient creation failed.'
            )
    else:
        recipient.verification_status = PaystackRecipient.VERIFICATION_MANUAL_REVIEW
        recipient.bank_verified = False
        recipient.payout_enabled = False
        recipient.notes = (
            f'Submitted "{business_name}" vs Paystack "{resolved_name}" '
            f'(similarity {similarity:.2f}). Awaiting admin review.'
        )

    recipient.save()
    return VerificationResult(
        recipient=recipient,
        verified=recipient.bank_verified,
        similarity=similarity,
        resolved_name=resolved_name,
        error=None if recipient.bank_verified else recipient.notes,
    )


def approve_manual_review(
    recipient: PaystackRecipient, *, currency: str = 'ZAR',
) -> VerificationResult:
    """Admin override — accept a `manual_review` recipient and create
    the Paystack Transfer Recipient. Used by ops when a vendor's
    trading name and bank-registered name legitimately differ.
    """
    if recipient.verification_status != PaystackRecipient.VERIFICATION_MANUAL_REVIEW:
        raise ValueError('Only manual-review recipients can be approved.')
    rcp_result = paystack_api.create_transfer_recipient(
        name=recipient.resolved_account_name or recipient.business_name,
        account_number=recipient.account_number,
        bank_code=recipient.bank_code,
        currency=currency,
    )
    if rcp_result.get('status') and rcp_result.get('data'):
        data = rcp_result['data']
        recipient.recipient_code = data.get('recipient_code', '')
        recipient.paystack_recipient_id = data.get('id')
        recipient.verification_status = PaystackRecipient.VERIFICATION_VERIFIED
        recipient.bank_verified = True
        recipient.payout_enabled = True
        recipient.paystack_response = {
            **(recipient.paystack_response or {}), 'admin_approved_recipient': rcp_result,
        }
        recipient.save()
        return VerificationResult(
            recipient=recipient,
            verified=True,
            similarity=1.0,
            resolved_name=recipient.resolved_account_name,
            error=None,
        )
    raise RuntimeError(
        rcp_result.get('message') or 'Failed to create transfer recipient on Paystack.'
    )
