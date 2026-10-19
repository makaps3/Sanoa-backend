"""
Branded transactional email for Sanoa.

Every email shares one look (`templates/emails/base_email.html`) with the
Sanoa logo embedded inline (CID attachment, so it renders without the client
fetching a remote image) and the brand palette (#219ebc / #023047).

Public helpers:
    send_otp_email(user, code, purpose=..., expires_minutes=...)
    send_welcome_email(user)                # vendors get a QR of their store
    send_password_reset_email(user, code, expires_minutes=...)
    send_vendor_invoice_email(order, vendor)  # items + commission only
"""
from __future__ import annotations

import io
import logging
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

log = logging.getLogger('sanoa.email')

_LOGO_CID = 'sanoa_logo'
_QR_CID = 'sanoa_qr'


def _logo_path():
    return settings.BASE_DIR / 'static' / 'email' / 'sanoa-logo.png'


def _base_context(extra: dict | None = None) -> dict:
    ctx = {
        'brand': getattr(settings, 'SANOA_BRAND', {}),
        'site_url': getattr(settings, 'SANOA_SITE_URL', 'https://sanoa.co.za'),
        'from_name': getattr(settings, 'EMAIL_FROM_NAME', 'Sanoa'),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _attach_inline_image(message: EmailMultiAlternatives, data: bytes, cid: str):
    img = MIMEImage(data)
    img.add_header('Content-ID', f'<{cid}>')
    img.add_header('Content-Disposition', 'inline', filename=f'{cid}.png')
    message.attach(img)


def generate_qr_png(data: str, box_size: int = 8, border: int = 2) -> bytes | None:
    """Return PNG bytes for a QR code encoding `data`, or None on failure."""
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M

        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color='#023047', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    except Exception:
        log.exception('QR generation failed')
        return None


def send_branded_email(
    *,
    subject: str,
    to,
    template: str,
    context: dict | None = None,
    qr_bytes: bytes | None = None,
    attachments: list | None = None,
    reply_to=None,
) -> bool:
    """Render `template` (extends base_email.html) and send it with the logo
    (and optional QR) inlined. `attachments` is a list of
    (filename, content_bytes, mimetype) tuples — e.g. a PDF invoice.
    Returns True on success; never raises so a failed email can't break the
    calling request.
    """
    recipients = [to] if isinstance(to, str) else list(to)
    if not recipients:
        return False

    # Testing: redirect every email to the allow-listed address so it
    # actually arrives (Resend test mode only delivers to the account email).
    redirect = getattr(settings, 'EMAIL_REDIRECT_ALL', '') or ''
    if redirect:
        recipients = [redirect]

    try:
        html = render_to_string(template, _base_context(context))
        text = strip_tags(html)

        message = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            reply_to=reply_to,
        )
        message.attach_alternative(html, 'text/html')
        message.mixed_subtype = 'related'  # allow inline (cid) images

        # Inline logo
        try:
            with open(_logo_path(), 'rb') as fh:
                _attach_inline_image(message, fh.read(), _LOGO_CID)
        except OSError:
            log.warning('Sanoa email logo not found at %s', _logo_path())

        # Optional inline QR
        if qr_bytes:
            _attach_inline_image(message, qr_bytes, _QR_CID)

        # File attachments (e.g. the PDF invoice — the "download").
        for filename, content, mimetype in (attachments or []):
            message.attach(filename, content, mimetype)
    except Exception:
        log.exception('Failed to build email "%s" to %s', subject, recipients)
        return False

    def _deliver():
        try:
            return message.send(fail_silently=False) > 0
        except (TimeoutError, OSError) as exc:
            # Can't reach the SMTP host — almost always the network/firewall
            # blocking the outbound port rather than a code fault, so log one
            # actionable line instead of a full stack trace on every send.
            log.error(
                'Could not reach the mail server (%s:%s) — %s. The email "%s" '
                'was not delivered. Check outbound access to that port, or set '
                'EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend '
                'in .env to print emails locally instead.',
                getattr(settings, 'EMAIL_HOST', '?'),
                getattr(settings, 'EMAIL_PORT', '?'),
                exc.__class__.__name__, subject,
            )
        except Exception:
            log.exception('Failed to send email "%s" to %s', subject, recipients)

        return False

    # Authentication mail must report delivery failure instead of losing a daemon
    # thread when a worker restarts. Use a durable queue before making this async.
    return _deliver()


