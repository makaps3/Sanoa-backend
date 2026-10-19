# Vendor Analytics — Dart Service Reference

Base path: `/api/business/analytics/<vendor_id>/`  
All requests require `Authorization: Bearer <access_token>`.

**Access rules:**
- A **vendor** can only request their own `vendor_id`.
- A **platform admin** can request any `vendor_id`.
- Any other UUID returns `403 Forbidden`.

---

## Table of Contents

- [Query Parameters](#query-parameters)
- [Dart Models](#dart-models)
- [Service Class](#service-class)
- [Endpoint Reference](#endpoint-reference)
- [Response Bodies](#response-bodies)
- [Error Responses](#error-responses)

---

## Query Parameters

All 8 endpoints accept the same period filters:

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `period` | string | `?period=month` | `today` · `week` · `month` (default) · `year` |
| `from` | ISO date | `?from=2026-01-01` | Custom range start (UTC) |
| `to` | ISO date | `?to=2026-03-31` | Custom range end (UTC) |

When `from` + `to` are both provided they override `period`.

---

## Dart Models

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;


// ─────────────────────────────────────────────────────────────────────────────
// Shared
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

/// AI-generated notes included in every response.
/// Each string is prefixed with an emoji.
typedef AnalyticsInsights = List<String>;

class BreakdownItem {
  final String label;
  final int count;
  final double? total;

  const BreakdownItem({required this.label, required this.count, this.total});

  factory BreakdownItem.fromJson(Map<String, dynamic> json) {
    final labelValue =
        json.values.firstWhere((v) => v is String, orElse: () => '').toString();
    return BreakdownItem(
      label: labelValue,
      count: (json['count'] as num?)?.toInt() ?? 0,
      total: json['total'] != null
          ? double.parse(json['total'].toString())
          : null,
    );
  }
}

class DailyPoint {
  final String day;
  final int count;
  final double? revenue;

  const DailyPoint({required this.day, required this.count, this.revenue});

  factory DailyPoint.fromJson(Map<String, dynamic> json) {
    return DailyPoint(
      day: json['day'] as String,
      count: (json['count'] as num?)?.toInt() ?? 0,
      revenue: json['revenue'] != null
          ? double.parse(json['revenue'].toString())
          : null,
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Overview
// ─────────────────────────────────────────────────────────────────────────────

class VendorMlScore {
  final double score;

  /// 'bronze' | 'silver' | 'gold' | 'platinum'
  final String tier;

  final DateTime scoredAt;

  const VendorMlScore({
    required this.score,
    required this.tier,
    required this.scoredAt,
  });

  factory VendorMlScore.fromJson(Map<String, dynamic> json) {
    return VendorMlScore(
      score: double.parse(json['score'].toString()),
      tier: json['tier'] as String,
      scoredAt: DateTime.parse(json['scored_at'] as String),
    );
  }
}

class VendorOverviewResult {
  final AnalyticsPeriod period;
  final String vendorId;
  final String vendorName;
  final Map<String, dynamic> revenue;

  /// total, completed, cancelled, pending
  final Map<String, int> orders;

  final int uniqueCustomers;
  final VendorMlScore? performanceScore;
  final AnalyticsInsights insights;

  const VendorOverviewResult({
    required this.period,
    required this.vendorId,
    required this.vendorName,
    required this.revenue,
    required this.orders,
    required this.uniqueCustomers,
    this.performanceScore,
    required this.insights,
  });

  factory VendorOverviewResult.fromJson(Map<String, dynamic> json) {
    final rev = json['revenue'] as Map<String, dynamic>;
    final ord = json['orders'] as Map<String, dynamic>;
    return VendorOverviewResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      vendorId: json['vendor_id'] as String,
      vendorName: json['vendor_name'] as String? ?? '',
      revenue: {
        'total': double.parse((rev['total'] ?? 0).toString()),
        'previous_period':
            double.parse((rev['previous_period'] ?? 0).toString()),
        'growth_percent': rev['growth_percent'] != null
            ? double.parse(rev['growth_percent'].toString())
            : null,
      },
      orders: {
        'total': ord['total'] as int,
        'completed': ord['completed'] as int,
        'cancelled': ord['cancelled'] as int,
        'pending': ord['pending'] as int,
      },
      uniqueCustomers: json['unique_customers'] as int,
      performanceScore: json['performance_score'] != null
          ? VendorMlScore.fromJson(json['performance_score'])
          : null,
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Orders
// ─────────────────────────────────────────────────────────────────────────────

class VendorOrderTotals {
  final int totalOrders;
  final double totalRevenue;
  final double avgOrderValue;
  final int completed;
  final int cancelled;
  final int refunded;

  const VendorOrderTotals({
    required this.totalOrders,
    required this.totalRevenue,
    required this.avgOrderValue,
    required this.completed,
    required this.cancelled,
    required this.refunded,
  });

  factory VendorOrderTotals.fromJson(Map<String, dynamic> json) {
    return VendorOrderTotals(
      totalOrders: json['total_orders'] as int,
      totalRevenue: double.parse((json['total_revenue'] ?? 0).toString()),
      avgOrderValue: double.parse((json['avg_order_value'] ?? 0).toString()),
      completed: json['completed'] as int,
      cancelled: json['cancelled'] as int,
      refunded: json['refunded'] as int,
    );
  }
}

class VendorOrderAnalyticsResult {
  final AnalyticsPeriod period;
  final String vendorId;
  final String vendorName;
  final VendorOrderTotals totals;
  final List<BreakdownItem> statusBreakdown;
  final List<BreakdownItem> fulfillmentSplit;
  final List<DailyPoint> dailyBreakdown;
  final AnalyticsInsights insights;

  const VendorOrderAnalyticsResult({
    required this.period,
    required this.vendorId,
    required this.vendorName,
    required this.totals,
    required this.statusBreakdown,
    required this.fulfillmentSplit,
    required this.dailyBreakdown,
    required this.insights,
  });

  factory VendorOrderAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorOrderAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      vendorId: json['vendor_id'] as String,
      vendorName: json['vendor_name'] as String? ?? '',
      totals: VendorOrderTotals.fromJson(json['totals']),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      fulfillmentSplit: (json['fulfillment_split'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      dailyBreakdown: (json['daily_breakdown'] as List)
          .map((e) => DailyPoint.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Products
// ─────────────────────────────────────────────────────────────────────────────

class VendorTopSellingProduct {
  final int productId;
  final String productName;
  final int unitsSold;
  final double revenue;
  final int orders;

  const VendorTopSellingProduct({
    required this.productId,
    required this.productName,
    required this.unitsSold,
    required this.revenue,
    required this.orders,
  });

  factory VendorTopSellingProduct.fromJson(Map<String, dynamic> json) {
    return VendorTopSellingProduct(
      productId: (json['product_id'] as num?)?.toInt() ?? 0,
      productName: json['product_name'] as String? ?? '',
      unitsSold: (json['units_sold'] as num?)?.toInt() ?? 0,
      revenue: double.parse((json['revenue'] ?? 0).toString()),
      orders: (json['orders'] as num?)?.toInt() ?? 0,
    );
  }
}

class VendorSlowMovingProduct {
  final int id;
  final String name;
  final double price;

  const VendorSlowMovingProduct({
    required this.id,
    required this.name,
    required this.price,
  });

  factory VendorSlowMovingProduct.fromJson(Map<String, dynamic> json) {
    return VendorSlowMovingProduct(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: json['name'] as String? ?? '',
      price: double.parse((json['price'] ?? 0).toString()),
    );
  }
}

class VendorProductAnalyticsResult {
  final AnalyticsPeriod period;
  final String vendorId;
  final Map<String, dynamic> totals;
  final List<BreakdownItem> statusBreakdown;
  final List<VendorTopSellingProduct> topSelling;
  final List<VendorSlowMovingProduct> slowMoving;
  final AnalyticsInsights insights;

  const VendorProductAnalyticsResult({
    required this.period,
    required this.vendorId,
    required this.totals,
    required this.statusBreakdown,
    required this.topSelling,
    required this.slowMoving,
    required this.insights,
  });

  factory VendorProductAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorProductAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      vendorId: json['vendor_id'] as String,
      totals: Map<String, dynamic>.from(json['totals']),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      topSelling: (json['top_selling'] as List)
          .map((e) => VendorTopSellingProduct.fromJson(e))
          .toList(),
      slowMoving: (json['slow_moving'] as List)
          .map((e) => VendorSlowMovingProduct.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Categories
// ─────────────────────────────────────────────────────────────────────────────

class VendorCategoryProductStat {
  final int categoryId;
  final String categoryName;
  final String categorySlug;

  /// Total products (all statuses) this vendor has in this category.
  final int totalProducts;

  /// Products with status = 'active'.
  final int activeProducts;

  final double avgPrice;

  const VendorCategoryProductStat({
    required this.categoryId,
    required this.categoryName,
    required this.categorySlug,
    required this.totalProducts,
    required this.activeProducts,
    required this.avgPrice,
  });

  factory VendorCategoryProductStat.fromJson(Map<String, dynamic> json) {
    return VendorCategoryProductStat(
      categoryId: (json['category_id'] as num?)?.toInt() ?? 0,
      categoryName: json['category_name'] as String? ?? '',
      categorySlug: json['category_slug'] as String? ?? '',
      totalProducts: (json['total_products'] as num?)?.toInt() ?? 0,
      activeProducts: (json['active_products'] as num?)?.toInt() ?? 0,
      avgPrice: double.parse((json['avg_price'] ?? 0).toString()),
    );
  }
}

class VendorCategoryRevenueStat {
  final int categoryId;
  final String categoryName;
  final double revenue;
  final int unitsSold;

  /// Distinct paid orders that contained items from this category.
  final int orderCount;

  const VendorCategoryRevenueStat({
    required this.categoryId,
    required this.categoryName,
    required this.revenue,
    required this.unitsSold,
    required this.orderCount,
  });

  factory VendorCategoryRevenueStat.fromJson(Map<String, dynamic> json) {
    return VendorCategoryRevenueStat(
      categoryId: (json['category_id'] as num?)?.toInt() ?? 0,
      categoryName: json['category_name'] as String? ?? '',
      revenue: double.parse((json['revenue'] ?? 0).toString()),
      unitsSold: (json['units_sold'] as num?)?.toInt() ?? 0,
      orderCount: (json['order_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class VendorCategoryTotals {
  /// Categories the vendor has at least one product in (any status).
  final int totalCategoriesWithProducts;

  /// Categories that have at least one active product.
  final int totalActiveCategories;

  /// Categories that generated revenue in the selected period.
  final int totalCategoriesWithRevenue;

  const VendorCategoryTotals({
    required this.totalCategoriesWithProducts,
    required this.totalActiveCategories,
    required this.totalCategoriesWithRevenue,
  });

  factory VendorCategoryTotals.fromJson(Map<String, dynamic> json) {
    return VendorCategoryTotals(
      totalCategoriesWithProducts:
          (json['total_categories_with_products'] as num?)?.toInt() ?? 0,
      totalActiveCategories:
          (json['total_active_categories'] as num?)?.toInt() ?? 0,
      totalCategoriesWithRevenue:
          (json['total_categories_with_revenue'] as num?)?.toInt() ?? 0,
    );
  }
}

class VendorCategoryAnalyticsResult {
  final AnalyticsPeriod period;
  final String vendorId;
  final String vendorName;
  final VendorCategoryTotals totals;

  /// Products per category — current snapshot, no time window.
  final List<VendorCategoryProductStat> productsPerCategory;

  /// Revenue + sales per category — paid orders within the selected period.
  final List<VendorCategoryRevenueStat> revenuePerCategory;

  /// Name of the highest-revenue category this period. Null if no sales.
  final String? topCategory;

  final AnalyticsInsights insights;

  const VendorCategoryAnalyticsResult({
    required this.period,
    required this.vendorId,
    required this.vendorName,
    required this.totals,
    required this.productsPerCategory,
    required this.revenuePerCategory,
    this.topCategory,
    required this.insights,
  });

  factory VendorCategoryAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorCategoryAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      vendorId: json['vendor_id'] as String,
      vendorName: json['vendor_name'] as String? ?? '',
      totals: VendorCategoryTotals.fromJson(json['totals']),
      productsPerCategory: (json['products_per_category'] as List)
          .map((e) => VendorCategoryProductStat.fromJson(e))
          .toList(),
      revenuePerCategory: (json['revenue_per_category'] as List)
          .map((e) => VendorCategoryRevenueStat.fromJson(e))
          .toList(),
      topCategory: json['top_category'] as String?,
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Customers
// ─────────────────────────────────────────────────────────────────────────────

class VendorRepeatCustomer {
  final String email;
  final int userId;
  final int orderCount;
  final double totalSpend;

  const VendorRepeatCustomer({
    required this.email,
    required this.userId,
    required this.orderCount,
    required this.totalSpend,
  });

  factory VendorRepeatCustomer.fromJson(Map<String, dynamic> json) {
    return VendorRepeatCustomer(
      email: json['user__email'] as String? ?? '',
      userId: (json['user_id'] as num?)?.toInt() ?? 0,
      orderCount: (json['order_count'] as num?)?.toInt() ?? 0,
      totalSpend: double.parse((json['total_spend'] ?? 0).toString()),
    );
  }
}

class VendorCustomerAnalyticsResult {
  final AnalyticsPeriod period;
  final String vendorId;
  final String vendorName;
  final int uniqueCustomers;
  final int newCustomers;
  final int repeatCustomers;
  final double avgCustomerLifetimeValue;
  final List<VendorRepeatCustomer> topRepeatCustomers;
  final AnalyticsInsights insights;

  const VendorCustomerAnalyticsResult({
    required this.period,
    required this.vendorId,
    required this.vendorName,
    required this.uniqueCustomers,
    required this.newCustomers,
    required this.repeatCustomers,
    required this.avgCustomerLifetimeValue,
    required this.topRepeatCustomers,
    required this.insights,
  });

  factory VendorCustomerAnalyticsResult.fromJson(Map<String, dynamic> json) {
    final t = json['totals'] as Map<String, dynamic>;
    return VendorCustomerAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      vendorId: json['vendor_id'] as String,
      vendorName: json['vendor_name'] as String? ?? '',
      uniqueCustomers: t['unique_customers'] as int,
      newCustomers: t['new_customers'] as int,
      repeatCustomers: t['repeat_customers'] as int,
      avgCustomerLifetimeValue:
          double.parse((t['avg_customer_lifetime_value'] ?? 0).toString()),
      topRepeatCustomers: (json['top_repeat_customers'] as List)
          .map((e) => VendorRepeatCustomer.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Negotiations
// ─────────────────────────────────────────────────────────────────────────────

class VendorNegotiationTotals {
  final int total;
  final int agreed;
  final int expired;
  final int open;
  final double agreementRatePercent;

  const VendorNegotiationTotals({
    required this.total,
    required this.agreed,
    required this.expired,
    required this.open,
    required this.agreementRatePercent,
  });

  factory VendorNegotiationTotals.fromJson(Map<String, dynamic> json) {
    return VendorNegotiationTotals(
      total: json['total'] as int,
      agreed: json['agreed'] as int,
      expired: json['expired'] as int,
      open: json['open'] as int,
      agreementRatePercent:
          double.parse(json['agreement_rate_percent'].toString()),
    );
  }
}

class VendorNegotiationAnalyticsResult {
  final AnalyticsPeriod period;
  final String vendorId;
  final VendorNegotiationTotals totals;
  final double agreedRevenue;
  final double avgRoundsToAgreement;
  final List<BreakdownItem> statusBreakdown;
  final List<BreakdownItem> modeBreakdown;
  final AnalyticsInsights insights;

  const VendorNegotiationAnalyticsResult({
    required this.period,
    required this.vendorId,
    required this.totals,
    required this.agreedRevenue,
    required this.avgRoundsToAgreement,
    required this.statusBreakdown,
    required this.modeBreakdown,
    required this.insights,
  });

  factory VendorNegotiationAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorNegotiationAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      vendorId: json['vendor_id'] as String,
      totals: VendorNegotiationTotals.fromJson(json['totals']),
      agreedRevenue:
          double.parse((json['agreed_revenue'] ?? 0).toString()),
      avgRoundsToAgreement:
          double.parse((json['avg_rounds_to_agreement'] ?? 0).toString()),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      modeBreakdown: (json['mode_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Payments
// ─────────────────────────────────────────────────────────────────────────────

class VendorTransactionSummary {
  final int total;
  final int successful;
  final double successRatePercent;
  final double totalRevenue;
  final double paystackFees;
  final double netRevenue;

  const VendorTransactionSummary({
    required this.total,
    required this.successful,
    required this.successRatePercent,
    required this.totalRevenue,
    required this.paystackFees,
    required this.netRevenue,
  });

  factory VendorTransactionSummary.fromJson(Map<String, dynamic> json) {
    return VendorTransactionSummary(
      total: json['total'] as int,
      successful: json['successful'] as int,
      successRatePercent:
          double.parse(json['success_rate_percent'].toString()),
      totalRevenue: double.parse((json['total_revenue'] ?? 0).toString()),
      paystackFees: double.parse((json['paystack_fees'] ?? 0).toString()),
      netRevenue: double.parse((json['net_revenue'] ?? 0).toString()),
    );
  }
}

class VendorPaymentAnalyticsResult {
  final AnalyticsPeriod period;
  final String vendorId;
  final String vendorName;
  final VendorTransactionSummary transactions;
  final Map<String, dynamic> refunds;
  final List<BreakdownItem> byStatus;
  final List<BreakdownItem> byChannel;
  final AnalyticsInsights insights;

  const VendorPaymentAnalyticsResult({
    required this.period,
    required this.vendorId,
    required this.vendorName,
    required this.transactions,
    required this.refunds,
    required this.byStatus,
    required this.byChannel,
    required this.insights,
  });

  factory VendorPaymentAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorPaymentAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      vendorId: json['vendor_id'] as String,
      vendorName: json['vendor_name'] as String? ?? '',
      transactions: VendorTransactionSummary.fromJson(json['transactions']),
      refunds: Map<String, dynamic>.from(json['refunds']),
      byStatus: (json['by_status'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      byChannel: (json['by_channel'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Subscription / Tier
// ─────────────────────────────────────────────────────────────────────────────

class VendorTierDetails {
  final String id;
  final String name;
  final String slug;

  /// 0 = starter/free, 1 = growth, 2 = pro, etc.
  final int tierLevel;

  /// Monthly price in ZAR (0 for the free tier).
  final double price;

  /// Platform commission percentage deducted on each sale.
  final double commissionRate;

  /// How much commission the vendor saves vs the default 12% rate.
  final double commissionSavingVsDefault;

  /// Maximum number of active product listings (0 = unlimited).
  final int maxProducts;

  final bool negotiationEnabled;
  final double maxMarkupPercent;
  final double maxDiscountPercent;
  final bool featuredListings;
  final double searchPriorityBoost;
  final int trialDays;
  final List<String> features;

  const VendorTierDetails({
    required this.id,
    required this.name,
    required this.slug,
    required this.tierLevel,
    required this.price,
    required this.commissionRate,
    required this.commissionSavingVsDefault,
    required this.maxProducts,
    required this.negotiationEnabled,
    required this.maxMarkupPercent,
    required this.maxDiscountPercent,
    required this.featuredListings,
    required this.searchPriorityBoost,
    required this.trialDays,
    required this.features,
  });

  factory VendorTierDetails.fromJson(Map<String, dynamic> json) {
    return VendorTierDetails(
      id: json['id']?.toString() ?? '',
      name: json['name'] as String,
      slug: json['slug'] as String,
      tierLevel: (json['tier_level'] as num?)?.toInt() ?? 0,
      price: double.parse((json['price'] ?? 0).toString()),
      commissionRate: double.parse((json['commission_rate'] ?? 0).toString()),
      commissionSavingVsDefault: double.parse(
          (json['commission_saving_vs_default'] ?? 0).toString()),
      maxProducts: (json['max_products'] as num?)?.toInt() ?? 0,
      negotiationEnabled: json['negotiation_enabled'] as bool? ?? false,
      maxMarkupPercent:
          double.parse((json['max_markup_percent'] ?? 0).toString()),
      maxDiscountPercent:
          double.parse((json['max_discount_percent'] ?? 0).toString()),
      featuredListings: json['featured_listings'] as bool? ?? false,
      searchPriorityBoost:
          double.parse((json['search_priority_boost'] ?? 0).toString()),
      trialDays: (json['trial_days'] as num?)?.toInt() ?? 0,
      features: List<String>.from(json['features'] ?? []),
    );
  }

  bool get isFreeTier => price == 0;
  bool get hasUnlimitedProducts => maxProducts == 0;
}

class VendorSubscriptionDetails {
  final String id;

  /// 'active' | 'trialing' | 'cancelled' | 'expired' | 'past_due'
  final String status;

  final DateTime startedAt;
  final DateTime currentPeriodStart;
  final DateTime currentPeriodEnd;
  final DateTime? cancelledAt;

  /// Calendar days left in the current billing period. 0 if expired.
  final int? daysRemaining;

  final bool isActive;

  const VendorSubscriptionDetails({
    required this.id,
    required this.status,
    required this.startedAt,
    required this.currentPeriodStart,
    required this.currentPeriodEnd,
    this.cancelledAt,
    this.daysRemaining,
    required this.isActive,
  });

  factory VendorSubscriptionDetails.fromJson(Map<String, dynamic> json) {
    return VendorSubscriptionDetails(
      id: json['id']?.toString() ?? '',
      status: json['status'] as String,
      startedAt: DateTime.parse(json['started_at'] as String),
      currentPeriodStart:
          DateTime.parse(json['current_period_start'] as String),
      currentPeriodEnd: DateTime.parse(json['current_period_end'] as String),
      cancelledAt: json['cancelled_at'] != null
          ? DateTime.parse(json['cancelled_at'] as String)
          : null,
      daysRemaining: (json['days_remaining'] as num?)?.toInt(),
      isActive: json['is_active'] as bool? ?? false,
    );
  }
}

class VendorProductUsage {
  final int activeProducts;

  /// An int (hard limit) or the string 'unlimited'.
  final dynamic limit;

  /// null when limit is unlimited.
  final double? usagePercent;

  const VendorProductUsage({
    required this.activeProducts,
    required this.limit,
    this.usagePercent,
  });

  bool get isUnlimited => limit == 'unlimited';

  factory VendorProductUsage.fromJson(Map<String, dynamic> json) {
    return VendorProductUsage(
      activeProducts: (json['active_products'] as num?)?.toInt() ?? 0,
      limit: json['limit'],
      usagePercent: json['usage_percent'] != null
          ? double.parse(json['usage_percent'].toString())
          : null,
    );
  }
}

class VendorSubscriptionAnalyticsResult {
  final String vendorId;

  /// null if the vendor has no tier subscription at all.
  final VendorSubscriptionDetails? subscription;

  /// null if the vendor has no tier subscription at all.
  final VendorTierDetails? tier;

  final VendorProductUsage? productUsage;
  final AnalyticsInsights insights;

  const VendorSubscriptionAnalyticsResult({
    required this.vendorId,
    this.subscription,
    this.tier,
    this.productUsage,
    required this.insights,
  });

  factory VendorSubscriptionAnalyticsResult.fromJson(
      Map<String, dynamic> json) {
    return VendorSubscriptionAnalyticsResult(
      vendorId: json['vendor_id'] as String,
      subscription: json['subscription'] != null
          ? VendorSubscriptionDetails.fromJson(json['subscription'])
          : null,
      tier: json['tier'] != null
          ? VendorTierDetails.fromJson(json['tier'])
          : null,
      productUsage: json['product_usage'] != null
          ? VendorProductUsage.fromJson(json['product_usage'])
          : null,
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}
```

---

## Service Class

```dart
class VendorAnalyticsService {
  final String baseUrl;
  final String Function() getToken;

  const VendorAnalyticsService({
    required this.baseUrl,
    required this.getToken,
  });

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${getToken()}',
      };

  Uri _uri(String vendorId, String endpoint,
      [Map<String, String>? params]) {
    final uri = Uri.parse(
        '$baseUrl/api/business/analytics/$vendorId/$endpoint');
    return params != null ? uri.replace(queryParameters: params) : uri;
  }

  Map<String, String> _periodParams({
    String? period,
    String? from,
    String? to,
  }) {
    final p = <String, String>{};
    if (period != null) p['period'] = period;
    if (from != null) p['from'] = from;
    if (to != null) p['to'] = to;
    return p;
  }

  // ── Overview ────────────────────────────────────────────────────────────────

  Future<VendorOverviewResult> getOverview(
    String vendorId, {
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri(vendorId, 'overview/',
          _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorOverviewResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getOverview failed: ${res.body}');
  }

  // ── Orders ──────────────────────────────────────────────────────────────────

  Future<VendorOrderAnalyticsResult> getOrderAnalytics(
    String vendorId, {
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri(vendorId, 'orders/',
          _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorOrderAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getOrderAnalytics failed: ${res.body}');
  }

  // ── Products ────────────────────────────────────────────────────────────────

  Future<VendorProductAnalyticsResult> getProductAnalytics(
    String vendorId, {
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri(vendorId, 'products/',
          _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorProductAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getProductAnalytics failed: ${res.body}');
  }

  // ── Categories ──────────────────────────────────────────────────────────────

  Future<VendorCategoryAnalyticsResult> getCategoryAnalytics(
    String vendorId, {
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri(vendorId, 'categories/',
          _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorCategoryAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getCategoryAnalytics failed: ${res.body}');
  }

  // ── Customers ───────────────────────────────────────────────────────────────

  Future<VendorCustomerAnalyticsResult> getCustomerAnalytics(
    String vendorId, {
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri(vendorId, 'customers/',
          _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorCustomerAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getCustomerAnalytics failed: ${res.body}');
  }

  // ── Negotiations ────────────────────────────────────────────────────────────

  Future<VendorNegotiationAnalyticsResult> getNegotiationAnalytics(
    String vendorId, {
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri(vendorId, 'negotiations/',
          _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorNegotiationAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getNegotiationAnalytics failed: ${res.body}');
  }

  // ── Payments ────────────────────────────────────────────────────────────────

  Future<VendorPaymentAnalyticsResult> getPaymentAnalytics(
    String vendorId, {
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri(vendorId, 'payments/',
          _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorPaymentAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getPaymentAnalytics failed: ${res.body}');
  }

  // ── Subscription / Tier ─────────────────────────────────────────────────────

  /// Period params are ignored by this endpoint (subscription data is not
  /// time-windowed), but are accepted for API consistency.
  Future<VendorSubscriptionAnalyticsResult> getSubscriptionAnalytics(
    String vendorId,
  ) async {
    final res = await http.get(
      _uri(vendorId, 'subscription/'),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorSubscriptionAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getSubscriptionAnalytics failed: ${res.body}');
  }
}
```

---

## Endpoint Reference

All endpoints share the base path `/api/business/analytics/<vendor_id>/`.

| Method | Endpoint | Description | Insights |
|--------|----------|-------------|---------|
| `GET` | `overview/` | Revenue, orders, unique customers, ML performance score | ✅ |
| `GET` | `orders/` | Order totals, status + fulfillment breakdown, daily chart | ✅ |
| `GET` | `products/` | Top selling, slow moving, status breakdown | ✅ |
| `GET` | `categories/` | Products per category, revenue per category, top category | ✅ |
| `GET` | `customers/` | Unique, new, repeat customers, avg LTV, top spenders | ✅ |
| `GET` | `negotiations/` | Agreement rate, revenue, rounds, AI vs manual split | ✅ |
| `GET` | `payments/` | Transactions, success rate, fees, refunds, by channel | ✅ |
| `GET` | `subscription/` | Current tier, days remaining, product usage, savings | ✅ |

---

## Response Bodies

### `GET /overview/`

```json
{
  "period": { "start": "2026-04-24T00:00:00Z", "end": "2026-05-24T00:00:00Z" },
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "vendor_name": "FreshMart SA",
  "revenue": {
    "total": "42000.00",
    "previous_period": "34200.00",
    "growth_percent": 22.81
  },
  "orders": { "total": 210, "completed": 188, "cancelled": 11, "pending": 11 },
  "unique_customers": 84,
  "performance_score": {
    "score": 78.4,
    "tier": "gold",
    "scored_at": "2026-05-19T02:00:00Z"
  },
  "insights": [
    "📈 Your revenue grew 22.8% vs the previous period — excellent performance!",
    "✅ Order completion rate is 89.5% — well done.",
    "🥇 Gold tier — score 78/100. Reduce refunds and disputes to reach Platinum."
  ]
}
```

---

### `GET /orders/`

```json
{
  "period": { "start": "...", "end": "..." },
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "vendor_name": "FreshMart SA",
  "totals": {
    "total_orders": 210,
    "total_revenue": "42000.00",
    "avg_order_value": "200.00",
    "completed": 188,
    "cancelled": 11,
    "refunded": 5
  },
  "status_breakdown": [
    { "status": "delivered", "count": 188, "revenue": "37600.00" },
    { "status": "cancelled", "count": 11,  "revenue": null }
  ],
  "fulfillment_split": [
    { "fulfillment_type": "delivery", "count": 160 },
    { "fulfillment_type": "pickup",   "count": 50  }
  ],
  "daily_breakdown": [
    { "day": "2026-05-23", "count": 7, "revenue": "1400.00" }
  ],
  "insights": [
    "✅ Order completion rate is excellent at 89.5%.",
    "💰 Average order value is R200.00 — customers are making high-value purchases. Keep inventory stocked."
  ]
}
```

---

### `GET /products/`

```json
{
  "period": { "start": "...", "end": "..." },
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "totals": {
    "total_products": 85,
    "active": 72,
    "avg_price": "145.00"
  },
  "status_breakdown": [
    { "status": "active",   "count": 72 },
    { "status": "inactive", "count": 13 }
  ],
  "top_selling": [
    {
      "product_id": 12,
      "product_name": "Organic Apples 1kg",
      "units_sold": 340,
      "revenue": "5100.00",
      "orders": 290
    }
  ],
  "slow_moving": [
    { "id": 45, "name": "Artisan Honey 500ml", "price": "89.00" }
  ],
  "insights": [
    "🔥 Your best seller is 'Organic Apples 1kg' with 340 units sold.",
    "📦 3 active products had no sales this period. Consider promotions or price reductions."
  ]
}
```

---

### `GET /categories/`

```json
{
  "period": { "start": "...", "end": "..." },
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "vendor_name": "FreshMart SA",
  "totals": {
    "total_categories_with_products": 4,
    "total_active_categories": 4,
    "total_categories_with_revenue": 3
  },
  "products_per_category": [
    {
      "category_id": 3,
      "category_name": "Fresh Produce",
      "category_slug": "fresh-produce",
      "total_products": 40,
      "active_products": 38,
      "avg_price": "65.00"
    },
    {
      "category_id": 7,
      "category_name": "Dairy & Eggs",
      "category_slug": "dairy-eggs",
      "total_products": 24,
      "active_products": 22,
      "avg_price": "48.00"
    }
  ],
  "revenue_per_category": [
    {
      "category_id": 3,
      "category_name": "Fresh Produce",
      "revenue": "28000.00",
      "units_sold": 1800,
      "order_count": 160
    },
    {
      "category_id": 7,
      "category_name": "Dairy & Eggs",
      "revenue": "9600.00",
      "units_sold": 640,
      "order_count": 80
    }
  ],
  "top_category": "Fresh Produce",
  "insights": [
    "🏆 Top revenue category: 'Fresh Produce' (73.9% of period revenue).",
    "📌 No sales from: Beverages. Consider promotions or featured listings for these categories."
  ]
}
```

---

### `GET /customers/`

```json
{
  "period": { "start": "...", "end": "..." },
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "vendor_name": "FreshMart SA",
  "totals": {
    "unique_customers": 84,
    "new_customers": 21,
    "repeat_customers": 38,
    "avg_customer_lifetime_value": "500.00"
  },
  "top_repeat_customers": [
    {
      "user__email": "loyalbuyer@example.com",
      "user_id": 42,
      "order_count": 9,
      "total_spend": "1800.00"
    }
  ],
  "insights": [
    "🔁 38 repeat customers (45.2%) — loyal buyers are driving your sales. Consider a loyalty reward.",
    "💰 Average customer lifetime value is R500.00 — high-value shoppers are choosing your store."
  ]
}
```

---

### `GET /negotiations/`

```json
{
  "period": { "start": "...", "end": "..." },
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "totals": {
    "total": 48,
    "agreed": 38,
    "expired": 7,
    "open": 3,
    "agreement_rate_percent": 79.17
  },
  "agreed_revenue": "9600.00",
  "avg_rounds_to_agreement": 2.4,
  "status_breakdown": [
    { "status": "agreed",  "count": 38 },
    { "status": "expired", "count": 7  },
    { "status": "open",    "count": 3  }
  ],
  "mode_breakdown": [
    { "mode": "ai",     "count": 35 },
    { "mode": "manual", "count": 13 }
  ],
  "insights": [
    "🤝 Excellent negotiation agreement rate of 79.2%. Customers respond well to your pricing.",
    "⏳ You have 3 open negotiations. Respond quickly — unresolved rooms expire and reduce your score."
  ]
}
```

---

### `GET /payments/`

```json
{
  "period": { "start": "...", "end": "..." },
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "vendor_name": "FreshMart SA",
  "transactions": {
    "total": 224,
    "successful": 214,
    "success_rate_percent": 95.54,
    "total_revenue": "42000.00",
    "paystack_fees": "840.00",
    "net_revenue": "41160.00"
  },
  "refunds": {
    "count": 5,
    "total_amount": "1000.00"
  },
  "by_status": [
    { "status": "success", "count": 214, "total": "42000.00" },
    { "status": "failed",  "count": 10,  "total": null }
  ],
  "by_channel": [
    { "channel": "card",          "count": 150, "total": "29400.00" },
    { "channel": "bank_transfer", "count": 64,  "total": "12600.00" }
  ],
  "insights": [
    "✅ Payment success rate is excellent at 95.5%.",
    "💸 Refunds total R1000.00 (2.4% of revenue). Investigate product quality or description accuracy."
  ]
}
```

---

### `GET /subscription/`

```json
{
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "subscription": {
    "id": "aabb1234-0000-4562-b3fc-cc123456def0",
    "status": "active",
    "started_at": "2026-01-15T08:00:00Z",
    "current_period_start": "2026-05-15T08:00:00Z",
    "current_period_end": "2026-06-15T08:00:00Z",
    "cancelled_at": null,
    "days_remaining": 22,
    "is_active": true
  },
  "tier": {
    "id": "bbcc5678-1111-4562-b3fc-dd234567ef01",
    "name": "Growth",
    "slug": "growth",
    "tier_level": 1,
    "price": "299.00",
    "commission_rate": "10.00",
    "commission_saving_vs_default": "2.00",
    "max_products": 100,
    "negotiation_enabled": true,
    "max_markup_percent": "15.00",
    "max_discount_percent": "10.00",
    "featured_listings": false,
    "search_priority_boost": "0.20",
    "trial_days": 14,
    "features": [
      "Up to 100 product listings",
      "Price negotiation engine",
      "Priority search placement",
      "10% platform commission"
    ]
  },
  "product_usage": {
    "active_products": 72,
    "limit": 100,
    "usage_percent": 72.0
  },
  "insights": [
    "💰 You save 2.0% commission on every sale vs the default 12% rate.",
    "📦 You are using 72.0% of your product limit (72/100). Consider upgrading to list more products."
  ]
}
```

**When no subscription exists:**

```json
{
  "vendor_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "subscription": null,
  "tier": null,
  "product_usage": null,
  "insights": ["ℹ️ This vendor has no active tier subscription."]
}
```

---

## Subscription Status Values

| `status` | Meaning |
|----------|---------|
| `active` | Fully paid and in good standing |
| `trialing` | In free trial — will auto-convert or expire |
| `cancelled` | Cancelled; access continues until period end |
| `expired` | Billing period ended without renewal |
| `past_due` | Payment failed — Paystack will retry |

---

## Vendor Tier Levels

| `tier_level` | Typical name | Commission | Negotiation | Products |
|---|---|---|---|---|
| `0` | Starter | 12% | ✗ | 20 |
| `1` | Growth | 10% | ✓ | 100 |
| `2` | Pro | 8% | ✓ | Unlimited |

---

## Subscription Insights Reference

| Trigger | Note |
|---------|------|
| `status == 'past_due'` | `"🔴 Your subscription is past due. Update your payment method..."` |
| `status == 'cancelled'` | `"⚠️ Your Growth subscription was cancelled..."` |
| `days_remaining <= 7 && status == 'active'` | `"⏳ Your Growth subscription renews in 4 day(s)."` |
| `commission_saving > 0` | `"💰 You save 2.0% commission on every sale vs the default 12% rate."` |
| `usage_percent >= 80` | `"📦 You are using 80% of your product limit. Consider upgrading."` |
| `negotiation_enabled == false` | `"💡 Upgrade to a higher tier to unlock the price negotiation engine."` |

---

## Error Responses

| Status | Body | Cause |
|--------|------|-------|
| `401` | `{"detail": "Authentication credentials were not provided."}` | Missing or expired token |
| `403` | `{"detail": "Forbidden."}` | Vendor token used with a different vendor's UUID |
| `404` | `{"detail": "Vendor not found."}` | UUID does not match any vendor profile |
