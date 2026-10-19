# Sanoa Debit API (Buy Now Pay Later) - Complete Documentation

> **Base URL:** `https://your-domain.com/api/debit/`
>
> **Authentication:** JWT Bearer Token
>
> **Header:** `Authorization: Bearer <access_token>`
>
> **Currency:** ZAR (South African Rand)

---

## Table of Contents

1. [Debit Account](#1-debit-account)
2. [Eligibility Check](#2-eligibility-check)
3. [Debit Purchases](#3-debit-purchases)
4. [Repayments](#4-repayments)
5. [Dart Models](#5-dart-models)
6. [Dart API Service](#6-dart-api-service)

---

## 1. Debit Account

### 1.1 Get Current User Debit Account

```
GET /api/debit/account/
```

**Auth:** Required (authenticated user)

**Response `200 OK`:**

```json
{
  "id": 12,
  "user_email": "customer@example.com",
  "status": "active",
  "credit_limit": "2000.00",
  "current_balance": "550.00",
  "available_credit": "1450.00",
  "created_at": "2026-03-01T09:00:00Z",
  "updated_at": "2026-03-20T10:10:00Z"
}
```

Properties:
- `credit_limit`: max amount user can owe
- `current_balance`: total owed
- `available_credit`: `credit_limit - current_balance`
- `status`: `active | suspended | closed`

---

## 2. Eligibility Check

### 2.1 Check Vendor Eligibility

```
POST /api/debit/eligibility/
```

**Auth:** Required

**Body:**

```json
{
  "vendor_id": 123
}
```

**Response `200 OK`:**

```json
{
  "is_eligible": true,
  "loyalty_points": 6500,
  "points_eligible": true,
  "min_points_required": 1000,
  "max_points_allowed": 100000,
  "is_following_vendor": true,
  "has_active_subscription": true,
  "subscription_plan": "Premium",
  "credit_limit": "2000.00",
  "min_deposit_percent": "10.00"
}
```

Errors:
- `400` when `vendor_id` invalid or vendor not found

---

## 3. Debit Purchases

### 3.1 List My Purchases

```
GET /api/debit/purchases/my-purchases/
```

Query params:
- `status` (optional): `pending`, `active`, `paid`, `defaulted`, `cancelled`

**Auth:** Required

**Response `200 OK`:**

```json
[
  {
    "id": "a1b2c3d4-...",
    "vendor": 12,
    "vendor_email": "vendor@example.com",
    "order": 56,
    "total_amount": "1000.00",
    "deposit_amount": "100.00",
    "deposit_percentage": "10.00",
    "remaining_amount": "900.00",
    "amount_paid": "250.00",
    "outstanding_balance": "650.00",
    "status": "active",
    "is_fully_paid": false,
    "is_overdue": false,
    "due_date": "2026-04-20",
    "paid_at": null,
    "created_at": "2026-03-20T10:00:00Z",
    "updated_at": "2026-03-21T09:00:00Z",
    "repayments": [
      {
        "id": "d4e5f6...",
        "amount": "250.00",
        "payment_method": "card",
        "reference": "PAY-001",
        "created_at": "2026-03-21T08:59:00Z"
      }
    ]
  }
]
```

### 3.2 Get Purchase Details

```
GET /api/debit/purchases/{id}/detail_purchase/
```

**Auth:** Required

**Response `200 OK`:** same object as list item above

### 3.3 Buy on Debit

```
POST /api/debit/purchases/buy-on-debit/
```

**Auth:** Required

**Body:**

```json
{
  "vendor_id": 123,
  "total_amount": "1500.00",
  "deposit_amount": "150.00",
  "due_date": "2026-04-18",    // optional
  "order_id": 789              // optional
}
```

Validation rules:
- `vendor_id` must be a vendor user
- user loyalty points between `1000` and `100000`
- user must follow vendor
- user must have active subscription
- deposit ≥ 10% of total
- remaining (total - deposit) ≤ available credit
- debit account must be `active`

**Success `201 Created`:** created purchase object (same as purchase serializer output)

Errors:
- `400` with detailed message if rules fail

---

## 4. Repayments

### 4.1 Make a Repayment

```
POST /api/debit/purchases/repay/
```

**Auth:** Required

**Body:**

```json
{
  "purchase_id": "a1b2c3d4-...",
  "amount": "150.00",
  "payment_method": "card",  // card|eft|wallet|cash
  "reference": "TXN-12345"  // optional
}
```

Validation rules:
- purchase must belong to current user
- purchase must not be fully paid
- purchase status must be `active` or `defaulted`
- amount must be > 0 and ≤ outstanding_balance

**Success `201 Created`:**

```json
{
  "id": "e6f7g8...",
  "amount": "150.00",
  "payment_method": "card",
  "reference": "TXN-12345",
  "created_at": "2026-03-22T10:00:00Z"
}
```

On full payment, purchase status transitions to `paid` and `paid_at` updates.

---

## 5. Dart Models

```dart
class DebitAccount {
  final int id;
  final String userEmail;
  final String status;
  final String creditLimit;
  final String currentBalance;
  final String availableCredit;
  final DateTime createdAt;
  final DateTime updatedAt;

  DebitAccount({
    required this.id,
    required this.userEmail,
    required this.status,
    required this.creditLimit,
    required this.currentBalance,
    required this.availableCredit,
    required this.createdAt,
    required this.updatedAt,
  });

  factory DebitAccount.fromJson(Map<String, dynamic> json) => DebitAccount(
        id: json['id'],
        userEmail: json['user_email'],
        status: json['status'],
        creditLimit: json['credit_limit'],
        currentBalance: json['current_balance'],
        availableCredit: json['available_credit'],
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
      );
}

class DebitEligibility {
  final bool isEligible;
  final int loyaltyPoints;
  final bool pointsEligible;
  final int minPointsRequired;
  final int maxPointsAllowed;
  final bool isFollowingVendor;
  final bool hasActiveSubscription;
  final String? subscriptionPlan;
  final String creditLimit;
  final String minDepositPercent;

  DebitEligibility({
    required this.isEligible,
    required this.loyaltyPoints,
    required this.pointsEligible,
    required this.minPointsRequired,
    required this.maxPointsAllowed,
    required this.isFollowingVendor,
    required this.hasActiveSubscription,
    required this.subscriptionPlan,
    required this.creditLimit,
    required this.minDepositPercent,
  });

  factory DebitEligibility.fromJson(Map<String, dynamic> json) => DebitEligibility(
        isEligible: json['is_eligible'],
        loyaltyPoints: json['loyalty_points'],
        pointsEligible: json['points_eligible'],
        minPointsRequired: json['min_points_required'],
        maxPointsAllowed: json['max_points_allowed'],
        isFollowingVendor: json['is_following_vendor'],
        hasActiveSubscription: json['has_active_subscription'],
        subscriptionPlan: json['subscription_plan'],
        creditLimit: json['credit_limit'],
        minDepositPercent: json['min_deposit_percent'],
      );
}

class DebitRepayment {
  final String id;
  final String amount;
  final String paymentMethod;
  final String reference;
  final DateTime createdAt;

  DebitRepayment({
    required this.id,
    required this.amount,
    required this.paymentMethod,
    required this.reference,
    required this.createdAt,
  });

  factory DebitRepayment.fromJson(Map<String, dynamic> json) => DebitRepayment(
        id: json['id'],
        amount: json['amount'],
        paymentMethod: json['payment_method'],
        reference: json['reference'] ?? '',
        createdAt: DateTime.parse(json['created_at']),
      );
}

class DebitPurchase {
  final String id;
  final int vendor;
  final String vendorEmail;
  final int? order;
  final String totalAmount;
  final String depositAmount;
  final String depositPercentage;
  final String remainingAmount;
  final String amountPaid;
  final String outstandingBalance;
  final String status;
  final bool isFullyPaid;
  final bool isOverdue;
  final String dueDate;
  final String? paidAt;
  final DateTime createdAt;
  final DateTime updatedAt;
  final List<DebitRepayment> repayments;

  DebitPurchase({
    required this.id,
    required this.vendor,
    required this.vendorEmail,
    this.order,
    required this.totalAmount,
    required this.depositAmount,
    required this.depositPercentage,
    required this.remainingAmount,
    required this.amountPaid,
    required this.outstandingBalance,
    required this.status,
    required this.isFullyPaid,
    required this.isOverdue,
    required this.dueDate,
    this.paidAt,
    required this.createdAt,
    required this.updatedAt,
    required this.repayments,
  });

  factory DebitPurchase.fromJson(Map<String, dynamic> json) => DebitPurchase(
        id: json['id'],
        vendor: json['vendor'],
        vendorEmail: json['vendor_email'],
        order: json['order'],
        totalAmount: json['total_amount'],
        depositAmount: json['deposit_amount'],
        depositPercentage: json['deposit_percentage'],
        remainingAmount: json['remaining_amount'],
        amountPaid: json['amount_paid'],
        outstandingBalance: json['outstanding_balance'],
        status: json['status'],
        isFullyPaid: json['is_fully_paid'],
        isOverdue: json['is_overdue'],
        dueDate: json['due_date'],
        paidAt: json['paid_at'],
        createdAt: DateTime.parse(json['created_at']),
        updatedAt: DateTime.parse(json['updated_at']),
        repayments: (json['repayments'] as List)
            .map((e) => DebitRepayment.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}
```

---

## 6. Dart API Service

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class DebitApiService {
  final String baseUrl;
  final String? accessToken;

  DebitApiService({required this.baseUrl, this.accessToken});

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (accessToken != null) 'Authorization': 'Bearer $accessToken',
      };

  Future<DebitAccount> getDebitAccount() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/debit/account/'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to load debit account: ${response.body}');
    }
    return DebitAccount.fromJson(jsonDecode(response.body));
  }

  Future<DebitEligibility> checkEligibility(int vendorId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/debit/eligibility/'),
      headers: _headers,
      body: jsonEncode({'vendor_id': vendorId}),
    );
    if (response.statusCode != 200) {
      throw Exception('Eligibility check failed: ${response.body}');
    }
    return DebitEligibility.fromJson(jsonDecode(response.body));
  }

  Future<List<DebitPurchase>> getMyPurchases({String? status}) async {
    final query = status != null ? '?status=$status' : '';
    final response = await http.get(
      Uri.parse('$baseUrl/api/debit/purchases/my-purchases/$query'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to list purchases: ${response.body}');
    }
    return (jsonDecode(response.body) as List)
        .map((e) => DebitPurchase.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<DebitPurchase> getPurchaseDetail(String id) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/debit/purchases/$id/detail_purchase/'),
      headers: _headers,
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to load purchase: ${response.body}');
    }
    return DebitPurchase.fromJson(jsonDecode(response.body));
  }

  Future<DebitPurchase> buyOnDebit({
    required int vendorId,
    required String totalAmount,
    required String depositAmount,
    String? dueDate,
    int? orderId,
  }) async {
    final body = <String, dynamic>{
      'vendor_id': vendorId,
      'total_amount': totalAmount,
      'deposit_amount': depositAmount,
      if (dueDate != null) 'due_date': dueDate,
      if (orderId != null) 'order_id': orderId,
    };
    final response = await http.post(
      Uri.parse('$baseUrl/api/debit/purchases/buy-on-debit/'),
      headers: _headers,
      body: jsonEncode(body),
    );
    if (response.statusCode != 201) {
      throw Exception('Buy on debit failed: ${response.body}');
    }
    return DebitPurchase.fromJson(jsonDecode(response.body));
  }

  Future<DebitRepayment> repay({
    required String purchaseId,
    required String amount,
    required String paymentMethod,
    String? reference,
  }) async {
    final body = <String, dynamic>{
      'purchase_id': purchaseId,
      'amount': amount,
      'payment_method': paymentMethod,
      if (reference != null) 'reference': reference,
    };
    final response = await http.post(
      Uri.parse('$baseUrl/api/debit/purchases/repay/'),
      headers: _headers,
      body: jsonEncode(body),
    );
    if (response.statusCode != 201) {
      throw Exception('Repay failed: ${response.body}');
    }
    return DebitRepayment.fromJson(jsonDecode(response.body));
  }
}
```
