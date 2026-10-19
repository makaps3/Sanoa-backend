# Admin Subscription Analytics — Dart Service Reference

Base URL: `GET /api/platform-admin/analytics/subscriptions/`  
All requests require `Authorization: Bearer <admin_access_token>`.

Covers **two subscription systems** in a single endpoint:
- **Customer credit plans** (`subscriptions` app) — buyers subscribe to credit plans (Basic, Premium, Plus)
- **Vendor business tiers** (`tiers` app) — vendors subscribe to platform tiers (Starter, Growth, Pro, etc.)

---

## Query Parameters

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `period` | string | `?period=month` | `today` · `week` · `month` (default) · `year` |
| `from` | ISO date | `?from=2026-01-01` | Custom start date (UTC) |
| `to` | ISO date | `?to=2026-03-31` | Custom end date (UTC) |

---

## Dart Models

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;


// ─────────────────────────────────────────────────────────────────────────────
// Shared building blocks
// ─────────────────────────────────────────────────────────────────────────────

class AnalyticsPeriod {
  final DateTime start;
  final DateTime end;

  const AnalyticsPeriod({required this.start, required this.end});

  factory AnalyticsPeriod.fromJson(Map<String, dynamic> json) {
    return AnalyticsPeriod(
      start: DateTime.parse(json['start'] as String),
      end: DateTime.parse(json['end'] as String),
    );
  }
}

class SubscriptionStatusBreakdownItem {
  final String status;
  final int count;

  const SubscriptionStatusBreakdownItem({
    required this.status,
    required this.count,
  });

