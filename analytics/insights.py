"""
Rule-based AI insight note generator for analytics endpoints.
Produces human-readable, actionable notes from metric values.
No external AI API calls — all logic is deterministic.
"""
from decimal import Decimal


def _pct(val):
    return round(float(val or 0), 1)


def _rand(val):
    return f"R{float(val or 0):,.2f}"


# ── Platform Overview ─────────────────────────────────────────────────────────

def platform_overview_insights(data):
    notes = []
    revenue = data.get('revenue', {}) or {}
    # Prefer the structured actual/projected blocks; fall back to flat keys.
    actual_block = revenue.get('actual') if isinstance(revenue.get('actual'), dict) else None
    diff_block = revenue.get('difference') if isinstance(revenue.get('difference'), dict) else None
    growth = (actual_block or {}).get('growth_percent') if actual_block else revenue.get('growth_percent')

    if growth is not None:
        if growth >= 20:
            notes.append(f"📈 Actual revenue is up {growth:.1f}% vs the previous period — strong growth momentum.")
        elif growth >= 5:
            notes.append(f"📊 Actual revenue grew {growth:.1f}% vs the previous period — steady progress.")
        elif growth >= 0:
            notes.append(f"⚠️ Actual revenue growth is flat at {growth:.1f}%. Consider promotions or vendor onboarding.")
        else:
            notes.append(f"🔴 Actual revenue declined {abs(growth):.1f}% vs the previous period. Investigate top cancellation drivers.")

    if diff_block:
        try:
            gap = float(diff_block.get('amount') or 0)
        except (TypeError, ValueError):
            gap = 0
        conversion = diff_block.get('conversion_percent')
        if gap > 0:
            notes.append(
                f"🔮 {_rand(gap)} sits in the projected pipeline awaiting delivery — convert these to grow actual revenue."
            )
        if conversion is not None:
            if conversion >= 80:
                notes.append(f"✅ {conversion:.1f}% of projected revenue is already realised — excellent platform fulfilment.")
            elif conversion < 50:
                notes.append(f"⚠️ Only {conversion:.1f}% of projected revenue has converted into actual. Investigate fulfilment bottlenecks.")

    orders = data.get('orders', {})
    total = orders.get('total', 0)
    cancelled = orders.get('cancelled', 0)
    if total and cancelled / total > 0.2:
        notes.append(f"⚠️ Cancellation rate is high ({cancelled/total*100:.1f}%). Review top cancellation reasons.")

    deliveries = data.get('deliveries', {})
    d_total = deliveries.get('total', 0)
    d_completed = deliveries.get('completed', 0)
    if d_total and d_completed / d_total < 0.8:
        notes.append(f"🚚 Delivery completion rate is {d_completed/d_total*100:.1f}% — below the 80% target. Investigate failed deliveries.")

    users = data.get('users', {})
    if users.get('new_customers', 0) == 0:
        notes.append("👤 No new customer registrations this period. Consider a referral or marketing campaign.")
    elif users.get('new_customers', 0) > 50:
        notes.append(f"🎉 {users['new_customers']} new customers joined this period — great acquisition!")

    if not notes:
        notes.append("✅ Platform metrics look healthy this period.")
    return notes


# ── Customer Analytics ────────────────────────────────────────────────────────

def customer_analytics_insights(data):
    notes = []
    churn = data.get('churn_risk', {})
    high = churn.get('high', 0)
    medium = churn.get('medium', 0)
    total = data.get('totals', {}).get('total_customers', 0) or 1

    if high / total > 0.3:
        notes.append(f"🚨 {high} customers ({high/total*100:.1f}%) are at HIGH churn risk. Launch an immediate re-engagement campaign with loyalty rewards.")
    elif high / total > 0.15:
        notes.append(f"⚠️ {high} customers are at high churn risk. Consider targeted email or push notification campaigns.")
    else:
        notes.append(f"✅ Churn risk is well managed — only {high} high-risk customers.")

    if medium / total > 0.4:
        notes.append(f"📧 {medium} customers are at medium churn risk. A discount voucher or loyalty point bonus could retain them.")

    suspended = data.get('totals', {}).get('suspended', 0)
    if suspended > 0:
        notes.append(f"🔒 {suspended} customers are currently suspended due to overdue credit. Prioritise repayment outreach.")

    avg_loyalty = data.get('loyalty', {}).get('avg_points_per_customer', 0)
    if float(avg_loyalty or 0) < 100:
        notes.append("💎 Average loyalty points are low. Consider a bonus points event to increase engagement.")

    return notes