# ─────────────────────────────────────────────────────────────────────
# Specific emails
# ─────────────────────────────────────────────────────────────────────

def _display_name(user) -> str:
    full = f'{user.first_name} {user.last_name}'.strip()
    return full or (user.email.split('@')[0] if user.email else 'there')


def send_otp_email(user, code: str, *, purpose: str = 'verification',
                   expires_minutes: int = 10) -> bool:
    heading = {
        'verification': 'Verify your email',
        'login': 'Your login code',
        'password_reset': 'Reset your password',
    }.get(purpose, 'Your verification code')
    return send_branded_email(
        subject=f'Sanoa · {code} is your verification code',
        to=user.email,
        template='emails/otp.html',
        context={
            'name': _display_name(user),
            'code': code,
            'heading': heading,
            'purpose': purpose,
            'expires_minutes': expires_minutes,
        },
    )


def _vendor_profile(user):
    return getattr(user, 'vendor_profile', None)


def send_welcome_email(user) -> bool:
    """Welcome the new user. Vendors also receive a QR code encoding their
    store details, ready to print or share."""
    vp = _vendor_profile(user)
    is_vendor = user.user_type in ('vendor', 'employee') and vp is not None

    qr_bytes = None
    store_name = None
    if is_vendor:
        store_name = vp.trading_name or vp.name or 'Your store'
        site = getattr(settings, 'SANOA_SITE_URL', 'https://sanoa.co.za')
        # Encoded payload — readable details + a deep link to the store.
        payload = (
            f'Sanoa Vendor\n'
            f'Store: {store_name}\n'
            f'ID: {vp.id}\n'
            f'{site}/vendor/{vp.id}'
        )
        qr_bytes = generate_qr_png(payload)

    return send_branded_email(
        subject='Welcome to Sanoa 🎉',
        to=user.email,
        template='emails/welcome.html',
        context={
            'name': _display_name(user),
            'user_type': user.user_type,
            'is_vendor': is_vendor,
            'store_name': store_name,
            'has_qr': qr_bytes is not None,
        },
        qr_bytes=qr_bytes,
    )


def send_password_reset_email(user, code: str, *, expires_minutes: int = 10) -> bool:
    return send_branded_email(
        subject='Sanoa · Reset your password',
        to=user.email,
        template='emails/password_reset.html',
        context={
            'name': _display_name(user),
            'code': code,
            'expires_minutes': expires_minutes,
        },
    )