  factory SubscriptionStatusBreakdownItem.fromJson(Map<String, dynamic> json) {
    return SubscriptionStatusBreakdownItem(
      status: json['status'] as String? ?? '',
      count: (json['count'] as num?)?.toInt() ?? 0,
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Customer plan — plan_breakdown entry
// ─────────────────────────────────────────────────────────────────────────────

class CustomerPlanBreakdown {
  /// UUID of the Plan record.
  final String planId;
  final String planName;
  final String slug;

  /// 'basic' | 'premium' | 'plus'
  final String planTier;

  /// Subscription price per billing cycle (ZAR).
  final double price;

  /// 'monthly' | 'yearly'
  final String billingCycle;

  /// Number of active/trialing subscribers on this plan right now.
  final int subscriberCount;

  const CustomerPlanBreakdown({
    required this.planId,
    required this.planName,
    required this.slug,
    required this.planTier,
    required this.price,
    required this.billingCycle,
    required this.subscriberCount,
  });

  factory CustomerPlanBreakdown.fromJson(Map<String, dynamic> json) {
    return CustomerPlanBreakdown(
      planId: json['plan__id']?.toString() ?? '',
      planName: json['plan__name'] as String? ?? '',
      slug: json['plan__slug'] as String? ?? '',
      planTier: json['plan__plan_tier'] as String? ?? '',
      price: double.parse((json['plan__price'] ?? 0).toString()),
      billingCycle: json['plan__billing_cycle'] as String? ?? 'monthly',
      subscriberCount: (json['subscriber_count'] as num?)?.toInt() ?? 0,
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Customer plan — plans_catalogue entry
// ─────────────────────────────────────────────────────────────────────────────

class CustomerPlanCatalogueItem {
  final String id;
  final String name;
  final String slug;

  /// 'basic' | 'premium' | 'plus'
  final String planTier;

  final double price;

  /// 'monthly' | 'yearly'
  final String billingCycle;

  /// Maximum credit amount per billing cycle (ZAR).
  final double creditLimit;

  /// Free trial days (0 = no trial).
  final int trialDays;

  const CustomerPlanCatalogueItem({
    required this.id,
    required this.name,
    required this.slug,
    required this.planTier,
    required this.price,
    required this.billingCycle,
    required this.creditLimit,
    required this.trialDays,
  });

  factory CustomerPlanCatalogueItem.fromJson(Map<String, dynamic> json) {
    return CustomerPlanCatalogueItem(
      id: json['id']?.toString() ?? '',
      name: json['name'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      planTier: json['plan_tier'] as String? ?? '',
      price: double.parse((json['price'] ?? 0).toString()),
      billingCycle: json['billing_cycle'] as String? ?? 'monthly',
      creditLimit: double.parse((json['credit_limit'] ?? 0).toString()),
      trialDays: (json['trial_days'] as num?)?.toInt() ?? 0,
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Customer subscriptions summary
// ─────────────────────────────────────────────────────────────────────────────

class CustomerSubscriptionsSummary {
  /// All-time total subscriptions created.
  final int total;

  /// Currently active (status = 'active').
  final int active;

  /// Currently in free trial (status = 'trialing').
  final int trialing;

  /// Voluntarily cancelled (status = 'cancelled').
  final int cancelled;

  /// Expired without renewal (status = 'expired').
  final int expired;

  /// Payment overdue (status = 'past_due').
  final int pastDue;

  /// New subscriptions that started within the selected period.
  final int newThisPeriod;

  /// Cancellations that occurred within the selected period.
  final int cancellationsThisPeriod;

  /// Sum of plan prices for subscriptions that started this period.
  final double revenueThisPeriod;

  /// Estimated monthly recurring revenue from all currently active subscriptions.
  /// Yearly plans are divided by 12 for a comparable monthly figure.
  final double estimatedMrr;

  final List<SubscriptionStatusBreakdownItem> statusBreakdown;

  /// Active/trialing subscriber count per plan — used for plan popularity charts.
  final List<CustomerPlanBreakdown> planBreakdown;

  /// Full catalogue of all active plans (shown to admin for reference).
  final List<CustomerPlanCatalogueItem> plansCatalogue;

  const CustomerSubscriptionsSummary({
    required this.total,
    required this.active,
    required this.trialing,
    required this.cancelled,
    required this.expired,
    required this.pastDue,
    required this.newThisPeriod,
    required this.cancellationsThisPeriod,
    required this.revenueThisPeriod,
    required this.estimatedMrr,
    required this.statusBreakdown,
    required this.planBreakdown,
    required this.plansCatalogue,
  });

  factory CustomerSubscriptionsSummary.fromJson(Map<String, dynamic> json) {
    return CustomerSubscriptionsSummary(
      total: (json['total'] as num?)?.toInt() ?? 0,
      active: (json['active'] as num?)?.toInt() ?? 0,
      trialing: (json['trialing'] as num?)?.toInt() ?? 0,
      cancelled: (json['cancelled'] as num?)?.toInt() ?? 0,
      expired: (json['expired'] as num?)?.toInt() ?? 0,
      pastDue: (json['past_due'] as num?)?.toInt() ?? 0,
      newThisPeriod: (json['new_this_period'] as num?)?.toInt() ?? 0,
      cancellationsThisPeriod:
          (json['cancellations_this_period'] as num?)?.toInt() ?? 0,
      revenueThisPeriod:
          double.parse((json['revenue_this_period'] ?? 0).toString()),
      estimatedMrr: double.parse((json['estimated_mrr'] ?? 0).toString()),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => SubscriptionStatusBreakdownItem.fromJson(e))
          .toList(),
      planBreakdown: (json['plan_breakdown'] as List)
          .map((e) => CustomerPlanBreakdown.fromJson(e))
          .toList(),
      plansCatalogue: (json['plans_catalogue'] as List)
          .map((e) => CustomerPlanCatalogueItem.fromJson(e))
          .toList(),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Vendor tier — tier_breakdown entry
// ─────────────────────────────────────────────────────────────────────────────

class VendorTierBreakdown {
  /// UUID of the BusinessTier record.
  final String tierId;
  final String tierName;
  final String slug;

  /// Numeric level: 0 = free/starter, 1 = growth, 2 = pro, etc.
  final int tierLevel;

  /// Monthly price in ZAR (0 for the free/starter tier).
  final double price;

  /// Platform commission percentage for this tier.
  final double commissionRate;

  /// Number of vendors currently active/trialing on this tier.
  final int vendorCount;

  const VendorTierBreakdown({
    required this.tierId,
    required this.tierName,
    required this.slug,
    required this.tierLevel,
    required this.price,
    required this.commissionRate,
    required this.vendorCount,
  });

  factory VendorTierBreakdown.fromJson(Map<String, dynamic> json) {
    return VendorTierBreakdown(
      tierId: json['tier__id']?.toString() ?? '',
      tierName: json['tier__name'] as String? ?? '',
      slug: json['tier__slug'] as String? ?? '',
      tierLevel: (json['tier__tier_level'] as num?)?.toInt() ?? 0,
      price: double.parse((json['tier__price'] ?? 0).toString()),
      commissionRate:
          double.parse((json['tier__commission_rate'] ?? 0).toString()),
      vendorCount: (json['vendor_count'] as num?)?.toInt() ?? 0,
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Vendor tier — tiers_catalogue entry
// ─────────────────────────────────────────────────────────────────────────────

class VendorTierCatalogueItem {
  final String id;
  final String name;
  final String slug;
  final int tierLevel;
  final double price;
  final double commissionRate;

  /// Maximum products the vendor can list (0 = unlimited).
  final int maxProducts;

  /// Whether this tier includes access to the negotiation engine.
  final bool negotiationEnabled;

  final int trialDays;

  const VendorTierCatalogueItem({
    required this.id,
    required this.name,
    required this.slug,
    required this.tierLevel,
    required this.price,
    required this.commissionRate,
    required this.maxProducts,
    required this.negotiationEnabled,
    required this.trialDays,
  });

  factory VendorTierCatalogueItem.fromJson(Map<String, dynamic> json) {
    return VendorTierCatalogueItem(
      id: json['id']?.toString() ?? '',
      name: json['name'] as String? ?? '',
      slug: json['slug'] as String? ?? '',
      tierLevel: (json['tier_level'] as num?)?.toInt() ?? 0,
      price: double.parse((json['price'] ?? 0).toString()),
      commissionRate: double.parse((json['commission_rate'] ?? 0).toString()),
      maxProducts: (json['max_products'] as num?)?.toInt() ?? 0,
      negotiationEnabled: json['negotiation_enabled'] as bool? ?? false,
      trialDays: (json['trial_days'] as num?)?.toInt() ?? 0,
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Vendor tier subscriptions summary
// ─────────────────────────────────────────────────────────────────────────────

class VendorTierSubscriptionsSummary {
  final int total;
  final int active;
  final int trialing;
  final int cancelled;
  final int expired;
  final int pastDue;
  final int newThisPeriod;
  final int cancellationsThisPeriod;

  /// Sum of tier prices for subscriptions that started this period.
  final double revenueThisPeriod;

  /// Estimated monthly recurring revenue from all active vendor tier subscriptions.
  final double estimatedMrr;

  final List<SubscriptionStatusBreakdownItem> statusBreakdown;

  /// Active/trialing vendor count per tier — used for tier popularity charts.
  final List<VendorTierBreakdown> tierBreakdown;

  /// Full catalogue of all active tiers (shown to admin for reference).
  final List<VendorTierCatalogueItem> tiersCatalogue;

  const VendorTierSubscriptionsSummary({
    required this.total,
    required this.active,
    required this.trialing,
    required this.cancelled,
    required this.expired,
    required this.pastDue,
    required this.newThisPeriod,
    required this.cancellationsThisPeriod,
    required this.revenueThisPeriod,
    required this.estimatedMrr,
    required this.statusBreakdown,
    required this.tierBreakdown,
    required this.tiersCatalogue,
  });

  factory VendorTierSubscriptionsSummary.fromJson(Map<String, dynamic> json) {
    return VendorTierSubscriptionsSummary(
      total: (json['total'] as num?)?.toInt() ?? 0,
      active: (json['active'] as num?)?.toInt() ?? 0,
      trialing: (json['trialing'] as num?)?.toInt() ?? 0,
      cancelled: (json['cancelled'] as num?)?.toInt() ?? 0,
      expired: (json['expired'] as num?)?.toInt() ?? 0,
      pastDue: (json['past_due'] as num?)?.toInt() ?? 0,
      newThisPeriod: (json['new_this_period'] as num?)?.toInt() ?? 0,
      cancellationsThisPeriod:
          (json['cancellations_this_period'] as num?)?.toInt() ?? 0,
      revenueThisPeriod:
          double.parse((json['revenue_this_period'] ?? 0).toString()),
      estimatedMrr: double.parse((json['estimated_mrr'] ?? 0).toString()),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => SubscriptionStatusBreakdownItem.fromJson(e))
          .toList(),
      tierBreakdown: (json['tier_breakdown'] as List)
          .map((e) => VendorTierBreakdown.fromJson(e))
          .toList(),
      tiersCatalogue: (json['tiers_catalogue'] as List)
          .map((e) => VendorTierCatalogueItem.fromJson(e))
          .toList(),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Combined summary (both systems combined)
// ─────────────────────────────────────────────────────────────────────────────

class SubscriptionCombinedSummary {
  /// Active customer subscriptions + active vendor tier subscriptions.
  final int totalPayingSubscribers;

  /// Customer MRR + vendor tier MRR.
  final double combinedMrr;

  /// Customer revenue this period + vendor tier revenue this period.
  final double combinedRevenueThisPeriod;

  /// New customer subs + new vendor tier subs started this period.
  final int newThisPeriod;

  /// Customer cancellations + vendor tier cancellations this period.
  final int cancellationsThisPeriod;

  const SubscriptionCombinedSummary({
    required this.totalPayingSubscribers,
    required this.combinedMrr,
    required this.combinedRevenueThisPeriod,
    required this.newThisPeriod,
    required this.cancellationsThisPeriod,
  });

  factory SubscriptionCombinedSummary.fromJson(Map<String, dynamic> json) {
    return SubscriptionCombinedSummary(
      totalPayingSubscribers:
          (json['total_paying_subscribers'] as num?)?.toInt() ?? 0,
      combinedMrr: double.parse((json['combined_mrr'] ?? 0).toString()),
      combinedRevenueThisPeriod:
          double.parse((json['combined_revenue_this_period'] ?? 0).toString()),
      newThisPeriod: (json['new_this_period'] as num?)?.toInt() ?? 0,
      cancellationsThisPeriod:
          (json['cancellations_this_period'] as num?)?.toInt() ?? 0,
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Top-level response
// ─────────────────────────────────────────────────────────────────────────────

class AdminSubscriptionAnalyticsResult {
  final AnalyticsPeriod period;
  final CustomerSubscriptionsSummary customerSubscriptions;
  final VendorTierSubscriptionsSummary vendorTierSubscriptions;
  final SubscriptionCombinedSummary combined;

  /// AI-generated notes derived from the metrics.
  /// Each string starts with an emoji.
  final List<String> insights;

  const AdminSubscriptionAnalyticsResult({
    required this.period,
    required this.customerSubscriptions,
    required this.vendorTierSubscriptions,
    required this.combined,
    required this.insights,
  });

  factory AdminSubscriptionAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return AdminSubscriptionAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      customerSubscriptions:
          CustomerSubscriptionsSummary.fromJson(json['customer_subscriptions']),
      vendorTierSubscriptions:
          VendorTierSubscriptionsSummary.fromJson(json['vendor_tier_subscriptions']),
      combined: SubscriptionCombinedSummary.fromJson(json['combined']),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}
```

---

## Service Class

```dart
class AdminSubscriptionAnalyticsService {
  final String baseUrl;
  final String Function() getToken;

  const AdminSubscriptionAnalyticsService({
    required this.baseUrl,
    required this.getToken,
  });

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${getToken()}',
      };

  Uri _uri([Map<String, String>? params]) {
    final uri = Uri.parse(
        '$baseUrl/api/platform-admin/analytics/subscriptions/');
    return params != null ? uri.replace(queryParameters: params) : uri;
  }

  // ── Fetch subscription analytics ─────────────────────────────────────────

  /// [period]  'today' | 'week' | 'month' (default) | 'year'
  /// [from]    Custom start date, e.g. '2026-01-01'
  /// [to]      Custom end date,   e.g. '2026-03-31'
  /// When [from] + [to] are both provided they override [period].
  Future<AdminSubscriptionAnalyticsResult> get({
    String? period,
    String? from,
    String? to,
  }) async {
    final params = <String, String>{};
    if (period != null) params['period'] = period;
    if (from != null) params['from'] = from;
    if (to != null) params['to'] = to;

    final response = await http.get(
      _uri(params.isNotEmpty ? params : null),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return AdminSubscriptionAnalyticsResult.fromJson(
          jsonDecode(response.body));
    }
    throw Exception(
        'Failed to fetch subscription analytics: ${response.body}');
  }
}
```

---

## Endpoint Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/platform-admin/analytics/subscriptions/` | Admin | Full subscription analytics for both customers and vendors |

---

## Response Body

```json
{
  "period": {
    "start": "2026-04-23T00:00:00Z",
    "end":   "2026-05-23T00:00:00Z"
  },

  "customer_subscriptions": {
    "total": 420,
    "active": 380,
    "trialing": 15,
    "cancelled": 18,
    "expired": 5,
    "past_due": 2,
    "new_this_period": 34,
    "cancellations_this_period": 6,
    "revenue_this_period": "5100.00",
    "estimated_mrr": "9500.00",

    "status_breakdown": [
      { "status": "active",    "count": 380 },
      { "status": "trialing",  "count": 15  },
      { "status": "cancelled", "count": 18  },
      { "status": "expired",   "count": 5   },
      { "status": "past_due",  "count": 2   }
    ],

    "plan_breakdown": [
      {
        "plan__id":            "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "plan__name":          "Premium",
        "plan__slug":          "premium",
        "plan__plan_tier":     "premium",
        "plan__price":         "149.00",
        "plan__billing_cycle": "monthly",
        "subscriber_count":    210
      },
      {
        "plan__id":            "4ab12c74-1234-4562-b3fc-9d874f55bfa7",
        "plan__name":          "Basic",
        "plan__slug":          "basic",
        "plan__plan_tier":     "basic",
        "plan__price":         "49.00",
        "plan__billing_cycle": "monthly",
        "subscriber_count":    170
      }
    ],

    "plans_catalogue": [
      {
        "id":            "4ab12c74-1234-4562-b3fc-9d874f55bfa7",
        "name":          "Basic",
        "slug":          "basic",
        "plan_tier":     "basic",
        "price":         "49.00",
        "billing_cycle": "monthly",
        "credit_limit":  "500.00",
        "trial_days":    7
      },
      {
        "id":            "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "name":          "Premium",
        "slug":          "premium",
        "plan_tier":     "premium",
        "price":         "149.00",
        "billing_cycle": "monthly",
        "credit_limit":  "2000.00",
        "trial_days":    14
      },
      {
        "id":            "8cd34e91-8888-4562-b3fc-7e123a99cde5",
        "name":          "Plus",
        "slug":          "plus",
        "plan_tier":     "plus",
        "price":         "299.00",
        "billing_cycle": "yearly",
        "credit_limit":  "5000.00",
        "trial_days":    30
      }
    ]
  },

  "vendor_tier_subscriptions": {
    "total": 112,
    "active": 98,
    "trialing": 4,
    "cancelled": 7,
    "expired": 2,
    "past_due": 1,
    "new_this_period": 9,
    "cancellations_this_period": 2,
    "revenue_this_period": "8820.00",
    "estimated_mrr": "42000.00",

    "status_breakdown": [
      { "status": "active",    "count": 98 },
      { "status": "trialing",  "count": 4  },
      { "status": "cancelled", "count": 7  },
      { "status": "expired",   "count": 2  },
      { "status": "past_due",  "count": 1  }
    ],

    "tier_breakdown": [
      {
        "tier__id":              "aabb1234-0000-4562-b3fc-cc123456def0",
        "tier__name":            "Growth",
        "tier__slug":            "growth",
        "tier__tier_level":      1,
        "tier__price":           "299.00",
        "tier__commission_rate": "10.00",
        "vendor_count":          60
      },
      {
        "tier__id":              "bbcc5678-1111-4562-b3fc-dd234567ef01",
        "tier__name":            "Pro",
        "tier__slug":            "pro",
        "tier__tier_level":      2,
        "tier__price":           "599.00",
        "tier__commission_rate": "8.00",
        "vendor_count":          38
      }
    ],

    "tiers_catalogue": [
      {
        "id":                  "zz001122-ffff-4562-b3fc-ee000000aa00",
        "name":                "Starter",
        "slug":                "starter",
        "tier_level":          0,
        "price":               "0.00",
        "commission_rate":     "12.00",
        "max_products":        20,
        "negotiation_enabled": false,
        "trial_days":          0
      },
      {
        "id":                  "aabb1234-0000-4562-b3fc-cc123456def0",
        "name":                "Growth",
        "slug":                "growth",
        "tier_level":          1,
        "price":               "299.00",
        "commission_rate":     "10.00",
        "max_products":        100,
        "negotiation_enabled": true,
        "trial_days":          14
      },
      {
        "id":                  "bbcc5678-1111-4562-b3fc-dd234567ef01",
        "name":                "Pro",
        "slug":                "pro",
        "tier_level":          2,
        "price":               "599.00",
        "commission_rate":     "8.00",
        "max_products":        0,
        "negotiation_enabled": true,
        "trial_days":          30
      }
    ]
  },

  "combined": {
    "total_paying_subscribers":      478,
    "combined_mrr":                  "51500.00",
    "combined_revenue_this_period":  "13920.00",
    "new_this_period":               43,
    "cancellations_this_period":     8
  },

  "insights": [
    "💰 Combined estimated MRR is R51,500.00 across customer and vendor subscriptions.",
    "👥 380 customers are on active credit plans.",
    "🏪 98 vendors are on paid business tiers.",
    "🆕 43 new subscriptions started this period.",
    "🆓 15 customers are currently on a free trial. Convert them with targeted in-app messaging."
  ]
}
```

---

## Field Reference

### `customer_subscriptions`

| Field | Type | Description |
|-------|------|-------------|
| `total` | int | All-time total subscriptions ever created |
| `active` | int | Currently active (status = `active`) |
| `trialing` | int | Currently in free trial (status = `trialing`) |
| `cancelled` | int | Voluntarily cancelled by the customer |
| `expired` | int | Expired without renewal |
| `past_due` | int | Payment failed — subscription suspended |
| `new_this_period` | int | Subscriptions that started within the query period |
| `cancellations_this_period` | int | Cancellations that occurred within the query period |
| `revenue_this_period` | decimal string | Sum of plan prices for subscriptions started this period |
| `estimated_mrr` | decimal string | Monthly recurring revenue from all active subs (yearly plans ÷ 12) |
| `status_breakdown` | array | Count per status value |
| `plan_breakdown` | array | Active + trialing subscriber count per plan |
| `plans_catalogue` | array | Full list of all active plans with credit terms |

### `vendor_tier_subscriptions`

| Field | Type | Description |
|-------|------|-------------|
| `total` | int | All-time total vendor tier subscriptions |
| `active` | int | Currently active |
| `trialing` | int | Currently on trial |
| `cancelled` | int | Cancelled |
| `expired` | int | Expired |
| `past_due` | int | Payment overdue |
| `new_this_period` | int | New vendor tier subscriptions started this period |
| `cancellations_this_period` | int | Cancellations this period |
| `revenue_this_period` | decimal string | Sum of tier prices for subs started this period |
| `estimated_mrr` | decimal string | MRR from all active vendor tier subscriptions |
| `status_breakdown` | array | Count per status value |
| `tier_breakdown` | array | Active + trialing vendor count per tier |
| `tiers_catalogue` | array | Full list of all active tiers with limits and features |

### `combined`

| Field | Type | Description |
|-------|------|-------------|
| `total_paying_subscribers` | int | Active customer subs + active vendor tier subs |
| `combined_mrr` | decimal string | Customer MRR + vendor MRR |
| `combined_revenue_this_period` | decimal string | Customer revenue + vendor revenue this period |
| `new_this_period` | int | Total new subs across both systems |
| `cancellations_this_period` | int | Total cancellations across both systems |

### `insights`

Array of strings. Each entry is an AI-generated note prefixed with an emoji.  
Returns `[]` if there is no data to comment on.

| Trigger condition | Example note |
|---|---|
| MRR > 0 | `"💰 Combined estimated MRR is R51,500.00 across customer and vendor subscriptions."` |
| Active customer subs > 0 | `"👥 380 customers are on active credit plans."` |
| Active vendor subs > 0 | `"🏪 98 vendors are on paid business tiers."` |
| Customer churn > 10% | `"⚠️ 6 customer subscription cancellations this period (10.3% churn). Investigate reasons and improve retention."` |
| Vendor churn > 10% | `"⚠️ 2 vendor tier cancellations this period (12.5% churn). Review tier value proposition."` |
| Any `past_due` customers | `"🔴 2 customer subscriptions are past due. Trigger payment retries via Paystack."` |
| Any `past_due` vendors | `"🔴 1 vendor tier subscription is past due. Retry charges or risk losing their active tier benefits."` |
| Trialing > 0 | `"🆓 15 customers are currently on a free trial. Convert them with targeted in-app messaging."` |
| New subs > 0 | `"🆕 43 new subscriptions started this period."` |

---

## Subscription Status Values

| Status | Meaning |
|--------|---------|
| `active` | Fully paid and in good standing |
| `trialing` | In free trial period — will auto-convert or expire |
| `cancelled` | Voluntarily cancelled; access continues until end of billing period |
| `expired` | Billing period ended without renewal |
| `past_due` | Most recent payment failed; Paystack will retry |

---

## Customer Plan Tiers

| `plan_tier` | Credit limit range | Typical price |
|---|---|---|
| `basic` | R 500 | R 49/month |
| `premium` | R 2 000 | R 149/month |
| `plus` | R 5 000 | R 299/year |

---

## Vendor Business Tier Levels

| `tier_level` | Name | Price | Commission | Negotiation |
|---|---|---|---|---|
| `0` | Starter | Free | 12% | ✗ |
| `1` | Growth | R 299/month | 10% | ✓ |
| `2` | Pro | R 599/month | 8% | ✓ |

---

## Error Responses

| Status | Body | Cause |
|--------|------|-------|
| `401` | `{"detail": "Authentication credentials were not provided."}` | Missing or expired token |
| `403` | `{"detail": "Forbidden."}` | Token does not belong to a platform admin |