# ── Order Analytics ───────────────────────────────────────────────────────────

def order_analytics_insights(data):
    notes = []
    totals = data.get('totals', {})
    total = totals.get('total_orders', 0)
    completed = totals.get('completed', 0)
    cancelled = totals.get('cancelled', 0)
    refunded = totals.get('refunded', 0)

    if total:
        comp_rate = completed / total * 100
        if comp_rate >= 85:
            notes.append(f"✅ Order completion rate is excellent at {comp_rate:.1f}%.")
        elif comp_rate >= 70:
            notes.append(f"📊 Order completion rate is {comp_rate:.1f}%. Target is 85%+ — review unfulfilled orders.")
        else:
            notes.append(f"🔴 Order completion rate is critically low at {comp_rate:.1f}%. Immediate action needed.")

        if cancelled / total > 0.15:
            notes.append(f"⚠️ {cancelled/total*100:.1f}% of orders were cancelled. Analyse reasons — stock issues or payment failures?")
        if refunded / total > 0.05:
            notes.append(f"💸 Refund rate is {refunded/total*100:.1f}%. Investigate product quality or delivery issues.")

    avg = float(totals.get('avg_order_value', 0) or 0)
    if avg < 100:
        notes.append(f"📦 Average order value is {_rand(avg)}. Upselling or bundling could increase basket size.")
    elif avg > 500:
        notes.append(f"💰 Average order value is {_rand(avg)} — customers are making high-value purchases.")

    return notes


# ── Payment Analytics ─────────────────────────────────────────────────────────

def payment_analytics_insights(data):
    notes = []
    txns = data.get('transactions', {})
    success_rate = float(txns.get('success_rate_percent', 0) or 0)
    # Accept both new (`platform_fee`) and legacy (`paystack_fees`) keys.
    fees = float(txns.get('platform_fee', txns.get('paystack_fees', 0)) or 0)
    revenue = float(txns.get('total_revenue', 0) or 0)

    if success_rate >= 95:
        notes.append(f"✅ Payment success rate is excellent at {success_rate:.1f}%.")
    elif success_rate >= 85:
        notes.append(f"📊 Payment success rate is {success_rate:.1f}%. Investigate failed payment channels.")
    else:
        notes.append(f"🔴 Payment success rate is critically low at {success_rate:.1f}%. Check payment gateway health.")

    if revenue and fees / revenue > 0.03:
        notes.append(f"💳 Platform fees are {fees/revenue*100:.1f}% of revenue ({_rand(fees)}). Consider fee optimisation strategies.")

    disputes = data.get('disputes', {})
    if disputes.get('count', 0) > 0:
        notes.append(f"⚠️ {disputes['count']} disputes totalling {_rand(disputes.get('total_amount', 0))}. Resolve within SLA.")

    return notes


# ── Vendor Performance ────────────────────────────────────────────────────────

