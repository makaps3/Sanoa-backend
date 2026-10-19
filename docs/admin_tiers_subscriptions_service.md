# Admin Tiers & Subscriptions Service

**Dart / Flutter Reference — Platform Admin Only**
**Base URL:** `/api/`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Vendor Tiers Admin Endpoints](#2-vendor-tiers-admin-endpoints)
3. [Customer Plans Admin Endpoints](#3-customer-plans-admin-endpoints)
4. [Dart Models](#4-dart-models)
5. [AdminTiersSubscriptionsService](#5-admintierssubscriptionsservice)

---

## 1. Overview

All endpoints in this document require a **platform admin** JWT token (user with an `AdminProfile`).

| Prefix | Manages |
|--------|---------|
| `/api/tiers/admin/` | Vendor business tiers and vendor tier subscriptions |
| `/api/subscriptions/admin/` | Customer credit plans and customer subscriptions |

---

## 2. Vendor Tiers Admin Endpoints

### 2.1 Business Tiers CRUD

#### `GET /api/tiers/admin/plans/`
List all business tiers (including inactive).

**Query params:** none

**Response 200**
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "name": "Starter",
      "slug": "starter",
      "description": "Basic vendor tier",
      "price": "0.00",
      "tier_level": 1,
      "duration": 30,
      "duration_unit": "days",
      "max_products": 20,
      "product_limit_display": "20 products",
      "commission_rate": "5.00",
      "search_priority_boost": 0,
      "featured_listings": false,
      "features": {},
      "negotiation_enabled": false,
      "max_markup_percent": "10.00",
      "max_discount_percent": "5.00",
      "trial_days": 0,
      "is_free": true,
      "is_active": true,
      "sort_order": 1,
      "paystack_plan_code": null,
      "paystack_plan_id": null,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

#### `POST /api/tiers/admin/plans/`
Create a new business tier.

**Request body**
```json
{
  "name": "Pro",
  "slug": "pro",
  "description": "Pro vendor tier",
  "price": "299.00",
  "tier_level": 2,
  "duration": 1,
  "duration_unit": "months",
  "max_products": 100,
  "commission_rate": "3.50",
  "search_priority_boost": 2,
  "featured_listings": true,
  "features": {"analytics": true, "priority_support": true},
  "negotiation_enabled": true,
  "max_markup_percent": "25.00",
  "max_discount_percent": "15.00",
  "trial_days": 7,
  "is_active": true,
  "sort_order": 2
}
```

**Response 201** — same shape as GET item above.

---

#### `GET /api/tiers/admin/plans/{id}/`
Retrieve a single tier by UUID.

**Response 200** — same shape as list item.

---

#### `PUT /api/tiers/admin/plans/{id}/`
Full update of a tier.

#### `PATCH /api/tiers/admin/plans/{id}/`
Partial update of a tier.

#### `DELETE /api/tiers/admin/plans/{id}/`
Delete a tier.

**Response 204** — no content.

---

#### `POST /api/tiers/admin/plans/{id}/toggle-active/`
Toggle the `is_active` flag.

**Response 200** — full tier object with updated `is_active`.

---

#### `POST /api/tiers/admin/plans/{id}/sync-paystack/`
Create or update this tier on Paystack. Free tiers return an error.

**Response 200**
```json
{
  "message": "Tier synced to Paystack.",
  "paystack_plan_code": "PLN_xxxxxxxxxxxx"
}
```

**Response 400 (free tier)**
```json
{"error": "Free tiers do not need Paystack plans."}
```

---

### 2.2 Vendor Tier Subscriptions

#### `GET /api/tiers/admin/subscriptions/`
List all vendor tier subscriptions.

**Query params:**
- `status` — filter by status: `active`, `trialing`, `cancelled`, `expired`, `past_due`
- `tier` — filter by tier UUID

**Response 200**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "vendor": "vendor-uuid",
      "vendor_email": "vendor@example.com",
      "vendor_name": "Acme Store",
      "tier": "tier-uuid",
      "tier_name": "Pro",
      "tier_price": "299.00",
      "tier_level": 2,
      "status": "active",
      "is_active": true,
      "started_at": "2025-01-01T00:00:00Z",
      "current_period_start": "2025-01-01T00:00:00Z",
      "current_period_end": "2025-02-01T00:00:00Z",
      "cancelled_at": null,
      "paystack_subscription_code": "SUB_xxxxxxxxxxxx",
      "paystack_customer_code": "CUS_xxxxxxxxxxxx",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

#### `GET /api/tiers/admin/subscriptions/{id}/`
Retrieve a single vendor tier subscription.

**Response 200** — same shape as list item.

---

#### `POST /api/tiers/admin/subscriptions/{id}/cancel/`
Force-cancel a vendor tier subscription. Also disables on Paystack if linked.

**Response 200** — full subscription object with `status: "cancelled"`.

**Response 400**
```json
{"error": "Already cancelled."}
```

---

#### `POST /api/tiers/admin/subscriptions/assign/`
Directly assign a tier to a vendor (bypasses Paystack payment).

**Request body**
```json
{
  "vendor_id": "vendor-profile-uuid",
  "tier_id": "tier-uuid",
  "status": "active"
}
```

`status` choices: `active`, `trialing`, `cancelled`, `expired`, `past_due` (default: `active`)

**Response 201**
```json
{
  "id": "uuid",
  "vendor": "vendor-uuid",
  "vendor_email": "vendor@example.com",
  "vendor_name": "Acme Store",
  "tier": "tier-uuid",
  "tier_name": "Pro",
  "tier_price": "299.00",
  "tier_level": 2,
  "status": "active",
  "is_active": true,
  "started_at": "2025-01-01T00:00:00Z",
  "current_period_start": "2025-01-01T00:00:00Z",
  "current_period_end": "2025-02-01T00:00:00Z",
  "cancelled_at": null,
  "paystack_subscription_code": null,
  "paystack_customer_code": null,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

## 3. Customer Plans Admin Endpoints

### 3.1 Credit Plans CRUD

#### `GET /api/subscriptions/admin/plans/`
List all credit plans (including inactive).

**Response 200**
```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "name": "Basic Credit",
      "slug": "basic-credit",
      "description": "Entry-level buyer credit plan",
      "plan_tier": "basic",
      "billing_cycle": "monthly",
      "price": "99.00",
      "duration": 1,
      "duration_unit": "months",
      "credit_limit": "2000.00",
      "interest_rate": "5.00",
      "deposit_percent": "10.00",
      "max_items_on_credit": 5,
      "repayment_days": 30,
      "grace_period_days": 3,
      "late_payment_penalty_percent": "2.00",
      "service_fee_discount_percent": "0.00",
      "delivery_fee_discount_percent": "0.00",
      "features": {},
      "requires_follower": false,
      "trial_days": 0,
      "sort_order": 1,
      "is_active": true,
      "paystack_plan_code": "PLN_xxxxxxxxxxxx",
      "paystack_plan_id": 12345,
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

#### `POST /api/subscriptions/admin/plans/`
Create a new credit plan.

**Request body**
```json
{
  "name": "Premium Credit",
  "slug": "premium-credit",
  "description": "Premium buyer credit plan",
  "plan_tier": "premium",
  "billing_cycle": "monthly",
  "price": "299.00",
  "duration": 1,
  "duration_unit": "months",
  "credit_limit": "10000.00",
  "interest_rate": "3.00",
  "deposit_percent": "5.00",
  "max_items_on_credit": 20,
  "repayment_days": 30,
  "grace_period_days": 5,
  "late_payment_penalty_percent": "1.50",
  "service_fee_discount_percent": "10.00",
  "delivery_fee_discount_percent": "5.00",
  "features": {"priority_delivery": true},
  "requires_follower": false,
  "trial_days": 14,
  "sort_order": 2,
  "is_active": true
}
```

**Response 201** — same shape as GET item above.

---

#### `GET /api/subscriptions/admin/plans/{id}/`
Retrieve a single plan.

#### `PUT /api/subscriptions/admin/plans/{id}/`
Full update.

#### `PATCH /api/subscriptions/admin/plans/{id}/`
Partial update.

#### `DELETE /api/subscriptions/admin/plans/{id}/`
Delete a plan. **Response 204.**

---

#### `POST /api/subscriptions/admin/plans/{id}/toggle-active/`
Toggle `is_active`.

**Response 200** — full plan object.

---

#### `POST /api/subscriptions/admin/plans/{id}/sync-paystack/`
Sync plan to Paystack.

**Response 200**
```json
{
  "message": "Plan synced to Paystack.",
  "paystack_plan_code": "PLN_xxxxxxxxxxxx"
}
```

---

### 3.2 Customer Subscriptions

#### `GET /api/subscriptions/admin/subscriptions/`
List all customer subscriptions.

**Query params:**
- `status` — `active`, `trialing`, `cancelled`, `expired`, `past_due`
- `plan` — filter by plan UUID

**Response 200**
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "user": 42,
      "user_email": "customer@example.com",
      "plan": "plan-uuid",
      "plan_name": "Basic Credit",
      "plan_price": "99.00",
      "plan_tier": "basic",
      "status": "active",
      "is_active": true,
      "started_at": "2025-01-01T00:00:00Z",
      "current_period_start": "2025-01-01T00:00:00Z",
      "current_period_end": "2025-02-01T00:00:00Z",
      "cancelled_at": null,
      "paystack_subscription_code": "SUB_xxxxxxxxxxxx",
      "paystack_customer_code": "CUS_xxxxxxxxxxxx",
      "created_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

---

#### `GET /api/subscriptions/admin/subscriptions/{id}/`
Retrieve a single subscription.

**Response 200** — same shape as list item.

---

#### `POST /api/subscriptions/admin/subscriptions/{id}/cancel/`
Force-cancel a customer subscription. Also disables on Paystack if linked.

**Response 200** — full subscription object with `status: "cancelled"`.

---

#### `POST /api/subscriptions/admin/subscriptions/assign/`
Directly assign a plan to a customer (bypasses Paystack).

**Request body**
```json
{
  "user_id": 42,
  "plan_id": "plan-uuid",
  "status": "active"
}
```

`status` choices: `active`, `trialing`, `cancelled`, `expired`, `past_due` (default: `active`)

**Response 201**
```json
{
  "id": "uuid",
  "user": 42,
  "user_email": "customer@example.com",
  "plan": "plan-uuid",
  "plan_name": "Basic Credit",
  "plan_price": "99.00",
  "plan_tier": "basic",
  "status": "active",
  "is_active": true,
  "started_at": "2025-01-01T00:00:00Z",
  "current_period_start": "2025-01-01T00:00:00Z",
  "current_period_end": "2025-02-01T00:00:00Z",
  "cancelled_at": null,
  "paystack_subscription_code": null,
  "paystack_customer_code": null,
  "created_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-01T00:00:00Z"
}
```

---

## 4. Dart Models

```dart
// ─── Vendor Tier (Admin) ─────────────────────────────────────────────────────

class AdminBusinessTier {
  final String id;
  final String name;
  final String slug;
  final String? description;
  final double price;
  final int tierLevel;
  final int duration;
  final String durationUnit;
  final int? maxProducts;
  final String? productLimitDisplay;
  final double commissionRate;
  final int searchPriorityBoost;
  final bool featuredListings;
  final Map<String, dynamic> features;
  final bool negotiationEnabled;
  final double maxMarkupPercent;
  final double maxDiscountPercent;
  final int trialDays;
  final bool isFree;
  final bool isActive;
  final int sortOrder;
  final String? payStackPlanCode;
  final int? payStackPlanId;
  final DateTime createdAt;
  final DateTime updatedAt;

  const AdminBusinessTier({
    required this.id,
    required this.name,
    required this.slug,
    this.description,
    required this.price,
    required this.tierLevel,
    required this.duration,
    required this.durationUnit,
    this.maxProducts,
    this.productLimitDisplay,
    required this.commissionRate,
    required this.searchPriorityBoost,
    required this.featuredListings,
    required this.features,
    required this.negotiationEnabled,
    required this.maxMarkupPercent,
    required this.maxDiscountPercent,
    required this.trialDays,
    required this.isFree,
    required this.isActive,
    required this.sortOrder,
    this.payStackPlanCode,
    this.payStackPlanId,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AdminBusinessTier.fromJson(Map<String, dynamic> json) => AdminBusinessTier(
    id: json['id'],
    name: json['name'],
    slug: json['slug'],
    description: json['description'],
    price: double.parse(json['price'].toString()),
    tierLevel: json['tier_level'],
    duration: json['duration'],
    durationUnit: json['duration_unit'],
    maxProducts: json['max_products'],
    productLimitDisplay: json['product_limit_display'],
    commissionRate: double.parse(json['commission_rate'].toString()),
    searchPriorityBoost: json['search_priority_boost'],
    featuredListings: json['featured_listings'],
    features: Map<String, dynamic>.from(json['features'] ?? {}),
    negotiationEnabled: json['negotiation_enabled'],
    maxMarkupPercent: double.parse(json['max_markup_percent'].toString()),
    maxDiscountPercent: double.parse(json['max_discount_percent'].toString()),
    trialDays: json['trial_days'],
    isFree: json['is_free'],
    isActive: json['is_active'],
    sortOrder: json['sort_order'] ?? 0,
    payStackPlanCode: json['paystack_plan_code'],
    payStackPlanId: json['paystack_plan_id'],
    createdAt: DateTime.parse(json['created_at']),
    updatedAt: DateTime.parse(json['updated_at']),
  );
}


// ─── Vendor Tier Subscription (Admin) ────────────────────────────────────────

class AdminVendorTierSubscription {
  final String id;
  final String vendor;
  final String vendorEmail;
  final String vendorName;
  final String tier;
  final String tierName;
  final double tierPrice;
  final int tierLevel;
  final String status;
  final bool isActive;
  final DateTime startedAt;
  final DateTime currentPeriodStart;
  final DateTime currentPeriodEnd;
  final DateTime? cancelledAt;
  final String? payStackSubscriptionCode;
  final String? payStackCustomerCode;
  final DateTime createdAt;
  final DateTime updatedAt;

  const AdminVendorTierSubscription({
    required this.id,
    required this.vendor,
    required this.vendorEmail,
    required this.vendorName,
    required this.tier,
    required this.tierName,
    required this.tierPrice,
    required this.tierLevel,
    required this.status,
    required this.isActive,
    required this.startedAt,
    required this.currentPeriodStart,
    required this.currentPeriodEnd,
    this.cancelledAt,
    this.payStackSubscriptionCode,
    this.payStackCustomerCode,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AdminVendorTierSubscription.fromJson(Map<String, dynamic> json) =>
      AdminVendorTierSubscription(
        id: json['id'],
        vendor: json['vendor'],
        vendorEmail: json['vendor_email'],
        vendorName: json['vendor_name'],
        tier: json['tier'],
        tierName: json['tier_name'],
        tierPrice: double.parse(json['tier_price'].toString()),
        tierLevel: json['tier_level'],
        status: json['status'],
        isActive: json['is_active'],
        startedAt: DateTime.parse(json['started_at']),
        currentPeriodStart: DateTime.parse(json['current_period_start']),
        currentPeriodEnd: DateTime.parse(json['current_period_end']),
        cancelledAt: json['cancelled_at'] != null
            ? DateTime.parse(json['cancelled_at'])
            : null,
        payStackSubscriptionCode: json['paystack_subscription_code'],
        payStackCustomerCode: json['paystack_customer_code'],
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
      );
}


// ─── Customer Credit Plan (Admin) ─────────────────────────────────────────────

class AdminPlan {
  final String id;
  final String name;
  final String slug;
  final String? description;
  final String planTier;
  final String billingCycle;
  final double price;
  final int duration;
  final String durationUnit;
  final double creditLimit;
  final double interestRate;
  final double depositPercent;
  final int maxItemsOnCredit;
  final int repaymentDays;
  final int gracePeriodDays;
  final double latePaymentPenaltyPercent;
  final double serviceFeeDiscountPercent;
  final double deliveryFeeDiscountPercent;
  final Map<String, dynamic> features;
  final bool requiresFollower;
  final int trialDays;
  final int sortOrder;
  final bool isActive;
  final String? payStackPlanCode;
  final int? payStackPlanId;
  final DateTime createdAt;
  final DateTime updatedAt;

  const AdminPlan({
    required this.id,
    required this.name,
    required this.slug,
    this.description,
    required this.planTier,
    required this.billingCycle,
    required this.price,
    required this.duration,
    required this.durationUnit,
    required this.creditLimit,
    required this.interestRate,
    required this.depositPercent,
    required this.maxItemsOnCredit,
    required this.repaymentDays,
    required this.gracePeriodDays,
    required this.latePaymentPenaltyPercent,
    required this.serviceFeeDiscountPercent,
    required this.deliveryFeeDiscountPercent,
    required this.features,
    required this.requiresFollower,
    required this.trialDays,
    required this.sortOrder,
    required this.isActive,
    this.payStackPlanCode,
    this.payStackPlanId,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AdminPlan.fromJson(Map<String, dynamic> json) => AdminPlan(
    id: json['id'],
    name: json['name'],
    slug: json['slug'],
    description: json['description'],
    planTier: json['plan_tier'],
    billingCycle: json['billing_cycle'],
    price: double.parse(json['price'].toString()),
    duration: json['duration'],
    durationUnit: json['duration_unit'],
    creditLimit: double.parse(json['credit_limit'].toString()),
    interestRate: double.parse(json['interest_rate'].toString()),
    depositPercent: double.parse(json['deposit_percent'].toString()),
    maxItemsOnCredit: json['max_items_on_credit'],
    repaymentDays: json['repayment_days'],
    gracePeriodDays: json['grace_period_days'],
    latePaymentPenaltyPercent:
        double.parse(json['late_payment_penalty_percent'].toString()),
    serviceFeeDiscountPercent:
        double.parse(json['service_fee_discount_percent'].toString()),
    deliveryFeeDiscountPercent:
        double.parse(json['delivery_fee_discount_percent'].toString()),
    features: Map<String, dynamic>.from(json['features'] ?? {}),
    requiresFollower: json['requires_follower'],
    trialDays: json['trial_days'],
    sortOrder: json['sort_order'] ?? 0,
    isActive: json['is_active'],
    payStackPlanCode: json['paystack_plan_code'],
    payStackPlanId: json['paystack_plan_id'],
    createdAt: DateTime.parse(json['created_at']),
    updatedAt: DateTime.parse(json['updated_at']),
  );
}


// ─── Customer Subscription (Admin) ────────────────────────────────────────────

class AdminCustomerSubscription {
  final String id;
  final int user;
  final String userEmail;
  final String plan;
  final String planName;
  final double planPrice;
  final String planTier;
  final String status;
  final bool isActive;
  final DateTime startedAt;
  final DateTime currentPeriodStart;
  final DateTime currentPeriodEnd;
  final DateTime? cancelledAt;
  final String? payStackSubscriptionCode;
  final String? payStackCustomerCode;
  final DateTime createdAt;
  final DateTime updatedAt;

  const AdminCustomerSubscription({
    required this.id,
    required this.user,
    required this.userEmail,
    required this.plan,
    required this.planName,
    required this.planPrice,
    required this.planTier,
    required this.status,
    required this.isActive,
    required this.startedAt,
    required this.currentPeriodStart,
    required this.currentPeriodEnd,
    this.cancelledAt,
    this.payStackSubscriptionCode,
    this.payStackCustomerCode,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AdminCustomerSubscription.fromJson(Map<String, dynamic> json) =>
      AdminCustomerSubscription(
        id: json['id'],
        user: json['user'],
        userEmail: json['user_email'],
        plan: json['plan'],
        planName: json['plan_name'],
        planPrice: double.parse(json['plan_price'].toString()),
        planTier: json['plan_tier'],
        status: json['status'],
        isActive: json['is_active'],
        startedAt: DateTime.parse(json['started_at']),
        currentPeriodStart: DateTime.parse(json['current_period_start']),
        currentPeriodEnd: DateTime.parse(json['current_period_end']),
        cancelledAt: json['cancelled_at'] != null
            ? DateTime.parse(json['cancelled_at'])
            : null,
        payStackSubscriptionCode: json['paystack_subscription_code'],
        payStackCustomerCode: json['paystack_customer_code'],
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
      );
}
```

---

## 5. AdminTiersSubscriptionsService

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

/// Service for platform admin to manage vendor tiers and customer credit plans.
/// Requires a valid admin JWT token — see PlatformAdminService for auth.
class AdminTiersSubscriptionsService {
  final String baseUrl;
  final String Function() getToken;

  AdminTiersSubscriptionsService({
    required this.baseUrl,
    required this.getToken,
  });

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ${getToken()}',
  };

  // ═══════════════════════════════════════════════════════════════
  // VENDOR TIERS
  // ═══════════════════════════════════════════════════════════════

  Future<List<AdminBusinessTier>> listTiers() async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/tiers/admin/plans/'),
      headers: _headers,
    );
    _checkStatus(res);
    final body = jsonDecode(res.body);
    final results = body['results'] as List;
    return results.map((e) => AdminBusinessTier.fromJson(e)).toList();
  }

  Future<AdminBusinessTier> getTier(String id) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/tiers/admin/plans/$id/'),
      headers: _headers,
    );
    _checkStatus(res);
    return AdminBusinessTier.fromJson(jsonDecode(res.body));
  }

  Future<AdminBusinessTier> createTier(Map<String, dynamic> data) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/tiers/admin/plans/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    _checkStatus(res);
    return AdminBusinessTier.fromJson(jsonDecode(res.body));
  }

  Future<AdminBusinessTier> updateTier(
      String id, Map<String, dynamic> data, {bool partial = true}) async {
    final method = partial ? http.patch : http.put;
    final res = await method(
      Uri.parse('$baseUrl/api/tiers/admin/plans/$id/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    _checkStatus(res);
    return AdminBusinessTier.fromJson(jsonDecode(res.body));
  }

  Future<void> deleteTier(String id) async {
    final res = await http.delete(
      Uri.parse('$baseUrl/api/tiers/admin/plans/$id/'),
      headers: _headers,
    );
    if (res.statusCode != 204) _checkStatus(res);
  }

  Future<AdminBusinessTier> toggleTierActive(String id) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/tiers/admin/plans/$id/toggle-active/'),
      headers: _headers,
    );
    _checkStatus(res);
    return AdminBusinessTier.fromJson(jsonDecode(res.body));
  }

  Future<String> syncTierToPaystack(String id) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/tiers/admin/plans/$id/sync-paystack/'),
      headers: _headers,
    );
    _checkStatus(res);
    final body = jsonDecode(res.body);
    return body['paystack_plan_code'] as String;
  }

  // ─── Vendor Tier Subscriptions ────────────────────────────────

  Future<List<AdminVendorTierSubscription>> listVendorSubscriptions({
    String? status,
    String? tierId,
  }) async {
    final params = <String, String>{};
    if (status != null) params['status'] = status;
    if (tierId != null) params['tier'] = tierId;

    final uri = Uri.parse('$baseUrl/api/tiers/admin/subscriptions/')
        .replace(queryParameters: params.isEmpty ? null : params);
    final res = await http.get(uri, headers: _headers);
    _checkStatus(res);
    final body = jsonDecode(res.body);
    final results = body['results'] as List;
    return results
        .map((e) => AdminVendorTierSubscription.fromJson(e))
        .toList();
  }

  Future<AdminVendorTierSubscription> getVendorSubscription(String id) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/tiers/admin/subscriptions/$id/'),
      headers: _headers,
    );
    _checkStatus(res);
    return AdminVendorTierSubscription.fromJson(jsonDecode(res.body));
  }

  Future<AdminVendorTierSubscription> cancelVendorSubscription(
      String id) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/tiers/admin/subscriptions/$id/cancel/'),
      headers: _headers,
    );
    _checkStatus(res);
    return AdminVendorTierSubscription.fromJson(jsonDecode(res.body));
  }

  Future<AdminVendorTierSubscription> assignTierToVendor({
    required String vendorId,
    required String tierId,
    String status = 'active',
  }) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/tiers/admin/subscriptions/assign/'),
      headers: _headers,
      body: jsonEncode({
        'vendor_id': vendorId,
        'tier_id': tierId,
        'status': status,
      }),
    );
    _checkStatus(res);
    return AdminVendorTierSubscription.fromJson(jsonDecode(res.body));
  }

  // ═══════════════════════════════════════════════════════════════
  // CUSTOMER CREDIT PLANS
  // ═══════════════════════════════════════════════════════════════

  Future<List<AdminPlan>> listPlans() async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/subscriptions/admin/plans/'),
      headers: _headers,
    );
    _checkStatus(res);
    final body = jsonDecode(res.body);
    final results = body['results'] as List;
    return results.map((e) => AdminPlan.fromJson(e)).toList();
  }

  Future<AdminPlan> getPlan(String id) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/subscriptions/admin/plans/$id/'),
      headers: _headers,
    );
    _checkStatus(res);
    return AdminPlan.fromJson(jsonDecode(res.body));
  }

  Future<AdminPlan> createPlan(Map<String, dynamic> data) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/subscriptions/admin/plans/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    _checkStatus(res);
    return AdminPlan.fromJson(jsonDecode(res.body));
  }

  Future<AdminPlan> updatePlan(
      String id, Map<String, dynamic> data, {bool partial = true}) async {
    final method = partial ? http.patch : http.put;
    final res = await method(
      Uri.parse('$baseUrl/api/subscriptions/admin/plans/$id/'),
      headers: _headers,
      body: jsonEncode(data),
    );
    _checkStatus(res);
    return AdminPlan.fromJson(jsonDecode(res.body));
  }

  Future<void> deletePlan(String id) async {
    final res = await http.delete(
      Uri.parse('$baseUrl/api/subscriptions/admin/plans/$id/'),
      headers: _headers,
    );
    if (res.statusCode != 204) _checkStatus(res);
  }

  Future<AdminPlan> togglePlanActive(String id) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/subscriptions/admin/plans/$id/toggle-active/'),
      headers: _headers,
    );
    _checkStatus(res);
    return AdminPlan.fromJson(jsonDecode(res.body));
  }

  Future<String> syncPlanToPaystack(String id) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/subscriptions/admin/plans/$id/sync-paystack/'),
      headers: _headers,
    );
    _checkStatus(res);
    final body = jsonDecode(res.body);
    return body['paystack_plan_code'] as String;
  }

  // ─── Customer Subscriptions ───────────────────────────────────

  Future<List<AdminCustomerSubscription>> listCustomerSubscriptions({
    String? status,
    String? planId,
  }) async {
    final params = <String, String>{};
    if (status != null) params['status'] = status;
    if (planId != null) params['plan'] = planId;

    final uri = Uri.parse('$baseUrl/api/subscriptions/admin/subscriptions/')
        .replace(queryParameters: params.isEmpty ? null : params);
    final res = await http.get(uri, headers: _headers);
    _checkStatus(res);
    final body = jsonDecode(res.body);
    final results = body['results'] as List;
    return results
        .map((e) => AdminCustomerSubscription.fromJson(e))
        .toList();
  }

  Future<AdminCustomerSubscription> getCustomerSubscription(String id) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/subscriptions/admin/subscriptions/$id/'),
      headers: _headers,
    );
    _checkStatus(res);
    return AdminCustomerSubscription.fromJson(jsonDecode(res.body));
  }

  Future<AdminCustomerSubscription> cancelCustomerSubscription(
      String id) async {
    final res = await http.post(
      Uri.parse(
          '$baseUrl/api/subscriptions/admin/subscriptions/$id/cancel/'),
      headers: _headers,
    );
    _checkStatus(res);
    return AdminCustomerSubscription.fromJson(jsonDecode(res.body));
  }

  Future<AdminCustomerSubscription> assignPlanToCustomer({
    required int userId,
    required String planId,
    String status = 'active',
  }) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/subscriptions/admin/subscriptions/assign/'),
      headers: _headers,
      body: jsonEncode({
        'user_id': userId,
        'plan_id': planId,
        'status': status,
      }),
    );
    _checkStatus(res);
    return AdminCustomerSubscription.fromJson(jsonDecode(res.body));
  }

  // ─── Helpers ─────────────────────────────────────────────────

  void _checkStatus(http.Response res) {
    if (res.statusCode >= 400) {
      final body = jsonDecode(res.body);
      final message = body['detail'] ?? body['error'] ?? body.toString();
      throw Exception('API error ${res.statusCode}: $message');
    }
  }
}
```

---

## Quick Reference

| Method | Endpoint | Service call |
|--------|----------|--------------|
| `GET` | `/api/tiers/admin/plans/` | `listTiers()` |
| `POST` | `/api/tiers/admin/plans/` | `createTier(data)` |
| `GET` | `/api/tiers/admin/plans/{id}/` | `getTier(id)` |
| `PATCH` | `/api/tiers/admin/plans/{id}/` | `updateTier(id, data)` |
| `DELETE` | `/api/tiers/admin/plans/{id}/` | `deleteTier(id)` |
| `POST` | `/api/tiers/admin/plans/{id}/toggle-active/` | `toggleTierActive(id)` |
| `POST` | `/api/tiers/admin/plans/{id}/sync-paystack/` | `syncTierToPaystack(id)` |
| `GET` | `/api/tiers/admin/subscriptions/` | `listVendorSubscriptions(...)` |
| `GET` | `/api/tiers/admin/subscriptions/{id}/` | `getVendorSubscription(id)` |
| `POST` | `/api/tiers/admin/subscriptions/{id}/cancel/` | `cancelVendorSubscription(id)` |
| `POST` | `/api/tiers/admin/subscriptions/assign/` | `assignTierToVendor(...)` |
| `GET` | `/api/subscriptions/admin/plans/` | `listPlans()` |
| `POST` | `/api/subscriptions/admin/plans/` | `createPlan(data)` |
| `GET` | `/api/subscriptions/admin/plans/{id}/` | `getPlan(id)` |
| `PATCH` | `/api/subscriptions/admin/plans/{id}/` | `updatePlan(id, data)` |
| `DELETE` | `/api/subscriptions/admin/plans/{id}/` | `deletePlan(id)` |
| `POST` | `/api/subscriptions/admin/plans/{id}/toggle-active/` | `togglePlanActive(id)` |
| `POST` | `/api/subscriptions/admin/plans/{id}/sync-paystack/` | `syncPlanToPaystack(id)` |
| `GET` | `/api/subscriptions/admin/subscriptions/` | `listCustomerSubscriptions(...)` |
| `GET` | `/api/subscriptions/admin/subscriptions/{id}/` | `getCustomerSubscription(id)` |
| `POST` | `/api/subscriptions/admin/subscriptions/{id}/cancel/` | `cancelCustomerSubscription(id)` |
| `POST` | `/api/subscriptions/admin/subscriptions/assign/` | `assignPlanToCustomer(...)` |
