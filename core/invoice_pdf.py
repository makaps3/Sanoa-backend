"""
Professional vendor invoice PDF (fpdf2).

`build_vendor_invoice_pdf(order, vendor)` returns PDF bytes for a single
vendor's slice of an order — the items they sold plus the platform
commission. Delivery and service fees are deliberately excluded: they are
collected from the customer and settled to the driver / platform, so they
never appear on a vendor invoice.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings

NAVY = (2, 48, 71)
TEAL = (33, 158, 188)
INK = (43, 58, 68)
MUTED = (124, 144, 156)
LINE = (230, 237, 241)
RED = (229, 72, 77)
GREEN = (16, 185, 129)
CARD = (247, 250, 251)


def _money(v) -> str:
    return f"R{Decimal(str(v or 0)).quantize(Decimal('0.01')):,.2f}"


# fpdf2's built-in Helvetica is latin-1 only; product names, store names and
# punctuation (en-dashes, smart quotes, emoji) can fall outside it and crash
# PDF generation. Fold the common cases to ASCII and drop anything else.
_PUNCT = {
    '–': '-', '—': '-', '‘': "'", '’': "'",
    '“': '"', '”': '"', '…': '...', '•': '-',
    '·': '-', '–': '-',
}


def _t(s) -> str:
    if s is None:
        return ''
    s = str(s)
    for k, v in _PUNCT.items():
        s = s.replace(k, v)
    return s.encode('latin-1', 'replace').decode('latin-1')


def _logo_path():
    return settings.BASE_DIR / 'static' / 'email' / 'sanoa-logo.png'


def build_vendor_invoice_pdf(order, vendor) -> bytes:
    from fpdf import FPDF

    items = list(
        order.items.filter(vendor=vendor).values(
            'product_name', 'variant_name', 'quantity',
            'unit_price', 'total_price',
        )
    )
    items_amount = sum((Decimal(str(i['total_price'])) for i in items), Decimal('0'))
    # A vendor-funded promotion reduces the goods value commission is charged
    # on (carts are one-per-vendor, so this discount belongs to this vendor).
    vendor_discount = Decimal(str(getattr(order, 'vendor_funded_discount', 0) or 0))
    vendor_discount = min(vendor_discount, items_amount)
    net_sales = (items_amount - vendor_discount).quantize(Decimal('0.01'))
    pct = Decimal(str(getattr(order, 'commission_percent', 0) or 0))
    if pct > 0:
        commission = (net_sales * pct / Decimal('100')).quantize(Decimal('0.01'))
    else:
        commission = Decimal(str(getattr(order, 'commission_amount', 0) or 0))
    payout = (net_sales - commission).quantize(Decimal('0.01'))
    coupon_code = (getattr(order, 'coupon_code', '') or '').strip()

    store_name = vendor.trading_name or vendor.name or 'Vendor'
    vendor_email = getattr(getattr(vendor, 'user', None), 'email', '') or ''
    customer_email = getattr(getattr(order, 'user', None), 'email', '') or ''
    invoice_no = f"INV-{order.order_number}"
    created = order.created_at.strftime('%d %b %Y') if order.created_at else ''
    status = (getattr(order, 'status', '') or '').replace('_', ' ').title()

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(16, 16, 16)
    W = pdf.w - 32  # content width

    # ── Header band ─────────────────────────────────────────────
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 34, style='F')
    try:
        pdf.image(str(_logo_path()), x=16, y=8, w=18, h=18)
        logo_off = 38
    except Exception:
        logo_off = 16
    pdf.set_xy(logo_off, 10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(60, 8, 'Sanoa', ln=0)
    pdf.set_xy(pdf.w - 90, 9)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(74, 8, 'INVOICE', align='R', ln=1)
    pdf.set_xy(pdf.w - 90, 19)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(180, 205, 218)
    pdf.cell(74, 6, f'{invoice_no}', align='R', ln=1)

    pdf.ln(24)

    # ── Meta: From / Bill to / details ──────────────────────────
    top = pdf.get_y()
    col = W / 3

    def label(txt, x):
        pdf.set_xy(16 + x, top)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*TEAL)
        pdf.cell(col - 4, 5, txt.upper(), ln=2)

    def line(txt, bold=False, color=INK):
        pdf.set_x(16 + _cur_x[0])
        pdf.set_font('Helvetica', 'B' if bold else '', 10)
        pdf.set_text_color(*color)
        pdf.cell(col - 4, 5.4, _t(txt)[:42], ln=2)

    _cur_x = [0]

    _cur_x[0] = 0
    label('From', 0)
    line('Sanoa (Pty) Ltd', bold=True)
    line('Cape Town, South Africa', color=MUTED)
    line(getattr(settings, 'EMAIL_FROM_ADDRESS', ''), color=MUTED)

    _cur_x[0] = col
    pdf.set_y(top)
    label('Billed to', col)
    line(store_name, bold=True)
    if vendor_email:
        line(vendor_email, color=MUTED)
    line('Vendor', color=MUTED)

    _cur_x[0] = col * 2
    pdf.set_y(top)
    label('Details', col * 2)
    line(f'Invoice date: {created}')
    line(f'Order: #{order.order_number}', color=MUTED)
    if status:
        line(f'Status: {status}', color=MUTED)

    pdf.ln(6)
    pdf.set_y(max(pdf.get_y(), top + 30))

    # ── Items table ─────────────────────────────────────────────
    x0 = 16
    c_item, c_qty, c_unit, c_amt = W * 0.50, W * 0.14, W * 0.18, W * 0.18
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*LINE)
    pdf.set_text_color(*MUTED)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_x(x0)
    pdf.cell(c_item, 9, '  ITEM', border=0, fill=True)
    pdf.cell(c_qty, 9, 'QTY', border=0, align='C', fill=True)
    pdf.cell(c_unit, 9, 'UNIT', border=0, align='R', fill=True)
    pdf.cell(c_amt, 9, 'AMOUNT  ', border=0, align='R', fill=True, ln=1)

    pdf.set_font('Helvetica', '', 10)
    for it in items:
        name = it['product_name'] or 'Item'
        if it['variant_name']:
            name = f"{name} - {it['variant_name']}"
        name = _t(name)
        pdf.set_x(x0)
        pdf.set_text_color(*INK)
        pdf.cell(c_item, 9, '  ' + name[:46], border=0)
        pdf.set_text_color(*MUTED)
        pdf.cell(c_qty, 9, str(it['quantity']), border=0, align='C')
        pdf.cell(c_unit, 9, _money(it['unit_price']), border=0, align='R')
        pdf.set_text_color(*INK)
        pdf.cell(c_amt, 9, _money(it['total_price']) + '  ', border=0, align='R', ln=1)
        pdf.set_draw_color(*LINE)
        pdf.line(x0, pdf.get_y(), x0 + W, pdf.get_y())

    # ── Totals ──────────────────────────────────────────────────
    pdf.ln(6)
    tx = x0 + W * 0.52
    tw = W * 0.48

    def total_row(k, v, *, color=INK, bold=False, big=False):
        pdf.set_x(tx)
        pdf.set_font('Helvetica', 'B' if bold else '', 12 if big else 10)
        pdf.set_text_color(*MUTED if not bold else INK)
        pdf.cell(tw * 0.55, 8 if not big else 10, k, border=0)
        pdf.set_text_color(*color)
        pdf.set_font('Helvetica', 'B' if (bold or big) else '', 13 if big else 10)
        pdf.cell(tw * 0.45, 8 if not big else 10, v + '  ', border=0, align='R', ln=1)

    total_row('Items amount', _money(items_amount))
    if vendor_discount > 0:
        disc_label = f'Promotion ({coupon_code})' if coupon_code else 'Promotion'
        total_row(_t(disc_label)[:26], '- ' + _money(vendor_discount), color=GREEN)
        total_row('Net sales', _money(net_sales))
    comm_label = f'Commission ({pct:.0f}%)' if pct else 'Commission'
    total_row(comm_label, '- ' + _money(commission), color=RED)
    pdf.set_draw_color(*LINE)
    pdf.line(tx, pdf.get_y() + 1, tx + tw - 2, pdf.get_y() + 1)
    pdf.ln(3)
    total_row('Your payout', _money(payout), color=GREEN, bold=True, big=True)

    # ── Note + footer ───────────────────────────────────────────
    pdf.ln(8)
    pdf.set_x(x0)
    pdf.set_font('Helvetica', 'I', 8.5)
    pdf.set_text_color(*MUTED)
    note = (
        'Note: Delivery and service fees are collected from the customer and '
        'settled to the driver and the platform. They are not part of this '
        'vendor invoice.'
    )
    if vendor_discount > 0:
        note += (
            ' Your own promotion was funded by you, so commission is charged '
            'on net sales. Platform-wide promotions do not affect your payout.'
        )
    pdf.multi_cell(W, 4.6, _t(note))
    pdf.ln(2)
    pdf.set_x(x0)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        W, 4.6,
        _t(f'Thank you for selling on Sanoa. This invoice was generated for '
           f'{customer_email or "the customer order"} and is issued to '
           f'{store_name}.'),
    )

    out = pdf.output()
    return bytes(out)


def build_subscription_invoice_pdf(subscription, txn=None) -> bytes:
    """Professional receipt/invoice PDF for a vendor tier subscription."""
    from fpdf import FPDF

    tier = subscription.tier
    vendor = getattr(subscription, 'vendor', None)
    store_name = vendor.trading_name or vendor.name or 'Vendor'
    vendor_email = getattr(getattr(vendor, 'user', None), 'email', '') or ''
    amount = Decimal(str(
        getattr(txn, 'amount', None)
        if txn is not None and getattr(txn, 'amount', None) is not None
        else (tier.price or 0)
    ))
    unit = (getattr(tier, 'duration_unit', '') or '').lower()
    billing = 'Yearly' if unit in ('years', 'year') else 'Monthly'
    reference = getattr(txn, 'reference', '') or str(subscription.id)[:12]
    invoice_no = f'INV-SUB-{reference}'
    paid = getattr(txn, 'paid_at', None) or getattr(subscription, 'current_period_start', None)
    paid_str = paid.strftime('%d %b %Y') if paid else ''
    p_start = getattr(subscription, 'current_period_start', None)
    p_end = getattr(subscription, 'current_period_end', None)
    period = ''
    if p_start and p_end:
        period = f"{p_start.strftime('%d %b %Y')} - {p_end.strftime('%d %b %Y')}"
    card = ''
    if txn is not None and getattr(txn, 'last4', None):
        card = f"{(txn.card_type or 'Card').title()} **** {txn.last4}"

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(16, 16, 16)
    W = pdf.w - 32

    # Header band
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, pdf.w, 34, style='F')
    try:
        pdf.image(str(_logo_path()), x=16, y=8, w=18, h=18)
        logo_off = 38
    except Exception:
        logo_off = 16
    pdf.set_xy(logo_off, 10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 18)
    pdf.cell(60, 8, 'Sanoa', ln=0)
    pdf.set_xy(pdf.w - 90, 9)
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(74, 8, 'RECEIPT', align='R', ln=1)
    pdf.set_xy(pdf.w - 90, 19)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(180, 205, 218)
    pdf.cell(74, 6, invoice_no, align='R', ln=1)

    pdf.ln(26)
    top = pdf.get_y()

    # Billed to
    pdf.set_xy(16, top)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*TEAL)
    pdf.cell(90, 5, 'BILLED TO', ln=2)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(*INK)
    pdf.set_x(16)
    pdf.cell(90, 6, _t(store_name)[:44], ln=2)
    if vendor_email:
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(*MUTED)
        pdf.set_x(16)
        pdf.cell(90, 5.5, _t(vendor_email)[:44], ln=2)

    # Payment meta (right)
    pdf.set_xy(16 + W * 0.55, top)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(*TEAL)
    pdf.cell(W * 0.45, 5, 'PAYMENT', ln=2)

    def meta(k, v):
        pdf.set_x(16 + W * 0.55)
        pdf.set_font('Helvetica', '', 9.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(W * 0.22, 5.6, k, ln=0)
        pdf.set_font('Helvetica', 'B', 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(W * 0.23, 5.6, v, align='R', ln=2)

    meta('Date', paid_str)
    if card:
        meta('Method', _t(card))
    meta('Status', 'Paid')

    pdf.ln(12)
    pdf.set_y(max(pdf.get_y(), top + 34))

    # Line item
    x0 = 16
    c_desc, c_amt = W * 0.72, W * 0.28
    pdf.set_fill_color(*CARD)
    pdf.set_text_color(*MUTED)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_x(x0)
    pdf.cell(c_desc, 9, '  DESCRIPTION', fill=True)
    pdf.cell(c_amt, 9, 'AMOUNT  ', align='R', fill=True, ln=1)

    pdf.set_font('Helvetica', '', 11)
    pdf.set_x(x0)
    pdf.set_text_color(*INK)
    desc = _t(f'{tier.name} plan - {billing}')
    pdf.cell(c_desc, 11, '  ' + desc[:50])
    pdf.cell(c_amt, 11, _money(amount) + '  ', align='R', ln=1)
    pdf.set_draw_color(*LINE)
    pdf.line(x0, pdf.get_y(), x0 + W, pdf.get_y())
    if period:
        pdf.set_x(x0)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(W, 7, '  Billing period: ' + _t(period), ln=1)

    # Total
    pdf.ln(4)
    tx = x0 + W * 0.52
    tw = W * 0.48
    pdf.set_x(tx)
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(*INK)
    pdf.cell(tw * 0.55, 10, 'Total paid')
    pdf.set_text_color(*GREEN)
    pdf.cell(tw * 0.45, 10, _money(amount) + '  ', align='R', ln=1)

    # Footer
    pdf.ln(10)
    pdf.set_x(x0)
    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(
        W, 4.6,
        _t(f'Thank you for subscribing to Sanoa. This receipt confirms your '
           f'{billing.lower()} {tier.name} subscription payment '
           f'(ref {reference}).'),
    )

    out = pdf.output()
    return bytes(out)