def vendor_overview_insights(data):
    notes = []
    revenue = data.get('revenue', {})
    # Prefer the structured actual/projected blocks; fall back to flat keys.
    actual_block = revenue.get('actual') if isinstance(revenue.get('actual'), dict) else None
    projected_block = revenue.get('projected') if isinstance(revenue.get('projected'), dict) else None
    diff_block = revenue.get('difference') if isinstance(revenue.get('difference'), dict) else None

    actual_growth = (actual_block or {}).get('growth_percent') if actual_block else revenue.get('growth_percent')
    projected_total = float((projected_block or {}).get('total') or 0) if projected_block else None
    gap = float((diff_block or {}).get('amount') or 0) if diff_block else None
    conversion = (diff_block or {}).get('conversion_percent') if diff_block else None
    orders = data.get('orders', {})
    perf = data.get('performance_score')

    if actual_growth is not None:
        if actual_growth >= 15:
            notes.append(f"📈 Your actual revenue grew {actual_growth:.1f}% vs the previous period — excellent performance!")
        elif actual_growth >= 0:
            notes.append(f"📊 Actual revenue grew {actual_growth:.1f}%. Keep consistent to move into a higher tier.")
        else:
            notes.append(f"📉 Actual revenue declined {abs(actual_growth):.1f}%. Review product listings and pricing.")

    if gap is not None and gap > 0:
        gap_note = (
            f"🔮 {_rand(gap)} is still in the pipeline — projected revenue exceeds "
            f"actual by this much. Fulfil outstanding orders to realise it."
        )
        notes.append(gap_note)

    if conversion is not None and projected_total and projected_total > 0:
        if conversion >= 80:
            notes.append(f"✅ {conversion:.1f}% of projected revenue has converted into actual — excellent fulfilment rate.")
        elif conversion >= 50:
            notes.append(f"📊 {conversion:.1f}% of projected revenue has converted into actual. Speeding up fulfilment will lift this further.")
        else:
            notes.append(f"⚠️ Only {conversion:.1f}% of projected revenue has converted into actual. Investigate fulfilment bottlenecks.")

    total = orders.get('total', 0)
    completed = orders.get('completed', 0)
    if total:
        rate = completed / total * 100
        if rate < 75:
            notes.append(f"⚠️ Your order completion rate is {rate:.1f}%. Fulfil orders faster to improve your performance score.")
        else:
            notes.append(f"✅ Order completion rate is {rate:.1f}% — well done.")

    if perf:
        score = float(perf.get('score', 0) or 0)
        tier = perf.get('tier', 'bronze')
        if score >= 80:
            notes.append(f"🏆 You're in the Platinum tier with a performance score of {score:.0f}/100.")
        elif score >= 65:
            notes.append(f"🥇 Gold tier — score {score:.0f}/100. Reduce refunds and disputes to reach Platinum.")
        elif score >= 45:
            notes.append(f"🥈 Silver tier — score {score:.0f}/100. Increase order completion and reduce cancellations.")
        else:
            notes.append(f"🥉 Bronze tier — score {score:.0f}/100. Focus on fulfilling orders consistently to improve your tier.")

    return notes


def vendor_product_insights(data):
    notes = []
    totals = data.get('totals', {})
    slow = data.get('slow_moving', [])
    top = data.get('top_selling', [])

    if len(slow) > 5:
        notes.append(f"📦 {len(slow)} active products had no sales this period. Consider promotions, price reductions, or removing them.")

    if top:
        top_item = top[0]
        notes.append(f"🔥 Your best seller is '{top_item.get('product_name', '')}' with {top_item.get('units_sold', 0)} units sold.")

    avg = float(totals.get('avg_price', 0) or 0)
    if avg < 50:
        notes.append("💡 Average product price is low. Consider premium bundles or larger pack sizes to increase order value.")

    return notes