def send_vendor_invoice_email(order, vendor) -> bool:
    """Email a vendor their invoice for one order. Shows the vendor's items
    and the platform commission ONLY — delivery and service fees are the
    customer/platform's concern and never appear on the vendor invoice.
    """
    from decimal import Decimal

    user = getattr(vendor, 'user', None)
    if user is None or not getattr(user, 'email', ''):
        return False

    items = list(
        order.items.filter(vendor=vendor).values(
            'product_name', 'variant_name', 'quantity',
            'unit_price', 'total_price',
        )
    )
    if not items:
        return False

    items_amount = sum((Decimal(str(i['total_price'])) for i in items), Decimal('0'))

    # A vendor's own promotion/coupon is funded by the vendor, so it reduces
    # the goods value the commission is charged on. Carts are one-per-vendor,
    # so the order's vendor_funded_discount belongs entirely to this vendor.
    vendor_discount = Decimal(str(getattr(order, 'vendor_funded_discount', 0) or 0))
    vendor_discount = min(vendor_discount, items_amount)
    net_sales = (items_amount - vendor_discount).quantize(Decimal('0.01'))

    # Commission is charged on the discounted (net) goods value.
    pct = Decimal(str(getattr(order, 'commission_percent', 0) or 0))
    if pct > 0:
        commission = (net_sales * pct / Decimal('100')).quantize(Decimal('0.01'))
    else:
        commission = Decimal(str(getattr(order, 'commission_amount', 0) or 0))
    payout = (net_sales - commission).quantize(Decimal('0.01'))

    coupon_code = (getattr(order, 'coupon_code', '') or '').strip()
    fulfillment = (getattr(order, 'fulfillment_type', '') or '').replace('_', ' ').title()

    store_name = vendor.trading_name or vendor.name or 'Your store'

    # Attach a professional PDF invoice — the downloadable copy.
    attachments = None
    try:
        from core.invoice_pdf import build_vendor_invoice_pdf
        pdf_bytes = build_vendor_invoice_pdf(order, vendor)
        attachments = [(
            f'Sanoa-Invoice-{order.order_number}.pdf',
            pdf_bytes,
            'application/pdf',
        )]
    except Exception:
        log.exception('Invoice PDF generation failed for order %s', order.pk)

    return send_branded_email(
        subject=f'Sanoa · Invoice for order #{order.order_number}',
        to=user.email,
        template='emails/invoice.html',
        context={
            'name': _display_name(user),
            'store_name': store_name,
            'order': order,
            'order_number': order.order_number,
            'invoice_no': f'INV-{order.order_number}',
            'created_at': order.created_at,
            'status': (getattr(order, 'status', '') or '').replace('_', ' ').title(),
            'customer_email': getattr(getattr(order, 'user', None), 'email', ''),
            'fulfillment': fulfillment,
            'items': items,
            'items_amount': items_amount,
            'vendor_discount': vendor_discount,
            'has_discount': vendor_discount > 0,
            'coupon_code': coupon_code,
            'net_sales': net_sales,
            'commission': commission,
            'commission_percent': pct,
            'payout': payout,
            'has_pdf': attachments is not None,
        },
        attachments=attachments,
    )


def send_subscription_invoice_email(subscription, txn=None) -> bool:
    """Email a vendor a receipt/invoice for their tier subscription payment."""
    from decimal import Decimal

    vendor = getattr(subscription, 'vendor', None)
    user = getattr(vendor, 'user', None)
    if user is None or not getattr(user, 'email', ''):
        return False

    tier = subscription.tier
    amount = Decimal(str(
        getattr(txn, 'amount', None)
        if txn is not None and getattr(txn, 'amount', None) is not None
        else (tier.price or 0)
    ))
    store_name = vendor.trading_name or vendor.name or 'Your store'
    unit = (getattr(tier, 'duration_unit', '') or '').lower()
    billing = 'Yearly' if unit in ('years', 'year') else 'Monthly'
    reference = getattr(txn, 'reference', '') or str(subscription.id)[:12]
    invoice_no = f'INV-SUB-{reference}'
    paid_at = getattr(txn, 'paid_at', None) or getattr(
        subscription, 'current_period_start', None)
    card = None
    if txn is not None and getattr(txn, 'last4', None):
        card = f"{(txn.card_type or 'Card').title()} ···· {txn.last4}"

    attachments = None
    try:
        from core.invoice_pdf import build_subscription_invoice_pdf
        pdf_bytes = build_subscription_invoice_pdf(subscription, txn)
        attachments = [(
            f'Sanoa-Subscription-{reference}.pdf', pdf_bytes, 'application/pdf',
        )]
    except Exception:
        log.exception('Subscription invoice PDF failed for sub %s',
                      getattr(subscription, 'id', '?'))

    return send_branded_email(
        subject=f'Sanoa · Subscription receipt — {tier.name}',
        to=user.email,
        template='emails/subscription_invoice.html',
        context={
            'name': _display_name(user),
            'store_name': store_name,
            'invoice_no': invoice_no,
            'reference': reference,
            'tier_name': tier.name,
            'billing': billing,
            'amount': amount,
            'paid_at': paid_at,
            'period_start': getattr(subscription, 'current_period_start', None),
            'period_end': getattr(subscription, 'current_period_end', None),
            'card': card,
            'status': (getattr(subscription, 'status', '') or '').replace('_', ' ').title(),
            'has_pdf': attachments is not None,
        },
        attachments=attachments,
    )
