# Sanoa Analytics — Dart Service Reference

Three sets of analytics endpoints across three user roles.  
All endpoints require `Authorization: Bearer <access_token>`.  
All endpoints support period filtering via query parameters.

---

## Table of Contents

- [Query Parameters](#query-parameters)
- [Shared Models](#shared-models)
- [Admin Analytics](#admin-analytics) — 13 endpoints under `/api/platform-admin/analytics/`
- [Vendor Analytics](#vendor-analytics) — 6 endpoints under `/api/business/analytics/`
- [Driver Analytics](#driver-analytics) — 3 endpoints under `/api/delivery/driver/analytics/`
- [Endpoint Reference](#endpoint-reference)
- [Error Responses](#error-responses)

---

## Query Parameters

Every analytics endpoint accepts the same period filters:

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `period` | string | `?period=week` | `today` · `week` · `month` (default) · `year` |
| `from` | ISO date | `?from=2026-01-01` | Custom start date (UTC) |
| `to` | ISO date | `?to=2026-03-31` | Custom end date (UTC) |

When `from` + `to` are both provided they take precedence over `period`.

---

## Shared Models

```dart
/// The time window this analytics response covers.
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


/// A single item from a breakdown list, e.g. status_breakdown.
class BreakdownItem {
  final String label;
  final int count;
  final double? total;

  const BreakdownItem({required this.label, required this.count, this.total});

  factory BreakdownItem.fromJson(Map<String, dynamic> json) {
    // label key is whichever first non-count/total key is present
    final labelValue = json.values
        .firstWhere((v) => v is String, orElse: () => '')
        .toString();
    return BreakdownItem(
      label: labelValue,
      count: (json['count'] as num?)?.toInt() ?? 0,
      total: json['total'] != null ? double.parse(json['total'].toString()) : null,
    );
  }
}


/// A daily data point used in chart sparklines.
class DailyPoint {
  final String day;       // 'YYYY-MM-DD'
  final int count;
  final double? revenue;
  final double? net;
  final int? jobs;

  const DailyPoint({
    required this.day,
    required this.count,
    this.revenue,
    this.net,
    this.jobs,
  });

  factory DailyPoint.fromJson(Map<String, dynamic> json) {
    return DailyPoint(
      day: json['day'] as String,
      count: (json['count'] as num?)?.toInt() ?? 0,
      revenue: json['revenue'] != null ? double.parse(json['revenue'].toString()) : null,
      net: json['net'] != null ? double.parse(json['net'].toString()) : null,
      jobs: (json['jobs'] as num?)?.toInt(),
    );
  }
}


/// An AI-generated note returned in every analytics response.
/// Each string starts with an emoji followed by human-readable text.
typedef AnalyticsInsights = List<String>;
```

---

## Admin Analytics

Base path: `/api/platform-admin/analytics/`  
Requires a platform-admin access token.

---

### Models — Admin Analytics

```dart
// ─────────────────────────────────────────────────────────────────────────────
// Platform Overview
// ─────────────────────────────────────────────────────────────────────────────

class PlatformOverviewRevenue {
  final double total;
  final double previousPeriod;
  final double? growthPercent;

  const PlatformOverviewRevenue({
    required this.total,
    required this.previousPeriod,
    this.growthPercent,
  });

  factory PlatformOverviewRevenue.fromJson(Map<String, dynamic> json) {
    return PlatformOverviewRevenue(
      total: double.parse(json['total'].toString()),
      previousPeriod: double.parse(json['previous_period'].toString()),
      growthPercent: json['growth_percent'] != null
          ? double.parse(json['growth_percent'].toString())
          : null,
    );
  }
}

class PlatformOverviewOrders {
  final int total;
  final int completed;
  final int cancelled;

  const PlatformOverviewOrders({
    required this.total,
    required this.completed,
    required this.cancelled,
  });

  factory PlatformOverviewOrders.fromJson(Map<String, dynamic> json) {
    return PlatformOverviewOrders(
      total: json['total'] as int,
      completed: json['completed'] as int,
      cancelled: json['cancelled'] as int,
    );
  }
}

class PlatformOverviewUsers {
  final int totalCustomers;
  final int totalVendors;
  final int totalDrivers;
  final int newCustomers;
  final int newVendors;

  const PlatformOverviewUsers({
    required this.totalCustomers,
    required this.totalVendors,
    required this.totalDrivers,
    required this.newCustomers,
    required this.newVendors,
  });

  factory PlatformOverviewUsers.fromJson(Map<String, dynamic> json) {
    return PlatformOverviewUsers(
      totalCustomers: json['total_customers'] as int,
      totalVendors: json['total_vendors'] as int,
      totalDrivers: json['total_drivers'] as int,
      newCustomers: json['new_customers'] as int,
      newVendors: json['new_vendors'] as int,
    );
  }
}

class PlatformOverviewTransactions {
  final int total;
  final double totalValue;

  const PlatformOverviewTransactions({
    required this.total,
    required this.totalValue,
  });

  factory PlatformOverviewTransactions.fromJson(Map<String, dynamic> json) {
    return PlatformOverviewTransactions(
      total: json['total'] as int,
      totalValue: double.parse(json['total_value'].toString()),
    );
  }
}

class PlatformOverviewDeliveries {
  final int total;
  final int completed;

  const PlatformOverviewDeliveries({required this.total, required this.completed});

  factory PlatformOverviewDeliveries.fromJson(Map<String, dynamic> json) {
    return PlatformOverviewDeliveries(
      total: json['total'] as int,
      completed: json['completed'] as int,
    );
  }
}

class DailySnapshot {
  final String date;
  final double totalRevenue;
  final int totalOrders;
  final int totalTransactions;
  final int newCustomers;
  final int completedDeliveries;

  const DailySnapshot({
    required this.date,
    required this.totalRevenue,
    required this.totalOrders,
    required this.totalTransactions,
    required this.newCustomers,
    required this.completedDeliveries,
  });

  factory DailySnapshot.fromJson(Map<String, dynamic> json) {
    return DailySnapshot(
      date: json['date'] as String,
      totalRevenue: double.parse((json['total_revenue'] ?? 0).toString()),
      totalOrders: (json['total_orders'] ?? 0) as int,
      totalTransactions: (json['total_transactions'] ?? 0) as int,
      newCustomers: (json['new_customers'] ?? 0) as int,
      completedDeliveries: (json['completed_deliveries'] ?? 0) as int,
    );
  }
}

class AdminOverviewResult {
  final AnalyticsPeriod period;
  final PlatformOverviewRevenue revenue;
  final PlatformOverviewOrders orders;
  final PlatformOverviewUsers users;
  final PlatformOverviewTransactions transactions;
  final PlatformOverviewDeliveries deliveries;
  final List<DailySnapshot> dailySnapshots;
  final AnalyticsInsights insights;

  const AdminOverviewResult({
    required this.period,
    required this.revenue,
    required this.orders,
    required this.users,
    required this.transactions,
    required this.deliveries,
    required this.dailySnapshots,
    required this.insights,
  });

  factory AdminOverviewResult.fromJson(Map<String, dynamic> json) {
    return AdminOverviewResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      revenue: PlatformOverviewRevenue.fromJson(json['revenue']),
      orders: PlatformOverviewOrders.fromJson(json['orders']),
      users: PlatformOverviewUsers.fromJson(json['users']),
      transactions: PlatformOverviewTransactions.fromJson(json['transactions']),
      deliveries: PlatformOverviewDeliveries.fromJson(json['deliveries']),
      dailySnapshots: (json['daily_snapshots'] as List)
          .map((e) => DailySnapshot.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Customer Analytics
// ─────────────────────────────────────────────────────────────────────────────

class CustomerChurnRisk {
  final int low;
  final int medium;
  final int high;
  final String note;

  const CustomerChurnRisk({
    required this.low,
    required this.medium,
    required this.high,
    required this.note,
  });

  factory CustomerChurnRisk.fromJson(Map<String, dynamic> json) {
    return CustomerChurnRisk(
      low: json['low'] as int,
      medium: json['medium'] as int,
      high: json['high'] as int,
      note: json['note'] as String? ?? '',
    );
  }
}

class CustomerSpending {
  final double total;
  final double averageOrderValue;

  const CustomerSpending({required this.total, required this.averageOrderValue});

  factory CustomerSpending.fromJson(Map<String, dynamic> json) {
    return CustomerSpending(
      total: double.parse(json['total'].toString()),
      averageOrderValue: double.parse(json['average_order_value'].toString()),
    );
  }
}

class CustomerLoyalty {
  final int totalPointsIssued;
  final double avgPointsPerCustomer;

  const CustomerLoyalty({
    required this.totalPointsIssued,
    required this.avgPointsPerCustomer,
  });

  factory CustomerLoyalty.fromJson(Map<String, dynamic> json) {
    return CustomerLoyalty(
      totalPointsIssued: (json['total_points_issued'] as num?)?.toInt() ?? 0,
      avgPointsPerCustomer:
          double.parse((json['avg_points_per_customer'] ?? 0).toString()),
    );
  }
}

class TopSpender {
  final String userEmail;
  final int userId;
  final double totalSpend;
  final int orderCount;

  const TopSpender({
    required this.userEmail,
    required this.userId,
    required this.totalSpend,
    required this.orderCount,
  });

  factory TopSpender.fromJson(Map<String, dynamic> json) {
    return TopSpender(
      userEmail: json['user__email'] as String? ?? '',
      userId: (json['user__id'] as num?)?.toInt() ?? 0,
      totalSpend: double.parse((json['total_spend'] ?? 0).toString()),
      orderCount: (json['order_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class AdminCustomerAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, int> totals;
  final CustomerChurnRisk churnRisk;
  final CustomerSpending spending;
  final CustomerLoyalty loyalty;
  final List<TopSpender> topSpenders;
  final AnalyticsInsights insights;

  const AdminCustomerAnalyticsResult({
    required this.period,
    required this.totals,
    required this.churnRisk,
    required this.spending,
    required this.loyalty,
    required this.topSpenders,
    required this.insights,
  });

  factory AdminCustomerAnalyticsResult.fromJson(Map<String, dynamic> json) {
    final t = json['totals'] as Map<String, dynamic>;
    return AdminCustomerAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: {
        'total_customers': t['total_customers'] as int,
        'new_customers': t['new_customers'] as int,
        'suspended': t['suspended'] as int,
        'verified': t['verified'] as int,
      },
      churnRisk: CustomerChurnRisk.fromJson(json['churn_risk']),
      spending: CustomerSpending.fromJson(json['spending']),
      loyalty: CustomerLoyalty.fromJson(json['loyalty']),
      topSpenders: (json['top_spenders'] as List)
          .map((e) => TopSpender.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Order Analytics
// ─────────────────────────────────────────────────────────────────────────────

class OrderTotals {
  final int totalOrders;
  final double totalRevenue;
  final double avgOrderValue;
  final int completed;
  final int cancelled;
  final int refunded;

  const OrderTotals({
    required this.totalOrders,
    required this.totalRevenue,
    required this.avgOrderValue,
    required this.completed,
    required this.cancelled,
    required this.refunded,
  });

  factory OrderTotals.fromJson(Map<String, dynamic> json) {
    return OrderTotals(
      totalOrders: json['total_orders'] as int,
      totalRevenue: double.parse((json['total_revenue'] ?? 0).toString()),
      avgOrderValue: double.parse((json['avg_order_value'] ?? 0).toString()),
      completed: json['completed'] as int,
      cancelled: json['cancelled'] as int,
      refunded: json['refunded'] as int,
    );
  }
}

class TopVendorByRevenue {
  final int vendorId;
  final String vendorName;
  final String tradingName;
  final int orderCount;
  final double revenue;

  const TopVendorByRevenue({
    required this.vendorId,
    required this.vendorName,
    required this.tradingName,
    required this.orderCount,
    required this.revenue,
  });

  factory TopVendorByRevenue.fromJson(Map<String, dynamic> json) {
    return TopVendorByRevenue(
      vendorId: (json['vendor__id'] as num?)?.toInt() ?? 0,
      vendorName: json['vendor__name'] as String? ?? '',
      tradingName: json['vendor__trading_name'] as String? ?? '',
      orderCount: (json['order_count'] as num?)?.toInt() ?? 0,
      revenue: double.parse((json['revenue'] ?? 0).toString()),
    );
  }
}

class AdminOrderAnalyticsResult {
  final AnalyticsPeriod period;
  final OrderTotals totals;
  final List<BreakdownItem> statusBreakdown;
  final List<BreakdownItem> paymentStatusBreakdown;
  final List<BreakdownItem> fulfillmentSplit;
  final List<TopVendorByRevenue> topVendorsByRevenue;
  final List<DailyPoint> dailyBreakdown;
  final AnalyticsInsights insights;

  const AdminOrderAnalyticsResult({
    required this.period,
    required this.totals,
    required this.statusBreakdown,
    required this.paymentStatusBreakdown,
    required this.fulfillmentSplit,
    required this.topVendorsByRevenue,
    required this.dailyBreakdown,
    required this.insights,
  });

  factory AdminOrderAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return AdminOrderAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: OrderTotals.fromJson(json['totals']),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      paymentStatusBreakdown: (json['payment_status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      fulfillmentSplit: (json['fulfillment_split'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      topVendorsByRevenue: (json['top_vendors_by_revenue'] as List)
          .map((e) => TopVendorByRevenue.fromJson(e))
          .toList(),
      dailyBreakdown: (json['daily_breakdown'] as List)
          .map((e) => DailyPoint.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Payment Analytics
// ─────────────────────────────────────────────────────────────────────────────

class PaymentTransactionSummary {
  final int total;
  final int successful;
  final double successRatePercent;
  final double totalRevenue;
  final double paystackFees;
  final double netRevenue;

  const PaymentTransactionSummary({
    required this.total,
    required this.successful,
    required this.successRatePercent,
    required this.totalRevenue,
    required this.paystackFees,
    required this.netRevenue,
  });

  factory PaymentTransactionSummary.fromJson(Map<String, dynamic> json) {
    return PaymentTransactionSummary(
      total: json['total'] as int,
      successful: json['successful'] as int,
      successRatePercent: double.parse(json['success_rate_percent'].toString()),
      totalRevenue: double.parse((json['total_revenue'] ?? 0).toString()),
      paystackFees: double.parse((json['paystack_fees'] ?? 0).toString()),
      netRevenue: double.parse((json['net_revenue'] ?? 0).toString()),
    );
  }
}

class AdminPaymentAnalyticsResult {
  final AnalyticsPeriod period;
  final PaymentTransactionSummary transactions;
  final Map<String, dynamic> refunds;
  final Map<String, dynamic> disputes;
  final List<BreakdownItem> byStatus;
  final List<BreakdownItem> byChannel;
  final List<BreakdownItem> byIntent;
  final AnalyticsInsights insights;

  const AdminPaymentAnalyticsResult({
    required this.period,
    required this.transactions,
    required this.refunds,
    required this.disputes,
    required this.byStatus,
    required this.byChannel,
    required this.byIntent,
    required this.insights,
  });

  factory AdminPaymentAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return AdminPaymentAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      transactions: PaymentTransactionSummary.fromJson(json['transactions']),
      refunds: Map<String, dynamic>.from(json['refunds']),
      disputes: Map<String, dynamic>.from(json['disputes']),
      byStatus: (json['by_status'] as List).map((e) => BreakdownItem.fromJson(e)).toList(),
      byChannel: (json['by_channel'] as List).map((e) => BreakdownItem.fromJson(e)).toList(),
      byIntent: (json['by_intent'] as List).map((e) => BreakdownItem.fromJson(e)).toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Product Analytics
// ─────────────────────────────────────────────────────────────────────────────

class TopSellingProduct {
  final int productId;
  final String productName;
  final String vendorName;
  final int unitsSold;
  final double revenue;
  final int orderCount;

  const TopSellingProduct({
    required this.productId,
    required this.productName,
    required this.vendorName,
    required this.unitsSold,
    required this.revenue,
    required this.orderCount,
  });

  factory TopSellingProduct.fromJson(Map<String, dynamic> json) {
    return TopSellingProduct(
      productId: (json['product_id'] as num?)?.toInt() ?? 0,
      productName: json['product_name'] as String? ?? '',
      vendorName: json['product__vendor__name'] as String? ?? '',
      unitsSold: (json['units_sold'] as num?)?.toInt() ?? 0,
      revenue: double.parse((json['revenue'] ?? 0).toString()),
      orderCount: (json['order_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class AdminProductAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, dynamic> totals;
  final List<BreakdownItem> statusBreakdown;
  final List<TopSellingProduct> topSelling;
  final AnalyticsInsights insights;

  const AdminProductAnalyticsResult({
    required this.period,
    required this.totals,
    required this.statusBreakdown,
    required this.topSelling,
    required this.insights,
  });

  factory AdminProductAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return AdminProductAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: Map<String, dynamic>.from(json['totals']),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      topSelling: (json['top_selling'] as List)
          .map((e) => TopSellingProduct.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Category Analytics
// ─────────────────────────────────────────────────────────────────────────────

class CategoryProductStat {
  final int categoryId;
  final String categoryName;
  final int productCount;
  final double avgPrice;

  const CategoryProductStat({
    required this.categoryId,
    required this.categoryName,
    required this.productCount,
    required this.avgPrice,
  });

  factory CategoryProductStat.fromJson(Map<String, dynamic> json) {
    return CategoryProductStat(
      categoryId: (json['category__id'] as num?)?.toInt() ?? 0,
      categoryName: json['category__name'] as String? ?? '',
      productCount: (json['product_count'] as num?)?.toInt() ?? 0,
      avgPrice: double.parse((json['avg_price'] ?? 0).toString()),
    );
  }
}

class CategoryRevenueStat {
  final int categoryId;
  final String categoryName;
  final double revenue;
  final int orders;

  const CategoryRevenueStat({
    required this.categoryId,
    required this.categoryName,
    required this.revenue,
    required this.orders,
  });

  factory CategoryRevenueStat.fromJson(Map<String, dynamic> json) {
    return CategoryRevenueStat(
      categoryId: (json['product__category__id'] as num?)?.toInt() ?? 0,
      categoryName: json['product__category__name'] as String? ?? '',
      revenue: double.parse((json['revenue'] ?? 0).toString()),
      orders: (json['orders'] as num?)?.toInt() ?? 0,
    );
  }
}

class AdminCategoryAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, int> totals;
  final List<CategoryProductStat> productsPerCategory;
  final List<CategoryRevenueStat> revenuePerCategory;
  final AnalyticsInsights insights;

  const AdminCategoryAnalyticsResult({
    required this.period,
    required this.totals,
    required this.productsPerCategory,
    required this.revenuePerCategory,
    required this.insights,
  });

  factory AdminCategoryAnalyticsResult.fromJson(Map<String, dynamic> json) {
    final t = json['totals'] as Map<String, dynamic>;
    return AdminCategoryAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: {
        'total_categories': t['total_categories'] as int,
        'system_categories': t['system_categories'] as int,
        'custom_categories': t['custom_categories'] as int,
        'active': t['active'] as int,
      },
      productsPerCategory: (json['products_per_category'] as List)
          .map((e) => CategoryProductStat.fromJson(e))
          .toList(),
      revenuePerCategory: (json['revenue_per_category'] as List)
          .map((e) => CategoryRevenueStat.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Negotiation Analytics
// ─────────────────────────────────────────────────────────────────────────────

class NegotiationModePerformance {
  final int total;
  final int agreed;
  final double agreementRatePercent;

  const NegotiationModePerformance({
    required this.total,
    required this.agreed,
    required this.agreementRatePercent,
  });

  factory NegotiationModePerformance.fromJson(Map<String, dynamic> json) {
    return NegotiationModePerformance(
      total: json['total'] as int,
      agreed: json['agreed'] as int,
      agreementRatePercent:
          double.parse(json['agreement_rate_percent'].toString()),
    );
  }
}

class AdminNegotiationAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, dynamic> totals;
  final double avgRoundsToAgreement;
  final double agreedPriceTotal;
  final List<BreakdownItem> modeBreakdown;
  final List<BreakdownItem> statusBreakdown;
  final NegotiationModePerformance aiPerformance;
  final NegotiationModePerformance manualPerformance;
  final AnalyticsInsights insights;

  const AdminNegotiationAnalyticsResult({
    required this.period,
    required this.totals,
    required this.avgRoundsToAgreement,
    required this.agreedPriceTotal,
    required this.modeBreakdown,
    required this.statusBreakdown,
    required this.aiPerformance,
    required this.manualPerformance,
    required this.insights,
  });

  factory AdminNegotiationAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return AdminNegotiationAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: Map<String, dynamic>.from(json['totals']),
      avgRoundsToAgreement:
          double.parse((json['avg_rounds_to_agreement'] ?? 0).toString()),
      agreedPriceTotal:
          double.parse((json['agreed_price_total'] ?? 0).toString()),
      modeBreakdown: (json['mode_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      aiPerformance:
          NegotiationModePerformance.fromJson(json['ai_performance']),
      manualPerformance:
          NegotiationModePerformance.fromJson(json['manual_performance']),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Debit / Credit Analytics
// ─────────────────────────────────────────────────────────────────────────────

class DebitAccountSummary {
  final int total;
  final int active;
  final int suspended;
  final int closed;
  final List<BreakdownItem> statusBreakdown;

  const DebitAccountSummary({
    required this.total,
    required this.active,
    required this.suspended,
    required this.closed,
    required this.statusBreakdown,
  });

  factory DebitAccountSummary.fromJson(Map<String, dynamic> json) {
    return DebitAccountSummary(
      total: json['total'] as int,
      active: json['active'] as int,
      suspended: json['suspended'] as int,
      closed: json['closed'] as int,
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
    );
  }
}

class AdminDebitAnalyticsResult {
  final AnalyticsPeriod period;
  final DebitAccountSummary accounts;
  final Map<String, double> balances;
  final Map<String, dynamic> purchases;
  final Map<String, dynamic> repayments;
  final AnalyticsInsights insights;

  const AdminDebitAnalyticsResult({
    required this.period,
    required this.accounts,
    required this.balances,
    required this.purchases,
    required this.repayments,
    required this.insights,
  });

  factory AdminDebitAnalyticsResult.fromJson(Map<String, dynamic> json) {
    final b = json['balances'] as Map<String, dynamic>;
    return AdminDebitAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      accounts: DebitAccountSummary.fromJson(json['accounts']),
      balances: {
        'total_credit_limit':
            double.parse((b['total_credit_limit'] ?? 0).toString()),
        'total_outstanding_balance':
            double.parse((b['total_outstanding_balance'] ?? 0).toString()),
        'total_penalties':
            double.parse((b['total_penalties'] ?? 0).toString()),
      },
      purchases: Map<String, dynamic>.from(json['purchases']),
      repayments: Map<String, dynamic>.from(json['repayments']),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Delivery Analytics
// ─────────────────────────────────────────────────────────────────────────────

class DeliveryTotals {
  final int totalDeliveries;
  final int completed;
  final int failed;
  final int pending;
  final int inTransit;
  final double completionRatePercent;

  const DeliveryTotals({
    required this.totalDeliveries,
    required this.completed,
    required this.failed,
    required this.pending,
    required this.inTransit,
    required this.completionRatePercent,
  });

  factory DeliveryTotals.fromJson(Map<String, dynamic> json) {
    return DeliveryTotals(
      totalDeliveries: json['total_deliveries'] as int,
      completed: json['completed'] as int,
      failed: json['failed'] as int,
      pending: json['pending'] as int,
      inTransit: json['in_transit'] as int,
      completionRatePercent:
          double.parse(json['completion_rate_percent'].toString()),
    );
  }
}

class AdminDeliveryAnalyticsResult {
  final AnalyticsPeriod period;
  final DeliveryTotals totals;
  final Map<String, dynamic> performance;
  final Map<String, dynamic> ratings;
  final List<BreakdownItem> statusBreakdown;
  final AnalyticsInsights insights;

  const AdminDeliveryAnalyticsResult({
    required this.period,
    required this.totals,
    required this.performance,
    required this.ratings,
    required this.statusBreakdown,
    required this.insights,
  });

  factory AdminDeliveryAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return AdminDeliveryAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: DeliveryTotals.fromJson(json['totals']),
      performance: Map<String, dynamic>.from(json['performance']),
      ratings: Map<String, dynamic>.from(json['ratings']),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Driver Analytics (Admin view)
// ─────────────────────────────────────────────────────────────────────────────

class DriverGradeDistributionItem {
  final String grade;
  final int count;

  const DriverGradeDistributionItem({required this.grade, required this.count});

  factory DriverGradeDistributionItem.fromJson(Map<String, dynamic> json) {
    return DriverGradeDistributionItem(
      grade: json['grade'] as String? ?? '',
      count: (json['count'] as num?)?.toInt() ?? 0,
    );
  }
}

class AdminDriverTopEntry {
  final String email;
  final double score;
  final String grade;
  final int totalDeliveries;
  final double avgRating;
  final double completionRate;

  const AdminDriverTopEntry({
    required this.email,
    required this.score,
    required this.grade,
    required this.totalDeliveries,
    required this.avgRating,
    required this.completionRate,
  });

  factory AdminDriverTopEntry.fromJson(Map<String, dynamic> json) {
    return AdminDriverTopEntry(
      email: json['driver__user__email'] as String? ?? '',
      score: double.parse((json['score'] ?? 0).toString()),
      grade: json['grade'] as String? ?? '',
      totalDeliveries: (json['total_deliveries'] as num?)?.toInt() ?? 0,
      avgRating: double.parse((json['avg_rating'] ?? 0).toString()),
      completionRate: double.parse((json['completion_rate'] ?? 0).toString()),
    );
  }
}

class AdminDriverAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, dynamic> totals;
  final Map<String, dynamic> mlPerformance;
  final List<AdminDriverTopEntry> topDrivers;
  final List<BreakdownItem> vehicleBreakdown;
  final List<BreakdownItem> verificationBreakdown;
  final AnalyticsInsights insights;

  const AdminDriverAnalyticsResult({
    required this.period,
    required this.totals,
    required this.mlPerformance,
    required this.topDrivers,
    required this.vehicleBreakdown,
    required this.verificationBreakdown,
    required this.insights,
  });

  factory AdminDriverAnalyticsResult.fromJson(Map<String, dynamic> json) {
    final ml = json['ml_performance'] as Map<String, dynamic>;
    return AdminDriverAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: Map<String, dynamic>.from(json['totals']),
      mlPerformance: {
        'grade_distribution': (ml['grade_distribution'] as List)
            .map((e) => DriverGradeDistributionItem.fromJson(e))
            .toList(),
        'payout_anomaly_flagged': ml['payout_anomaly_flagged'] as int,
        'note': ml['note'] as String,
      },
      topDrivers: (json['top_drivers'] as List)
          .map((e) => AdminDriverTopEntry.fromJson(e))
          .toList(),
      vehicleBreakdown: (json['vehicle_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      verificationBreakdown: (json['verification_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Payout Analytics
// ─────────────────────────────────────────────────────────────────────────────

class PayoutSummary {
  final int count;
  final double totalGross;
  final double totalCommission;
  final double totalNetPaid;
  final double pending;

  const PayoutSummary({
    required this.count,
    required this.totalGross,
    required this.totalCommission,
    required this.totalNetPaid,
    required this.pending,
  });

  factory PayoutSummary.fromJson(Map<String, dynamic> json) {
    return PayoutSummary(
      count: (json['count'] as num?)?.toInt() ?? 0,
      totalGross: double.parse((json['total_gross'] ?? 0).toString()),
      totalCommission: double.parse((json['total_commission'] ?? 0).toString()),
      totalNetPaid: double.parse((json['total_net_paid'] ?? 0).toString()),
      pending: double.parse((json['pending'] ?? 0).toString()),
    );
  }
}

class TopEarnerEntry {
  final String email;
  final double total;
  final int jobs;

  const TopEarnerEntry({
    required this.email,
    required this.total,
    required this.jobs,
  });

  factory TopEarnerEntry.fromJson(Map<String, dynamic> json) {
    return TopEarnerEntry(
      email: json['driver__user__email'] as String? ?? '',
      total: double.parse((json['total'] ?? 0).toString()),
      jobs: (json['jobs'] as num?)?.toInt() ?? 0,
    );
  }
}

class AdminPayoutAnalyticsResult {
  final AnalyticsPeriod period;
  final PayoutSummary payouts;
  final Map<String, double> earnings;
  final List<BreakdownItem> statusBreakdown;
  final List<TopEarnerEntry> topEarners;
  final AnalyticsInsights insights;

  const AdminPayoutAnalyticsResult({
    required this.period,
    required this.payouts,
    required this.earnings,
    required this.statusBreakdown,
    required this.topEarners,
    required this.insights,
  });

  factory AdminPayoutAnalyticsResult.fromJson(Map<String, dynamic> json) {
    final e = json['earnings'] as Map<String, dynamic>;
    return AdminPayoutAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      payouts: PayoutSummary.fromJson(json['payouts']),
      earnings: {
        'total_gross': double.parse((e['total_gross'] ?? 0).toString()),
        'platform_commission':
            double.parse((e['platform_commission'] ?? 0).toString()),
        'driver_net': double.parse((e['driver_net'] ?? 0).toString()),
      },
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      topEarners: (json['top_earners'] as List)
          .map((e) => TopEarnerEntry.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Subaccount Analytics
// ─────────────────────────────────────────────────────────────────────────────

class SubaccountRevenueStat {
  final int subaccountId;
  final String businessName;
  final String subaccountCode;
  final double revenue;
  final int txnCount;
  final double fees;

  const SubaccountRevenueStat({
    required this.subaccountId,
    required this.businessName,
    required this.subaccountCode,
    required this.revenue,
    required this.txnCount,
    required this.fees,
  });

  factory SubaccountRevenueStat.fromJson(Map<String, dynamic> json) {
    return SubaccountRevenueStat(
      subaccountId: (json['subaccount__id'] as num?)?.toInt() ?? 0,
      businessName: json['subaccount__business_name'] as String? ?? '',
      subaccountCode: json['subaccount__subaccount_code'] as String? ?? '',
      revenue: double.parse((json['revenue'] ?? 0).toString()),
      txnCount: (json['txn_count'] as num?)?.toInt() ?? 0,
      fees: double.parse((json['fees'] ?? 0).toString()),
    );
  }
}

class AdminSubaccountAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, int> totals;
  final List<SubaccountRevenueStat> revenuePerSubaccount;
  final AnalyticsInsights insights;

  const AdminSubaccountAnalyticsResult({
    required this.period,
    required this.totals,
    required this.revenuePerSubaccount,
    required this.insights,
  });

  factory AdminSubaccountAnalyticsResult.fromJson(Map<String, dynamic> json) {
    final t = json['totals'] as Map<String, dynamic>;
    return AdminSubaccountAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: {
        'total_subaccounts': t['total_subaccounts'] as int,
        'active': t['active'] as int,
        'inactive': t['inactive'] as int,
      },
      revenuePerSubaccount: (json['revenue_per_subaccount'] as List)
          .map((e) => SubaccountRevenueStat.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Subscription Analytics
// ─────────────────────────────────────────────────────────────────────────────

/// A single customer plan from the plan_breakdown list.
class SubscriptionPlanBreakdown {
  final String planId;
  final String planName;
  final String slug;
  final String planTier;      // 'basic' | 'premium' | 'plus'
  final double price;
  final String billingCycle;  // 'monthly' | 'yearly'
  final int subscriberCount;

  const SubscriptionPlanBreakdown({
    required this.planId,
    required this.planName,
    required this.slug,
    required this.planTier,
    required this.price,
    required this.billingCycle,
    required this.subscriberCount,
  });

  factory SubscriptionPlanBreakdown.fromJson(Map<String, dynamic> json) {
    return SubscriptionPlanBreakdown(
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

/// A single tier from the vendor tier_breakdown list.
class VendorTierBreakdown {
  final String tierId;
  final String tierName;
  final String slug;
  final int tierLevel;
  final double price;
  final double commissionRate;
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

class CustomerSubscriptionSummary {
  final int total;
  final int active;
  final int trialing;
  final int cancelled;
  final int expired;
  final int pastDue;
  final int newThisPeriod;
  final int cancellationsThisPeriod;
  final double revenueThisPeriod;
  final double estimatedMrr;
  final List<BreakdownItem> statusBreakdown;
  final List<SubscriptionPlanBreakdown> planBreakdown;
  final List<Map<String, dynamic>> plansCatalogue;

  const CustomerSubscriptionSummary({
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

  factory CustomerSubscriptionSummary.fromJson(Map<String, dynamic> json) {
    return CustomerSubscriptionSummary(
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
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      planBreakdown: (json['plan_breakdown'] as List)
          .map((e) => SubscriptionPlanBreakdown.fromJson(e))
          .toList(),
      plansCatalogue: (json['plans_catalogue'] as List)
          .map((e) => Map<String, dynamic>.from(e))
          .toList(),
    );
  }
}

class VendorTierSubscriptionSummary {
  final int total;
  final int active;
  final int trialing;
  final int cancelled;
  final int expired;
  final int pastDue;
  final int newThisPeriod;
  final int cancellationsThisPeriod;
  final double revenueThisPeriod;
  final double estimatedMrr;
  final List<BreakdownItem> statusBreakdown;
  final List<VendorTierBreakdown> tierBreakdown;
  final List<Map<String, dynamic>> tiersCatalogue;

  const VendorTierSubscriptionSummary({
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

  factory VendorTierSubscriptionSummary.fromJson(Map<String, dynamic> json) {
    return VendorTierSubscriptionSummary(
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
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      tierBreakdown: (json['tier_breakdown'] as List)
          .map((e) => VendorTierBreakdown.fromJson(e))
          .toList(),
      tiersCatalogue: (json['tiers_catalogue'] as List)
          .map((e) => Map<String, dynamic>.from(e))
          .toList(),
    );
  }
}

class SubscriptionCombinedSummary {
  final int totalPayingSubscribers;
  final double combinedMrr;
  final double combinedRevenueThisPeriod;
  final int newThisPeriod;
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

class AdminSubscriptionAnalyticsResult {
  final AnalyticsPeriod period;
  final CustomerSubscriptionSummary customerSubscriptions;
  final VendorTierSubscriptionSummary vendorTierSubscriptions;
  final SubscriptionCombinedSummary combined;
  final AnalyticsInsights insights;

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
      customerSubscriptions: CustomerSubscriptionSummary.fromJson(
          json['customer_subscriptions']),
      vendorTierSubscriptions: VendorTierSubscriptionSummary.fromJson(
          json['vendor_tier_subscriptions']),
      combined: SubscriptionCombinedSummary.fromJson(json['combined']),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}
```

---

### Admin Analytics Service

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class AdminAnalyticsService {
  final String baseUrl;
  final String Function() getToken;

  const AdminAnalyticsService({
    required this.baseUrl,
    required this.getToken,
  });

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${getToken()}',
      };

  Uri _uri(String path, [Map<String, String>? params]) {
    final uri = Uri.parse('$baseUrl/api/platform-admin/analytics$path');
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

  Future<AdminOverviewResult> getOverview({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/overview/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminOverviewResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getOverview failed: ${res.body}');
  }

  // ── Customers ───────────────────────────────────────────────────────────────

  Future<AdminCustomerAnalyticsResult> getCustomerAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/customers/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminCustomerAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getCustomerAnalytics failed: ${res.body}');
  }

  // ── Orders ──────────────────────────────────────────────────────────────────

  Future<AdminOrderAnalyticsResult> getOrderAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/orders/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminOrderAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getOrderAnalytics failed: ${res.body}');
  }

  // ── Payments ────────────────────────────────────────────────────────────────

  Future<AdminPaymentAnalyticsResult> getPaymentAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/payments/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminPaymentAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getPaymentAnalytics failed: ${res.body}');
  }

  // ── Products ────────────────────────────────────────────────────────────────

  Future<AdminProductAnalyticsResult> getProductAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/products/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminProductAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getProductAnalytics failed: ${res.body}');
  }

  // ── Categories ──────────────────────────────────────────────────────────────

  Future<AdminCategoryAnalyticsResult> getCategoryAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/categories/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminCategoryAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getCategoryAnalytics failed: ${res.body}');
  }

  // ── Negotiations ────────────────────────────────────────────────────────────

  Future<AdminNegotiationAnalyticsResult> getNegotiationAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/negotiations/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminNegotiationAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getNegotiationAnalytics failed: ${res.body}');
  }

  // ── Debit / Credit ──────────────────────────────────────────────────────────

  Future<AdminDebitAnalyticsResult> getDebitAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/debit/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminDebitAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getDebitAnalytics failed: ${res.body}');
  }

  // ── Deliveries ──────────────────────────────────────────────────────────────

  Future<AdminDeliveryAnalyticsResult> getDeliveryAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/deliveries/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminDeliveryAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getDeliveryAnalytics failed: ${res.body}');
  }

  // ── Drivers ─────────────────────────────────────────────────────────────────

  Future<AdminDriverAnalyticsResult> getDriverAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/drivers/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminDriverAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getDriverAnalytics failed: ${res.body}');
  }

  // ── Payouts ─────────────────────────────────────────────────────────────────

  Future<AdminPayoutAnalyticsResult> getPayoutAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/payouts/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminPayoutAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getPayoutAnalytics failed: ${res.body}');
  }

  // ── Subaccounts ─────────────────────────────────────────────────────────────

  Future<AdminSubaccountAnalyticsResult> getSubaccountAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/subaccounts/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminSubaccountAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getSubaccountAnalytics failed: ${res.body}');
  }

  // ── Subscriptions ────────────────────────────────────────────────────────────

  Future<AdminSubscriptionAnalyticsResult> getSubscriptionAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/subscriptions/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return AdminSubscriptionAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getSubscriptionAnalytics failed: ${res.body}');
  }
}
```

---

## Vendor Analytics

Base path: `/api/business/analytics/`  
Requires a vendor access token. Each endpoint returns data scoped to the authenticated vendor's profile only.

---

### Models — Vendor Analytics

```dart
// ─────────────────────────────────────────────────────────────────────────────
// Vendor Overview
// ─────────────────────────────────────────────────────────────────────────────