def vendor_order_insights(data):
    notes = []
    totals = data.get('totals', {})
    total = totals.get('total_orders', 0)
    completed = totals.get('completed', 0)
    cancelled = totals.get('cancelled', 0)
    refunded = totals.get('refunded', 0)

    if total:
        comp_rate = completed / total * 100
        if comp_rate >= 85:
            notes.append(f"✅ Order completion rate is excellent at {comp_rate:.1f}%.")
        elif comp_rate >= 70:
            notes.append(f"📊 Order completion rate is {comp_rate:.1f}%. Target is 85%+ — follow up on pending orders.")
        else:
            notes.append(f"🔴 Order completion rate is critically low at {comp_rate:.1f}%. Review unfulfilled orders immediately.")

        if total > 0 and cancelled / total > 0.15:
            notes.append(f"⚠️ {cancelled / total * 100:.1f}% of orders were cancelled. Check stock availability and pricing.")
        if total > 0 and refunded / total > 0.05:
            notes.append(f"💸 Refund rate is {refunded / total * 100:.1f}%. Investigate product quality or delivery issues.")

    avg = float(totals.get('avg_order_value', 0) or 0)
    if avg > 0:
        if avg < 100:
            notes.append(f"📦 Average order value is {_rand(avg)}. Bundling products can increase basket size.")
        elif avg > 500:
            notes.append(f"💰 Average order value is {_rand(avg)} — customers are making high-value purchases. Keep inventory stocked.")

    if not notes:
        notes.append("✅ Order metrics look healthy this period.")
    return notes


def vendor_category_insights(data):
    notes = []
    totals = data.get('totals', {})
    revenue_list = data.get('revenue_per_category', [])
    products_list = data.get('products_per_category', [])

    total_with_products = totals.get('total_categories_with_products', 0)
    total_with_revenue = totals.get('total_categories_with_revenue', 0)

    if total_with_products == 0:
        notes.append("📦 No products found. Add products to your categories to start tracking performance.")
        return notes

    if total_with_revenue == 0:
        notes.append("📊 No category revenue recorded for this period. Ensure orders have been placed and paid.")
        return notes

    top_cat = data.get('top_category')
    if top_cat and revenue_list:
        total_rev = sum(float(r.get('revenue') or 0) for r in revenue_list)
        top_rev = float(revenue_list[0].get('revenue') or 0)
        if total_rev > 0:
            top_pct = top_rev / total_rev * 100
            if top_pct > 70:
                notes.append(f"⚠️ '{top_cat}' drives {top_pct:.1f}% of your revenue. Diversify across more categories to reduce dependency risk.")
            else:
                notes.append(f"🏆 Top revenue category: '{top_cat}' ({top_pct:.1f}% of period revenue).")

    # Categories that have active products but no sales this period
    cat_ids_with_rev = {str(r.get('category_id')) for r in revenue_list}
    no_sales = [
        p['category_name']
        for p in products_list
        if str(p.get('category_id')) not in cat_ids_with_rev and (p.get('active_products') or 0) > 0
    ]
    if no_sales:
        names = ', '.join(no_sales[:3])
        suffix = f" (+{len(no_sales) - 3} more)" if len(no_sales) > 3 else ''
        notes.append(f"📌 No sales from: {names}{suffix}. Consider promotions or featured listings for these categories.")

    if not notes:
        notes.append("✅ Category performance looks balanced this period.")
    return notes


def vendor_customer_insights(data):
    notes = []
    totals = data.get('totals', {})
    unique = totals.get('unique_customers', 0)
    new = totals.get('new_customers', 0)
    repeat = totals.get('repeat_customers', 0)
    ltv = float(totals.get('avg_customer_lifetime_value', 0) or 0)

    if unique == 0:
        notes.append("👤 No customers placed orders this period. Review product visibility and pricing.")
        return notes

    new_rate = new / unique * 100 if unique else 0
    repeat_rate = repeat / unique * 100 if unique else 0

    if new_rate > 70:
        notes.append(f"🆕 {new_rate:.1f}% of customers are first-time buyers. Great acquisition! Focus on re-engagement to convert them into repeat buyers.")

    if repeat_rate >= 30:
        notes.append(f"🔁 {repeat} repeat customers ({repeat_rate:.1f}%) — loyal buyers are driving your sales. Consider a loyalty reward.")
    elif repeat_rate < 10 and unique > 5:
        notes.append(f"⚠️ Only {repeat} repeat customers ({repeat_rate:.1f}%). Post-purchase follow-ups or coupons can improve retention.")

    if ltv > 500:
        notes.append(f"💰 Average customer lifetime value is {_rand(ltv)} — high-value shoppers are choosing your store.")
    elif ltv < 100 and unique > 0:
        notes.append(f"📈 Average lifetime value is {_rand(ltv)}. Upselling and bundles can increase this significantly.")

    if not notes:
        notes.append("✅ Customer metrics look healthy this period.")
    return notes


def vendor_payment_insights(data):
    notes = []
    txns = data.get('transactions', {})
    success_rate = float(txns.get('success_rate_percent', 0) or 0)
    # Revenue is the vendor's payout (items − commission). Commission is the
    # platform cut already removed; surface it for context.
    commission = float(txns.get('commission', 0) or 0)
    revenue = float(txns.get('total_revenue', 0) or 0)

    if txns.get('total', 0) == 0:
        notes.append("📊 No payment transactions recorded this period.")
        return notes

    if success_rate >= 95:
        notes.append(f"✅ Payment success rate is excellent at {success_rate:.1f}%.")
    elif success_rate >= 85:
        notes.append(f"📊 Payment success rate is {success_rate:.1f}%. Investigate any failed channels.")
    else:
        notes.append(f"🔴 Payment success rate is {success_rate:.1f}%. High failure rate may be costing you sales — check your payment settings.")

    if revenue > 0 and commission > 0:
        comm_pct = commission / (revenue + commission) * 100
        notes.append(f"💳 You kept {_rand(revenue)} after {_rand(commission)} platform commission ({comm_pct:.1f}%). Upgrade your plan to lower it.")

    refunds = data.get('refunds', {})
    refund_amt = float(refunds.get('total_amount', 0) or 0)
    if refund_amt > 0 and revenue > 0:
        refund_pct = refund_amt / revenue * 100
        if refund_pct > 5:
            notes.append(f"💸 Refunds total {_rand(refund_amt)} ({refund_pct:.1f}% of revenue). Investigate product quality or description accuracy.")

    if not notes:
        notes.append("✅ Payment metrics look healthy this period.")
    return notes


def vendor_negotiation_insights(data):
    notes = []
    totals = data.get('totals', {})
    rate = float(totals.get('agreement_rate_percent', 0) or 0)
    open_count = totals.get('open', 0)

    if rate >= 70:
        notes.append(f"🤝 Excellent negotiation agreement rate of {rate:.1f}%. Customers respond well to your pricing.")
    elif rate >= 50:
        notes.append(f"📊 Agreement rate is {rate:.1f}%. Adjusting your price floor policy could improve conversions.")
    else:
        notes.append(f"⚠️ Low negotiation agreement rate ({rate:.1f}%). Consider enabling AI mode to handle negotiations automatically.")

    if open_count > 10:
        notes.append(f"⏳ You have {open_count} open negotiations. Respond quickly — unresolved rooms expire and reduce your score.")

    return notes


# ── Negotiations (admin) ──────────────────────────────────────────────────────

def negotiation_analytics_insights(data):
    notes = []
    totals = data.get('totals', {})
    rate = float(totals.get('agreement_rate_percent', 0) or 0)
    ai = data.get('ai_performance', {})
    manual = data.get('manual_performance', {})

    if rate >= 60:
        notes.append(f"✅ Platform-wide negotiation agreement rate is {rate:.1f}%.")
    else:
        notes.append(f"⚠️ Agreement rate is {rate:.1f}%. Encourage vendors to set competitive price policies.")

    ai_rate = float(ai.get('agreement_rate_percent', 0) or 0)
    manual_rate = float(manual.get('agreement_rate_percent', 0) or 0)
    if ai_rate > manual_rate + 10:
        notes.append(f"🤖 AI negotiations convert {ai_rate:.1f}% vs {manual_rate:.1f}% for manual — AI mode is more effective. Encourage vendor adoption.")
    elif manual_rate > ai_rate + 10:
        notes.append(f"💬 Manual negotiations convert {manual_rate:.1f}% vs AI {ai_rate:.1f}%. Vendors who reply personally are outperforming the AI model.")

    return notes