class VendorMlPerformanceScore {
  final double score;
  final String tier;   // 'bronze' | 'silver' | 'gold' | 'platinum'
  final DateTime scoredAt;

  const VendorMlPerformanceScore({
    required this.score,
    required this.tier,
    required this.scoredAt,
  });

  factory VendorMlPerformanceScore.fromJson(Map<String, dynamic> json) {
    return VendorMlPerformanceScore(
      score: double.parse(json['score'].toString()),
      tier: json['tier'] as String,
      scoredAt: DateTime.parse(json['scored_at'] as String),
    );
  }
}

class VendorOverviewResult {
  final AnalyticsPeriod period;
  final Map<String, dynamic> revenue;
  final Map<String, int> orders;
  final int uniqueCustomers;
  final VendorMlPerformanceScore? performanceScore;
  final AnalyticsInsights insights;

  const VendorOverviewResult({
    required this.period,
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
      revenue: {
        'total': double.parse((rev['total'] ?? 0).toString()),
        'previous_period': double.parse((rev['previous_period'] ?? 0).toString()),
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
          ? VendorMlPerformanceScore.fromJson(json['performance_score'])
          : null,
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Vendor Orders
// ─────────────────────────────────────────────────────────────────────────────

class VendorOrderAnalyticsResult {
  final AnalyticsPeriod period;
  final OrderTotals totals;
  final List<BreakdownItem> statusBreakdown;
  final List<BreakdownItem> fulfillmentSplit;
  final List<DailyPoint> dailyBreakdown;
  final AnalyticsInsights insights;

  const VendorOrderAnalyticsResult({
    required this.period,
    required this.totals,
    required this.statusBreakdown,
    required this.fulfillmentSplit,
    required this.dailyBreakdown,
    required this.insights,
  });

  factory VendorOrderAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorOrderAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: OrderTotals.fromJson(json['totals']),
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
// Vendor Products
// ─────────────────────────────────────────────────────────────────────────────

class SlowMovingProduct {
  final int id;
  final String name;
  final double price;

  const SlowMovingProduct({
    required this.id,
    required this.name,
    required this.price,
  });

  factory SlowMovingProduct.fromJson(Map<String, dynamic> json) {
    return SlowMovingProduct(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: json['name'] as String? ?? '',
      price: double.parse((json['price'] ?? 0).toString()),
    );
  }
}

class VendorProductAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, dynamic> totals;
  final List<BreakdownItem> statusBreakdown;
  final List<TopSellingProduct> topSelling;
  final List<SlowMovingProduct> slowMoving;
  final AnalyticsInsights insights;

  const VendorProductAnalyticsResult({
    required this.period,
    required this.totals,
    required this.statusBreakdown,
    required this.topSelling,
    required this.slowMoving,
    required this.insights,
  });

  factory VendorProductAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorProductAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: Map<String, dynamic>.from(json['totals']),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      topSelling: (json['top_selling'] as List)
          .map((e) => TopSellingProduct.fromJson(e))
          .toList(),
      slowMoving: (json['slow_moving'] as List)
          .map((e) => SlowMovingProduct.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Vendor Customers
// ─────────────────────────────────────────────────────────────────────────────

class RepeatCustomerEntry {
  final String email;
  final int userId;
  final int orderCount;
  final double totalSpend;

  const RepeatCustomerEntry({
    required this.email,
    required this.userId,
    required this.orderCount,
    required this.totalSpend,
  });

  factory RepeatCustomerEntry.fromJson(Map<String, dynamic> json) {
    return RepeatCustomerEntry(
      email: json['user__email'] as String? ?? '',
      userId: (json['user_id'] as num?)?.toInt() ?? 0,
      orderCount: (json['order_count'] as num?)?.toInt() ?? 0,
      totalSpend: double.parse((json['total_spend'] ?? 0).toString()),
    );
  }
}

class VendorCustomerAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, dynamic> totals;
  final List<RepeatCustomerEntry> topRepeatCustomers;
  final AnalyticsInsights insights;

  const VendorCustomerAnalyticsResult({
    required this.period,
    required this.totals,
    required this.topRepeatCustomers,
    required this.insights,
  });

  factory VendorCustomerAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorCustomerAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      totals: Map<String, dynamic>.from(json['totals']),
      topRepeatCustomers: (json['top_repeat_customers'] as List)
          .map((e) => RepeatCustomerEntry.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Vendor Negotiations
// ─────────────────────────────────────────────────────────────────────────────

class VendorNegotiationAnalyticsResult {
  final AnalyticsPeriod period;
  final Map<String, dynamic> totals;
  final double agreedRevenue;
  final double avgRoundsToAgreement;
  final List<BreakdownItem> statusBreakdown;
  final List<BreakdownItem> modeBreakdown;
  final AnalyticsInsights insights;

  const VendorNegotiationAnalyticsResult({
    required this.period,
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
      totals: Map<String, dynamic>.from(json['totals']),
      agreedRevenue: double.parse((json['agreed_revenue'] ?? 0).toString()),
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
// Vendor Payments
// ─────────────────────────────────────────────────────────────────────────────

class VendorPaymentAnalyticsResult {
  final AnalyticsPeriod period;
  final PaymentTransactionSummary transactions;
  final Map<String, dynamic> refunds;
  final List<BreakdownItem> byStatus;
  final List<BreakdownItem> byChannel;
  final AnalyticsInsights insights;

  const VendorPaymentAnalyticsResult({
    required this.period,
    required this.transactions,
    required this.refunds,
    required this.byStatus,
    required this.byChannel,
    required this.insights,
  });

  factory VendorPaymentAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return VendorPaymentAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      transactions: PaymentTransactionSummary.fromJson(json['transactions']),
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
```

---

### Vendor Analytics Service

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

  Uri _uri(String path, [Map<String, String>? params]) {
    final uri = Uri.parse('$baseUrl/api/business/analytics$path');
    return params != null ? uri.replace(queryParameters: params) : uri;
  }

  Map<String, String> _periodParams({String? period, String? from, String? to}) {
    final p = <String, String>{};
    if (period != null) p['period'] = period;
    if (from != null) p['from'] = from;
    if (to != null) p['to'] = to;
    return p;
  }

  // ── Overview ────────────────────────────────────────────────────────────────

  Future<VendorOverviewResult> getOverview({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/overview/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorOverviewResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getOverview failed: ${res.body}');
  }

  // ── Orders ──────────────────────────────────────────────────────────────────

  Future<VendorOrderAnalyticsResult> getOrderAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/orders/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorOrderAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getOrderAnalytics failed: ${res.body}');
  }

  // ── Products ────────────────────────────────────────────────────────────────

  Future<VendorProductAnalyticsResult> getProductAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/products/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorProductAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getProductAnalytics failed: ${res.body}');
  }

  // ── Customers ───────────────────────────────────────────────────────────────

  Future<VendorCustomerAnalyticsResult> getCustomerAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/customers/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorCustomerAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getCustomerAnalytics failed: ${res.body}');
  }

  // ── Negotiations ────────────────────────────────────────────────────────────

  Future<VendorNegotiationAnalyticsResult> getNegotiationAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/negotiations/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorNegotiationAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getNegotiationAnalytics failed: ${res.body}');
  }

  // ── Payments ────────────────────────────────────────────────────────────────

  Future<VendorPaymentAnalyticsResult> getPaymentAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/payments/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return VendorPaymentAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getPaymentAnalytics failed: ${res.body}');
  }
}
```

---

## Driver Analytics

Base path: `/api/delivery/driver/analytics/`  
Requires a driver access token. Returns data scoped to the authenticated driver only.

---

### Models — Driver Analytics

```dart
// ─────────────────────────────────────────────────────────────────────────────
// Driver ML Performance Score
// ─────────────────────────────────────────────────────────────────────────────

class DriverMlScore {
  final double score;
  final String grade;           // 'A' | 'B' | 'C' | 'D' | 'F'
  final double completionRate;
  final double onTimeRate;
  final double? avgDeliveryTimeMins;
  final bool payoutAnomaly;
  final DateTime scoredAt;

  const DriverMlScore({
    required this.score,
    required this.grade,
    required this.completionRate,
    required this.onTimeRate,
    this.avgDeliveryTimeMins,
    required this.payoutAnomaly,
    required this.scoredAt,
  });

  factory DriverMlScore.fromJson(Map<String, dynamic> json) {
    return DriverMlScore(
      score: double.parse(json['score'].toString()),
      grade: json['grade'] as String,
      completionRate: double.parse((json['completion_rate'] ?? 0).toString()),
      onTimeRate: double.parse((json['on_time_rate'] ?? 0).toString()),
      avgDeliveryTimeMins: json['avg_delivery_time_mins'] != null
          ? double.parse(json['avg_delivery_time_mins'].toString())
          : null,
      payoutAnomaly: json['payout_anomaly'] as bool? ?? false,
      scoredAt: DateTime.parse(json['scored_at'] as String),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Driver Overview
// ─────────────────────────────────────────────────────────────────────────────

class DriverOverviewResult {
  final AnalyticsPeriod period;
  final Map<String, dynamic> deliveries;
  final Map<String, double> earnings;
  final double rating;
  final int totalDeliveriesAllTime;
  final DriverMlScore? performanceScore;
  final AnalyticsInsights insights;

  const DriverOverviewResult({
    required this.period,
    required this.deliveries,
    required this.earnings,
    required this.rating,
    required this.totalDeliveriesAllTime,
    this.performanceScore,
    required this.insights,
  });

  factory DriverOverviewResult.fromJson(Map<String, dynamic> json) {
    final d = json['deliveries'] as Map<String, dynamic>;
    final e = json['earnings'] as Map<String, dynamic>;
    return DriverOverviewResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      deliveries: {
        'total': d['total'] as int,
        'completed': d['completed'] as int,
        'failed': d['failed'] as int,
        'in_transit': d['in_transit'] as int,
        'completion_rate_percent':
            double.parse(d['completion_rate_percent'].toString()),
      },
      earnings: {
        'gross': double.parse((e['gross'] ?? 0).toString()),
        'platform_commission':
            double.parse((e['platform_commission'] ?? 0).toString()),
        'net': double.parse((e['net'] ?? 0).toString()),
      },
      rating: double.parse((json['rating'] ?? 0).toString()),
      totalDeliveriesAllTime:
          (json['total_deliveries_all_time'] as num?)?.toInt() ?? 0,
      performanceScore: json['performance_score'] != null
          ? DriverMlScore.fromJson(json['performance_score'])
          : null,
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Driver Earnings
// ─────────────────────────────────────────────────────────────────────────────

class DriverEarningsSummary {
  final int totalJobs;
  final double gross;
  final double platformCommission;
  final double net;
  final double avgPerJob;

  const DriverEarningsSummary({
    required this.totalJobs,
    required this.gross,
    required this.platformCommission,
    required this.net,
    required this.avgPerJob,
  });

  factory DriverEarningsSummary.fromJson(Map<String, dynamic> json) {
    return DriverEarningsSummary(
      totalJobs: (json['total_jobs'] as num?)?.toInt() ?? 0,
      gross: double.parse((json['gross'] ?? 0).toString()),
      platformCommission:
          double.parse((json['platform_commission'] ?? 0).toString()),
      net: double.parse((json['net'] ?? 0).toString()),
      avgPerJob: double.parse((json['avg_per_job'] ?? 0).toString()),
    );
  }
}

class DriverPayoutSummary {
  final int count;
  final double totalPaid;
  final List<BreakdownItem> statusBreakdown;

  const DriverPayoutSummary({
    required this.count,
    required this.totalPaid,
    required this.statusBreakdown,
  });

  factory DriverPayoutSummary.fromJson(Map<String, dynamic> json) {
    return DriverPayoutSummary(
      count: (json['count'] as num?)?.toInt() ?? 0,
      totalPaid: double.parse((json['total_paid'] ?? 0).toString()),
      statusBreakdown: (json['status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
    );
  }
}

class DriverEarningsAnalyticsResult {
  final AnalyticsPeriod period;
  final DriverEarningsSummary earnings;
  final DriverPayoutSummary payouts;
  final List<BreakdownItem> earningsStatusBreakdown;
  final List<DailyPoint> dailyEarnings;
  final AnalyticsInsights insights;

  const DriverEarningsAnalyticsResult({
    required this.period,
    required this.earnings,
    required this.payouts,
    required this.earningsStatusBreakdown,
    required this.dailyEarnings,
    required this.insights,
  });

  factory DriverEarningsAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return DriverEarningsAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      earnings: DriverEarningsSummary.fromJson(json['earnings']),
      payouts: DriverPayoutSummary.fromJson(json['payouts']),
      earningsStatusBreakdown: (json['earnings_status_breakdown'] as List)
          .map((e) => BreakdownItem.fromJson(e))
          .toList(),
      dailyEarnings: (json['daily_earnings'] as List)
          .map((e) => DailyPoint.fromJson(e))
          .toList(),
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}


// ─────────────────────────────────────────────────────────────────────────────
// Driver Performance
// ─────────────────────────────────────────────────────────────────────────────

class DriverPerformanceDelivery {
  final int totalJobs;
  final int completed;
  final int failed;
  final double? avgDeliveryTimeMins;
  final double onTimeRatePercent;
  final double avgDistanceKm;

  const DriverPerformanceDelivery({
    required this.totalJobs,
    required this.completed,
    required this.failed,
    this.avgDeliveryTimeMins,
    required this.onTimeRatePercent,
    required this.avgDistanceKm,
  });

  factory DriverPerformanceDelivery.fromJson(Map<String, dynamic> json) {
    return DriverPerformanceDelivery(
      totalJobs: (json['total_jobs'] as num?)?.toInt() ?? 0,
      completed: (json['completed'] as num?)?.toInt() ?? 0,
      failed: (json['failed'] as num?)?.toInt() ?? 0,
      avgDeliveryTimeMins: json['avg_delivery_time_mins'] != null
          ? double.parse(json['avg_delivery_time_mins'].toString())
          : null,
      onTimeRatePercent:
          double.parse((json['on_time_rate_percent'] ?? 0).toString()),
      avgDistanceKm: double.parse((json['avg_distance_km'] ?? 0).toString()),
    );
  }
}

class DriverPerformanceRatings {
  final double avgRating;
  final int totalRatings;
  final double allTimeAvg;

  const DriverPerformanceRatings({
    required this.avgRating,
    required this.totalRatings,
    required this.allTimeAvg,
  });

  factory DriverPerformanceRatings.fromJson(Map<String, dynamic> json) {
    return DriverPerformanceRatings(
      avgRating: double.parse((json['avg_rating'] ?? 0).toString()),
      totalRatings: (json['total_ratings'] as num?)?.toInt() ?? 0,
      allTimeAvg: double.parse((json['all_time_avg'] ?? 0).toString()),
    );
  }
}

class DriverPerformanceShifts {
  final int totalShifts;
  final double totalHoursOnline;

  const DriverPerformanceShifts({
    required this.totalShifts,
    required this.totalHoursOnline,
  });

  factory DriverPerformanceShifts.fromJson(Map<String, dynamic> json) {
    return DriverPerformanceShifts(
      totalShifts: (json['total_shifts'] as num?)?.toInt() ?? 0,
      totalHoursOnline: double.parse((json['total_hours_online'] ?? 0).toString()),
    );
  }
}

class DriverPerformanceMlScore {
  final double score;
  final String grade;
  final bool payoutAnomaly;
  final String modelVersion;
  final DateTime scoredAt;

  const DriverPerformanceMlScore({
    required this.score,
    required this.grade,
    required this.payoutAnomaly,
    required this.modelVersion,
    required this.scoredAt,
  });

  factory DriverPerformanceMlScore.fromJson(Map<String, dynamic> json) {
    return DriverPerformanceMlScore(
      score: double.parse(json['score'].toString()),
      grade: json['grade'] as String,
      payoutAnomaly: json['payout_anomaly'] as bool? ?? false,
      modelVersion: json['model_version'] as String? ?? '',
      scoredAt: DateTime.parse(json['scored_at'] as String),
    );
  }
}

class DriverPerformanceAnalyticsResult {
  final AnalyticsPeriod period;
  final DriverPerformanceDelivery deliveryPerformance;
  final DriverPerformanceRatings ratings;
  final DriverPerformanceShifts shifts;
  final DriverPerformanceMlScore? mlPerformanceScore;
  final AnalyticsInsights insights;

  const DriverPerformanceAnalyticsResult({
    required this.period,
    required this.deliveryPerformance,
    required this.ratings,
    required this.shifts,
    this.mlPerformanceScore,
    required this.insights,
  });

  factory DriverPerformanceAnalyticsResult.fromJson(Map<String, dynamic> json) {
    return DriverPerformanceAnalyticsResult(
      period: AnalyticsPeriod.fromJson(json['period']),
      deliveryPerformance:
          DriverPerformanceDelivery.fromJson(json['delivery_performance']),
      ratings: DriverPerformanceRatings.fromJson(json['ratings']),
      shifts: DriverPerformanceShifts.fromJson(json['shifts']),
      mlPerformanceScore: json['ml_performance_score'] != null
          ? DriverPerformanceMlScore.fromJson(json['ml_performance_score'])
          : null,
      insights: List<String>.from(json['insights'] ?? []),
    );
  }
}
```

---

### Driver Analytics Service

```dart
class DriverAnalyticsService {
  final String baseUrl;
  final String Function() getToken;

  const DriverAnalyticsService({
    required this.baseUrl,
    required this.getToken,
  });

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${getToken()}',
      };

  Uri _uri(String path, [Map<String, String>? params]) {
    final uri = Uri.parse('$baseUrl/api/delivery/driver/analytics$path');
    return params != null ? uri.replace(queryParameters: params) : uri;
  }

  Map<String, String> _periodParams({String? period, String? from, String? to}) {
    final p = <String, String>{};
    if (period != null) p['period'] = period;
    if (from != null) p['from'] = from;
    if (to != null) p['to'] = to;
    return p;
  }

  // ── Overview ────────────────────────────────────────────────────────────────

  Future<DriverOverviewResult> getOverview({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/overview/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return DriverOverviewResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getOverview failed: ${res.body}');
  }

  // ── Earnings ────────────────────────────────────────────────────────────────

  Future<DriverEarningsAnalyticsResult> getEarningsAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/earnings/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return DriverEarningsAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getEarningsAnalytics failed: ${res.body}');
  }

  // ── Performance ─────────────────────────────────────────────────────────────

  Future<DriverPerformanceAnalyticsResult> getPerformanceAnalytics({
    String? period,
    String? from,
    String? to,
  }) async {
    final res = await http.get(
      _uri('/performance/', _periodParams(period: period, from: from, to: to)),
      headers: _headers,
    );
    if (res.statusCode == 200) {
      return DriverPerformanceAnalyticsResult.fromJson(jsonDecode(res.body));
    }
    throw Exception('getPerformanceAnalytics failed: ${res.body}');
  }
}
```

---

## Endpoint Reference

### Admin — `/api/platform-admin/analytics/`

| Method | Endpoint | Response model | Insights |
|--------|----------|----------------|---------|
| `GET` | `/overview/` | `AdminOverviewResult` | ✅ |
| `GET` | `/customers/` | `AdminCustomerAnalyticsResult` | ✅ |
| `GET` | `/orders/` | `AdminOrderAnalyticsResult` | ✅ |
| `GET` | `/payments/` | `AdminPaymentAnalyticsResult` | ✅ |
| `GET` | `/products/` | `AdminProductAnalyticsResult` | — |
| `GET` | `/categories/` | `AdminCategoryAnalyticsResult` | — |
| `GET` | `/negotiations/` | `AdminNegotiationAnalyticsResult` | ✅ |
| `GET` | `/debit/` | `AdminDebitAnalyticsResult` | ✅ |
| `GET` | `/deliveries/` | `AdminDeliveryAnalyticsResult` | ✅ |
| `GET` | `/drivers/` | `AdminDriverAnalyticsResult` | ✅ |
| `GET` | `/payouts/` | `AdminPayoutAnalyticsResult` | ✅ |
| `GET` | `/subaccounts/` | `AdminSubaccountAnalyticsResult` | — |
| `GET` | `/subscriptions/` | `AdminSubscriptionAnalyticsResult` | ✅ |

### Vendor — `/api/business/analytics/`

| Method | Endpoint | Response model | Insights |
|--------|----------|----------------|---------|
| `GET` | `/overview/` | `VendorOverviewResult` | ✅ |
| `GET` | `/orders/` | `VendorOrderAnalyticsResult` | — |
| `GET` | `/products/` | `VendorProductAnalyticsResult` | ✅ |
| `GET` | `/customers/` | `VendorCustomerAnalyticsResult` | — |
| `GET` | `/negotiations/` | `VendorNegotiationAnalyticsResult` | ✅ |
| `GET` | `/payments/` | `VendorPaymentAnalyticsResult` | — |

### Driver — `/api/delivery/driver/analytics/`

| Method | Endpoint | Response model | Insights |
|--------|----------|----------------|---------|
| `GET` | `/overview/` | `DriverOverviewResult` | ✅ |
| `GET` | `/earnings/` | `DriverEarningsAnalyticsResult` | ✅ |
| `GET` | `/performance/` | `DriverPerformanceAnalyticsResult` | ✅ |

---

## Response Bodies

### `insights` field

Every response includes an `insights` key at the top level — an array of human-readable strings generated from the computed metrics. Each string is prefixed with an emoji for easy display.

```json
{
  "insights": [
    "📈 Revenue is up 23% vs the previous period.",
    "⚠️ 3 high-churn-risk customers identified — consider targeted retention offers.",
    "✅ Order completion rate is strong at 89%."
  ]
}
```

When no insights are applicable the field is an empty array `[]`, never `null`.

---

### `GET /api/platform-admin/analytics/overview/`

```json
{
  "period": { "start": "2026-04-23T00:00:00Z", "end": "2026-05-23T00:00:00Z" },
  "revenue": {
    "total": "284500.00",
    "previous_period": "231000.00",
    "growth_percent": 23.16
  },
  "orders": { "total": 1420, "completed": 1268, "cancelled": 89 },
  "users": {
    "total_customers": 3841,
    "total_vendors": 112,
    "total_drivers": 58,
    "new_customers": 204,
    "new_vendors": 7
  },
  "transactions": { "total": 1587, "total_value": "284500.00" },
  "deliveries": { "total": 1268, "completed": 1180 },
  "daily_snapshots": [
    {
      "date": "2026-05-22",
      "total_revenue": "12400.00",
      "total_orders": 62,
      "total_transactions": 69,
      "new_customers": 9,
      "completed_deliveries": 55
    }
  ],
  "insights": ["📈 Revenue grew 23% vs previous period.", "👥 204 new customers joined this month."]
}
```

---

### `GET /api/platform-admin/analytics/customers/`

```json
{
  "period": { "start": "...", "end": "..." },
  "totals": {
    "total_customers": 3841,
    "new_customers": 204,
    "suspended": 12,
    "verified": 3100
  },
  "churn_risk": {
    "low": 2901,
    "medium": 730,
    "high": 210,
    "note": "Computed weekly via Scikit-learn rule-based model"
  },
  "spending": { "total": "284500.00", "average_order_value": "215.40" },
  "loyalty": { "total_points_issued": 412000, "avg_points_per_customer": 107.3 },
  "top_spenders": [
    { "user__email": "buyer@example.com", "user__id": 42, "total_spend": "8200.00", "order_count": 38 }
  ],
  "insights": ["⚠️ 210 customers are high churn risk.", "🏆 Top spender made 38 orders this period."]
}
```

---

### `GET /api/platform-admin/analytics/orders/`

```json
{
  "period": { "start": "...", "end": "..." },
  "totals": {
    "total_orders": 1420,
    "total_revenue": "284500.00",
    "avg_order_value": "200.35",
    "completed": 1268,
    "cancelled": 89,
    "refunded": 23
  },
  "status_breakdown": [
    { "status": "delivered", "count": 1180, "revenue": "234000.00" },
    { "status": "cancelled", "count": 89, "revenue": "0.00" }
  ],
  "payment_status_breakdown": [
    { "payment_status": "paid", "count": 1350 },
    { "payment_status": "pending", "count": 45 }
  ],
  "fulfillment_split": [
    { "fulfillment_type": "delivery", "count": 1100 },
    { "fulfillment_type": "pickup", "count": 320 }
  ],
  "top_vendors_by_revenue": [
    {
      "vendor__id": 5,
      "vendor__name": "FreshMart",
      "vendor__trading_name": "FreshMart SA",
      "order_count": 210,
      "revenue": "42000.00"
    }
  ],
  "daily_breakdown": [
    { "day": "2026-05-22", "count": 62, "revenue": "12400.00" }
  ],
  "insights": ["✅ 89.3% of orders completed successfully.", "📦 1100 of 1420 orders were delivery."]
}
```

---

### `GET /api/platform-admin/analytics/payments/`

```json
{
  "period": { "start": "...", "end": "..." },
  "transactions": {
    "total": 1587,
    "successful": 1520,
    "success_rate_percent": 95.78,
    "total_revenue": "284500.00",
    "paystack_fees": "5690.00",
    "net_revenue": "278810.00"
  },
  "refunds": { "count": 23, "total_amount": "4600.00" },
  "disputes": { "count": 5, "total_amount": "1250.00" },
  "by_status": [
    { "status": "success", "count": 1520, "total": "284500.00" },
    { "status": "failed", "count": 67, "total": "0.00" }
  ],
  "by_channel": [
    { "channel": "card", "count": 980, "total": "196000.00" },
    { "channel": "bank_transfer", "count": 540, "total": "88500.00" }
  ],
  "by_intent": [
    { "payment_intent": "order_payment", "count": 1420, "total": "284500.00" }
  ],
  "insights": ["✅ 95.78% transaction success rate.", "💰 R278,810 net after Paystack fees."]
}
```

---

### `GET /api/platform-admin/analytics/negotiations/`

```json
{
  "period": { "start": "...", "end": "..." },
  "totals": {
    "total_negotiations": 320,
    "agreed": 240,
    "expired": 50,
    "cancelled": 10,
    "open": 20,
    "agreement_rate_percent": 75.0
  },
  "avg_rounds_to_agreement": 2.8,
  "agreed_price_total": "48000.00",
  "mode_breakdown": [
    { "mode": "ai", "count": 220 },
    { "mode": "manual", "count": 100 }
  ],
  "status_breakdown": [
    { "status": "agreed", "count": 240 },
    { "status": "expired", "count": 50 }
  ],
  "ai_performance": { "total": 220, "agreed": 176, "agreement_rate_percent": 80.0 },
  "manual_performance": { "total": 100, "agreed": 64, "agreement_rate_percent": 64.0 },
  "insights": ["🤖 AI negotiations close 16% more often than manual.", "✅ 75% overall agreement rate."]
}
```

---

### `GET /api/platform-admin/analytics/debit/`

```json
{
  "period": { "start": "...", "end": "..." },
  "accounts": {
    "total": 580,
    "active": 490,
    "suspended": 32,
    "closed": 58,
    "status_breakdown": [{ "status": "active", "count": 490 }]
  },
  "balances": {
    "total_credit_limit": "2900000.00",
    "total_outstanding_balance": "1840000.00",
    "total_penalties": "23400.00"
  },
  "purchases": {
    "count": 124,
    "total_credit_issued": "310000.00",
    "total_purchase_value": "310000.00",
    "overdue_count": 18,
    "status_breakdown": [{ "status": "active", "count": 100 }]
  },
  "repayments": { "count": 98, "total_repaid": "248000.00" },
  "insights": ["⚠️ 18 purchases are overdue.", "💳 63% of outstanding credit has been repaid."]
}
```

---

### `GET /api/platform-admin/analytics/deliveries/`

```json
{
  "period": { "start": "...", "end": "..." },
  "totals": {
    "total_deliveries": 1268,
    "completed": 1180,
    "failed": 42,
    "pending": 20,
    "in_transit": 26,
    "completion_rate_percent": 93.06
  },
  "performance": {
    "avg_distance_km": 8.4,
    "total_fare_collected": "88760.00",
    "avg_fare": "70.00",
    "avg_delivery_time_mins": 38.2
  },
  "ratings": { "avg_driver_rating": 4.6, "total_ratings": 1100 },
  "status_breakdown": [
    { "status": "delivered", "count": 1180 },
    { "status": "cancelled", "count": 42 }
  ],
  "insights": ["🚀 93% delivery completion rate.", "⭐ Average driver rating 4.6/5."]
}
```

---

### `GET /api/platform-admin/analytics/drivers/`

```json
{
  "period": { "start": "...", "end": "..." },
  "totals": {
    "total_drivers": 58,
    "available": 34,
    "approved": 51,
    "pending_verification": 7,
    "avg_rating": 4.6
  },
  "ml_performance": {
    "grade_distribution": [
      { "grade": "A", "count": 12 },
      { "grade": "B", "count": 23 },
      { "grade": "C", "count": 15 },
      { "grade": "D", "count": 6 },
      { "grade": "F", "count": 2 }
    ],
    "payout_anomaly_flagged": 3,
    "note": "Computed weekly via Scikit-learn composite scoring"
  },
  "top_drivers": [
    {
      "driver__user__email": "driver@example.com",
      "score": 94.2,
      "grade": "A",
      "total_deliveries": 820,
      "avg_rating": 4.9,
      "completion_rate": 0.98
    }
  ],
  "vehicle_breakdown": [
    { "vehicle_type": "motorbike", "count": 38 },
    { "vehicle_type": "car", "count": 20 }
  ],
  "verification_breakdown": [
    { "background_check_status": "approved", "count": 51 }
  ],
  "insights": ["⚠️ 3 drivers flagged for payout anomaly.", "🏆 12 drivers rated Grade A this week."]
}
```

---

### `GET /api/platform-admin/analytics/payouts/`

```json
{
  "period": { "start": "...", "end": "..." },
  "payouts": {
    "count": 58,
    "total_gross": "88760.00",
    "total_commission": "13314.00",
    "total_net_paid": "75446.00",
    "pending": "4200.00"
  },
  "earnings": {
    "total_gross": "88760.00",
    "platform_commission": "13314.00",
    "driver_net": "75446.00"
  },
  "status_breakdown": [
    { "status": "paid", "count": 51, "total": "70000.00" },
    { "status": "pending", "count": 7, "total": "5446.00" }
  ],
  "top_earners": [
    { "driver__user__email": "driver@example.com", "total": "4800.00", "jobs": 68 }
  ],
  "insights": ["💵 R75,446 net paid to drivers this period.", "📋 7 payouts pending processing."]
}
```

---

### `GET /api/platform-admin/analytics/subscriptions/`

```json
{
  "period": { "start": "2026-04-23T00:00:00Z", "end": "2026-05-23T00:00:00Z" },

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
      { "status": "active", "count": 380 },
      { "status": "trialing", "count": 15 },
      { "status": "cancelled", "count": 18 },
      { "status": "expired", "count": 5 },
      { "status": "past_due", "count": 2 }
    ],
    "plan_breakdown": [
      {
        "plan__id": "uuid-here",
        "plan__name": "Premium",
        "plan__slug": "premium",
        "plan__plan_tier": "premium",
        "plan__price": "149.00",
        "plan__billing_cycle": "monthly",
        "subscriber_count": 210
      },
      {
        "plan__id": "uuid-here",
        "plan__name": "Basic",
        "plan__slug": "basic",
        "plan__plan_tier": "basic",
        "plan__price": "49.00",
        "plan__billing_cycle": "monthly",
        "subscriber_count": 170
      }
    ],
    "plans_catalogue": [
      {
        "id": "uuid-here",
        "name": "Basic",
        "slug": "basic",
        "plan_tier": "basic",
        "price": "49.00",
        "billing_cycle": "monthly",
        "credit_limit": "500.00",
        "trial_days": 7
      },
      {
        "id": "uuid-here",
        "name": "Premium",
        "slug": "premium",
        "plan_tier": "premium",
        "price": "149.00",
        "billing_cycle": "monthly",
        "credit_limit": "2000.00",
        "trial_days": 14
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
      { "status": "active", "count": 98 },
      { "status": "trialing", "count": 4 },
      { "status": "cancelled", "count": 7 }
    ],
    "tier_breakdown": [
      {
        "tier__id": "uuid-here",
        "tier__name": "Growth",
        "tier__slug": "growth",
        "tier__tier_level": 1,
        "tier__price": "299.00",
        "tier__commission_rate": "10.00",
        "vendor_count": 60
      },
      {
        "tier__id": "uuid-here",
        "tier__name": "Pro",
        "tier__slug": "pro",
        "tier__tier_level": 2,
        "tier__price": "599.00",
        "tier__commission_rate": "8.00",
        "vendor_count": 38
      }
    ],
    "tiers_catalogue": [
      {
        "id": "uuid-here",
        "name": "Starter",
        "slug": "starter",
        "tier_level": 0,
        "price": "0.00",
        "commission_rate": "12.00",
        "max_products": 20,
        "negotiation_enabled": false,
        "trial_days": 0
      },
      {
        "id": "uuid-here",
        "name": "Growth",
        "slug": "growth",
        "tier_level": 1,
        "price": "299.00",
        "commission_rate": "10.00",
        "max_products": 100,
        "negotiation_enabled": true,
        "trial_days": 14
      }
    ]
  },

  "combined": {
    "total_paying_subscribers": 478,
    "combined_mrr": "51500.00",
    "combined_revenue_this_period": "13920.00",
    "new_this_period": 43,
    "cancellations_this_period": 8
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

### `GET /api/business/analytics/overview/`

```json
{
  "period": { "start": "...", "end": "..." },
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
  "insights": ["📈 Revenue up 22.8% vs previous period.", "🥇 Your vendor tier is Gold — keep it up!"]
}
```

---

### `GET /api/business/analytics/negotiations/`

```json
{
  "period": { "start": "...", "end": "..." },
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
    { "status": "agreed", "count": 38 },
    { "status": "expired", "count": 7 }
  ],
  "mode_breakdown": [
    { "mode": "ai", "count": 35 },
    { "mode": "manual", "count": 13 }
  ],
  "insights": ["✅ 79.2% of your negotiations ended in agreement.", "🤖 35 of 48 negotiations used AI mode."]
}
```

---

### `GET /api/delivery/driver/analytics/overview/`

```json
{
  "period": { "start": "...", "end": "..." },
  "deliveries": {
    "total": 68,
    "completed": 64,
    "failed": 2,
    "in_transit": 2,
    "completion_rate_percent": 94.12
  },
  "earnings": {
    "gross": "4896.00",
    "platform_commission": "734.40",
    "net": "4161.60"
  },
  "rating": 4.8,
  "total_deliveries_all_time": 820,
  "performance_score": {
    "score": 94.2,
    "grade": "A",
    "completion_rate": 0.96,
    "on_time_rate": 0.89,
    "avg_delivery_time_mins": 34.5,
    "payout_anomaly": false,
    "scored_at": "2026-05-19T02:00:00Z"
  },
  "insights": ["🏆 Grade A performance — excellent work!", "✅ 94% completion rate this month."]
}
```

---

### `GET /api/delivery/driver/analytics/performance/`

```json
{
  "period": { "start": "...", "end": "..." },
  "delivery_performance": {
    "total_jobs": 68,
    "completed": 64,
    "failed": 2,
    "avg_delivery_time_mins": 34.5,
    "on_time_rate_percent": 89.06,
    "avg_distance_km": 7.2
  },
  "ratings": {
    "avg_rating": 4.8,
    "total_ratings": 61,
    "all_time_avg": 4.8
  },
  "shifts": {
    "total_shifts": 22,
    "total_hours_online": 88.5
  },
  "ml_performance_score": {
    "score": 94.2,
    "grade": "A",
    "payout_anomaly": false,
    "model_version": "sklearn-rule-v1",
    "scored_at": "2026-05-19T02:00:00Z"
  },
  "insights": ["⏱️ Average delivery time is 34.5 mins — well within target.", "⭐ 4.8/5 average rating this period."]
}
```

---

## ML Score Reference

### Vendor Performance Tiers

| Tier | Score range | Meaning |
|------|-------------|---------|
| `platinum` | 80 – 100 | Exceptional performance |
| `gold` | 65 – 79 | Strong, reliable vendor |
| `silver` | 45 – 64 | Average performance |
| `bronze` | 0 – 44 | Needs improvement |

Score is computed weekly from: completion rate (×30), refund rate (−×20), dispute rate (−×20), order volume (×15), recency (×10), negotiation agreement rate (×5).

---

### Driver Performance Grades

| Grade | Score range |
|-------|-------------|
| `A` | 90 – 100 |
| `B` | 75 – 89 |
| `C` | 60 – 74 |
| `D` | 40 – 59 |
| `F` | 0 – 39 |

Score is computed weekly from: completion rate (×35), average rating (×30), on-time rate (×25), delivery volume (×10), minus 10 if payout anomaly is detected.

---

### Customer Churn Risk

| Segment | Churn probability | Action |
|---------|-------------------|--------|
| `low` | < 30% | No action needed |
| `medium` | 30 – 59% | Consider a retention offer |
| `high` | ≥ 60% | Priority re-engagement |

Computed weekly from: recency (days since last order), subscription status, loyalty points, order count, average order value.

---

## Error Responses

| Status | Body | Cause |
|--------|------|-------|
| `401` | `{"detail": "Authentication credentials were not provided."}` | Missing or expired token |
| `403` | `{"detail": "Forbidden."}` | Token does not belong to the required role |
| `403` | `{"detail": "Vendor profile required."}` | User has no vendor profile |
| `403` | `{"detail": "Driver profile required."}` | User has no driver profile |