# ── Debit / Credit ────────────────────────────────────────────────────────────

def debit_analytics_insights(data):
    notes = []
    accounts = data.get('accounts', {})
    balances = data.get('balances', {})
    purchases = data.get('purchases', {})

    suspended = accounts.get('suspended', 0)
    total_acc = accounts.get('total', 0) or 1
    if suspended / total_acc > 0.1:
        notes.append(f"🔴 {suspended} credit accounts ({suspended/total_acc*100:.1f}%) are suspended. High suspension rates indicate repayment issues — run targeted outreach.")

    overdue = purchases.get('overdue_count', 0)
    if overdue > 0:
        notes.append(f"⏰ {overdue} credit purchases are overdue. Consider sending automated payment reminders.")

    outstanding = float(balances.get('total_outstanding_balance', 0) or 0)
    penalties = float(balances.get('total_penalties', 0) or 0)
    if outstanding > 0 and penalties / outstanding > 0.1:
        notes.append(f"💸 Penalties account for {penalties/outstanding*100:.1f}% of outstanding balance ({_rand(penalties)}). This may worsen default rates.")

    return notes


# ── Deliveries ────────────────────────────────────────────────────────────────

def delivery_analytics_insights(data):
    notes = []
    totals = data.get('totals', {})
    perf = data.get('performance', {})
    ratings = data.get('ratings', {})

    rate = float(totals.get('completion_rate_percent', 0) or 0)
    if rate >= 90:
        notes.append(f"✅ Delivery completion rate is excellent at {rate:.1f}%.")
    elif rate >= 75:
        notes.append(f"📊 Delivery completion rate is {rate:.1f}%. Investigate reasons for {totals.get('failed', 0)} failed deliveries.")
    else:
        notes.append(f"🔴 Delivery completion rate is critically low at {rate:.1f}%. Review driver availability and routing.")

    avg_time = perf.get('avg_delivery_time_mins')
    if avg_time:
        if avg_time > 90:
            notes.append(f"⏱️ Average delivery time is {avg_time:.0f} minutes — above the 90-minute target. Optimise driver dispatch.")
        else:
            notes.append(f"⚡ Average delivery time is {avg_time:.0f} minutes — within target.")

    avg_rating = float(ratings.get('avg_driver_rating', 0) or 0)
    if avg_rating < 3.5:
        notes.append(f"⭐ Average driver rating is {avg_rating:.1f}/5. Low ratings may reduce customer retention — review underperforming drivers.")

    return notes


# ── Drivers (admin) ───────────────────────────────────────────────────────────

def driver_analytics_insights(data):
    notes = []
    totals = data.get('totals', {})
    ml = data.get('ml_performance', {})

    available = totals.get('available', 0)
    total = totals.get('total_drivers', 0) or 1
    if available / total < 0.3:
        notes.append(f"⚠️ Only {available} of {total} drivers are currently online ({available/total*100:.0f}%). Driver availability is low — consider incentive schemes.")

    pending = totals.get('pending_verification', 0)
    if pending > 0:
        notes.append(f"📋 {pending} drivers are awaiting verification. Approve quickly to increase delivery capacity.")

    anomaly = ml.get('payout_anomaly_flagged', 0)
    if anomaly > 0:
        notes.append(f"🚨 {anomaly} drivers have been flagged for payout anomalies by XGBoost. Review their earning patterns immediately.")

    avg_rating = float(totals.get('avg_rating', 0) or 0)
    if avg_rating < 3.5:
        notes.append(f"⭐ Platform average driver rating is {avg_rating:.1f}/5. Consider mandatory performance improvement for low-rated drivers.")

    return notes


# ── Payouts (admin) ───────────────────────────────────────────────────────────

def payout_analytics_insights(data):
    notes = []
    payouts = data.get('payouts', {})
    gross = float(payouts.get('total_gross', 0) or 0)
    commission = float(payouts.get('total_commission', 0) or 0)
    pending = float(payouts.get('pending', 0) or 0)

    if gross > 0:
        commission_rate = commission / gross * 100
        notes.append(f"💰 Platform retained {_rand(commission)} ({commission_rate:.1f}%) in commissions this period.")

    if pending > 0:
        notes.append(f"⏳ {_rand(pending)} in driver payouts are pending. Process promptly to maintain driver trust.")

    top_earners = data.get('top_earners', [])
    if top_earners:
        top = top_earners[0]
        notes.append(f"🏆 Top earning driver: {top.get('driver__user__email', 'N/A')} with {_rand(top.get('total', 0))} net this period.")

    return notes


# ── Driver self-analytics ─────────────────────────────────────────────────────

def driver_overview_insights(data):
    notes = []
    deliveries = data.get('deliveries', {})
    earnings = data.get('earnings', {})
    rating = float(data.get('rating', 0) or 0)
    perf = data.get('performance_score')

    rate = float(deliveries.get('completion_rate_percent', 0) or 0)
    if rate >= 90:
        notes.append(f"✅ Great job! Your delivery completion rate is {rate:.1f}%.")
    elif rate >= 75:
        notes.append(f"📊 Your completion rate is {rate:.1f}%. Completing more jobs will improve your performance grade.")
    else:
        notes.append(f"⚠️ Completion rate is {rate:.1f}%. Avoid cancellations to protect your grade and earnings.")

    if rating >= 4.5:
        notes.append(f"⭐ Excellent rating of {rating:.1f}/5! Keep up the great service.")
    elif rating >= 4.0:
        notes.append(f"⭐ Good rating of {rating:.1f}/5. Focus on on-time delivery for a 5-star experience.")
    elif rating < 3.5:
        notes.append(f"⚠️ Your rating is {rating:.1f}/5. Review customer feedback to identify areas for improvement.")

    if perf and perf.get('payout_anomaly'):
        notes.append("🚨 Your payout pattern has been flagged for review. Contact support if you believe this is an error.")

    return notes


def driver_earnings_insights(data):
    notes = []
    earnings = data.get('earnings', {})
    net = float(earnings.get('net', 0) or 0)
    gross = float(earnings.get('gross', 0) or 0)
    commission = float(earnings.get('platform_commission', 0) or 0)
    jobs = earnings.get('total_jobs', 0)

    if gross > 0:
        notes.append(f"💰 You earned {_rand(net)} net after {_rand(commission)} platform commission ({commission/gross*100:.1f}%) this period.")

    avg_per_job = float(earnings.get('avg_per_job', 0) or 0)
    if avg_per_job < 20:
        notes.append("📦 Average earning per delivery is low. Take longer-distance jobs to boost your income.")
    elif avg_per_job > 50:
        notes.append(f"🚀 Average {_rand(avg_per_job)} per delivery — great efficiency!")

    pending = data.get('payouts', {}).get('status_breakdown', [])
    pending_amount = next((float(r.get('total', 0) or 0) for r in pending if r.get('status') == 'pending'), 0)
    if pending_amount > 0:
        notes.append(f"⏳ {_rand(pending_amount)} in earnings is pending payout. Payouts are processed weekly.")

    return notes


def subscription_analytics_insights(data):
    notes = []
    cust = data.get('customer_subscriptions', {})
    vendor = data.get('vendor_tier_subscriptions', {})
    combined = data.get('combined', {})

    # Combined MRR
    mrr = float(combined.get('combined_mrr', 0) or 0)
    if mrr > 0:
        notes.append(f"💰 Combined estimated MRR is R{mrr:,.2f} across customer and vendor subscriptions.")

    # Customer subscription health
    cust_active = cust.get('active', 0)
    cust_total = cust.get('total', 0) or 1
    cust_cancelled = cust.get('cancellations_this_period', 0)
    if cust_active > 0:
        notes.append(f"👥 {cust_active} customers are on active credit plans.")
    if cust_cancelled > 0:
        churn_rate = cust_cancelled / cust_total * 100
        if churn_rate > 10:
            notes.append(f"⚠️ {cust_cancelled} customer subscription cancellations this period ({churn_rate:.1f}% churn). Investigate reasons and improve retention.")
        else:
            notes.append(f"📊 {cust_cancelled} customer cancellations this period ({churn_rate:.1f}% churn rate).")

    cust_past_due = cust.get('past_due', 0)
    if cust_past_due > 0:
        notes.append(f"🔴 {cust_past_due} customer subscriptions are past due. Trigger payment retries via Paystack.")

    cust_trialing = cust.get('trialing', 0)
    if cust_trialing > 0:
        notes.append(f"🆓 {cust_trialing} customers are currently on a free trial. Convert them with targeted in-app messaging.")

    # Vendor tier subscription health
    vendor_active = vendor.get('active', 0)
    vendor_total = vendor.get('total', 0) or 1
    vendor_cancelled = vendor.get('cancellations_this_period', 0)
    if vendor_active > 0:
        notes.append(f"🏪 {vendor_active} vendors are on paid business tiers.")
    if vendor_cancelled > 0:
        vendor_churn = vendor_cancelled / vendor_total * 100
        if vendor_churn > 10:
            notes.append(f"⚠️ {vendor_cancelled} vendor tier cancellations this period ({vendor_churn:.1f}% churn). Review tier value proposition.")
        else:
            notes.append(f"📊 {vendor_cancelled} vendor tier cancellations ({vendor_churn:.1f}% churn rate).")

    vendor_past_due = vendor.get('past_due', 0)
    if vendor_past_due > 0:
        notes.append(f"🔴 {vendor_past_due} vendor tier subscriptions are past due. Retry charges or risk losing their active tier benefits.")

    # New subscriptions this period
    new_total = combined.get('new_this_period', 0)
    if new_total > 0:
        notes.append(f"🆕 {new_total} new subscriptions started this period.")

    return notes


def driver_performance_insights(data):
    notes = []
    perf = data.get('delivery_performance', {})
    ml = data.get('ml_performance_score')
    ratings = data.get('ratings', {})
    shifts = data.get('shifts', {})

    on_time = float(perf.get('on_time_rate_percent', 0) or 0)
    if on_time >= 80:
        notes.append(f"⚡ You delivered {on_time:.1f}% of orders on time — excellent!")
    elif on_time >= 60:
        notes.append(f"📊 On-time rate is {on_time:.1f}%. Aim for 80%+ to improve your performance grade.")
    else:
        notes.append(f"⏱️ On-time rate is {on_time:.1f}%. Late deliveries lower your rating and grade — plan routes in advance.")

    avg_time = perf.get('avg_delivery_time_mins')
    if avg_time and avg_time > 90:
        notes.append(f"🚗 Average delivery time is {avg_time:.0f} mins — try to stay under 90 mins.")

    hours = float(shifts.get('total_hours_online', 0) or 0)
    if hours < 20:
        notes.append(f"📅 You were online {hours:.1f} hours this period. More active hours = more earnings opportunities.")

    if ml:
        grade = ml.get('grade', 'C')
        score = float(ml.get('score', 0) or 0)
        if grade in ('A', 'B'):
            notes.append(f"🏅 Performance grade: {grade} ({score:.0f}/100). You're among the top drivers on the platform!")
        elif grade == 'C':
            notes.append(f"📈 Performance grade: {grade} ({score:.0f}/100). Consistent on-time delivery will push you to grade B.")
        else:
            notes.append(f"⚠️ Performance grade: {grade} ({score:.0f}/100). Focus on completion rate and customer ratings to improve.")

    return notes
