# Fraud Detection — Flutter / Dart API Reference

> **Base URL** `https://<host>/api/fraud/`  
> **Authentication** All endpoints require a JWT `Authorization: Bearer <token>` header.  
> **Admin-only** endpoints additionally require the user to have `is_staff = true`.

---

## Table of Contents

1. [How the System Works](#1-how-the-system-works)
2. [Risk Score Explained](#2-risk-score-explained)
3. [What Gets Detected](#3-what-gets-detected)
4. [Dart Models](#4-dart-models)
   - 4.1 [FraudProfileSummary](#41-fraudprofilesummary)
   - 4.2 [FraudProfile (full)](#42-fraudprofile-full)
   - 4.3 [FraudEvent](#43-fraudevent)
   - 4.4 [Enums](#44-enums)
5. [Buyer Endpoints](#5-buyer-endpoints)
   - 5.1 [GET /me/ — My Risk Profile](#51-get-me--my-risk-profile)
6. [Admin Endpoints — Profiles](#6-admin-endpoints--profiles)
   - 6.1 [GET /profiles/ — List All Profiles](#61-get-profiles--list-all-profiles)
   - 6.2 [GET /profiles/{id}/ — Profile Detail](#62-get-profilesid--profile-detail)
   - 6.3 [PATCH /profiles/{id}/ — Submit Review](#63-patch-profilesid--submit-review)
7. [Admin Endpoints — Events](#7-admin-endpoints--events)
   - 7.1 [GET /events/ — List Events](#71-get-events--list-events)
   - 7.2 [POST /events/{id}/action/ — Resolve Event](#72-post-eventsidaction--resolve-event)
8. [Admin Endpoints — Rescoring](#8-admin-endpoints--rescoring)
   - 8.1 [POST /rescore/user/{id}/](#81-post-rescoreuserid)
   - 8.2 [POST /rescore/vendor/{id}/](#82-post-rescorevendorid)
9. [Admin Endpoints — Model Training](#9-admin-endpoints--model-training)
   - 9.1 [POST /train/](#91-post-train)
10. [Integration Guide for Flutter](#10-integration-guide-for-flutter)
11. [Error Responses](#11-error-responses)

---

## 1. How the System Works

The fraud detection system runs silently in the background from the moment a user or vendor is created. It never interrupts the normal shopping flow. Instead it continuously monitors behaviour and assigns a **risk score** to every account, updating that score whenever something suspicious happens.

### Two detection layers working together

The system uses two complementary approaches:

**Layer 1 — Rule engine (instant, deterministic)**
A set of hard-coded business rules that fire immediately when a threshold is crossed. For example: if a buyer requests refunds on more than 50% of their orders, that rule fires right away and adds 45 points to their risk score. Rules are fast, predictable, and easy for admins to understand and explain.

**Layer 2 — XGBoost machine learning classifier (pattern-aware)**
A trained binary classifier that reads 14 behavioural features about a user (or 8 features about a vendor) and predicts the probability that the account is fraudulent — expressed as 0 to 100. XGBoost catches subtle combinations that no single rule would catch, for example a moderately high refund rate *combined with* a very new account *and* no profile picture — each signal is mild, but together they are suspicious.

**How the two layers combine:**

```
final_score = min(100,  rule_score  +  xgb_score × 0.35)
```

Rules are authoritative when they fire. XGBoost adds up to 35 bonus points as a soft signal when it detects an unusual pattern the rules did not catch. This means:
- A buyer with a 60% refund rate gets flagged by the rule engine alone, even on day one of the model's life.
- A buyer with no rule violations but an unusual combination of signals gets flagged by XGBoost alone.
- Both layers agree → the score climbs very high very fast.

### When does scoring happen?

Scoring is **non-blocking and happens in the background** so no user-facing request is ever slowed down. A daemon thread handles the scoring after each trigger:

| Trigger event | Who gets scored |
|---|---|
| Buyer places a new order | That buyer |
| Buyer requests a refund | That buyer |
| A payment transaction fails | That buyer |
| A vendor profile is created or updated | That vendor |

In addition, **Celery Beat** runs a daily batch job that rescores every active account so no one is missed if they flew under the real-time triggers.

### XGBoost model lifecycle

The models are stored as `.joblib` files on disk and loaded once per worker process (singleton pattern). On first server start, if no trained models exist, they bootstrap on **800 synthetic users** and **400 synthetic vendors** so the system is immediately useful. Once admins start marking fraud events as "Confirmed" or "Cleared" through the review API, those labelled examples accumulate and the weekly retraining task switches to real data automatically (threshold: 50 confirmed user examples, 20 vendor examples).

---

## 2. Risk Score Explained

Every `FraudProfile` has a `risk_score` (0–100) and a derived `risk_level` string:

| Score range | risk_level | Meaning | Auto-flagged? |
|---|---|---|---|
| 0 – 24 | `low` | Normal behaviour, no concerns | No |
| 25 – 49 | `medium` | Some signals worth monitoring | No |
| 50 – 74 | `high` | Multiple strong signals, review recommended | **Yes** |
| 75 – 100 | `critical` | Very strong fraud signals, immediate review needed | **Yes** |

When a profile reaches `high` or `critical`, `is_flagged` is set to `true` and `auto_flagged_at` is recorded. This shows up in the admin review queue immediately.

---

## 3. What Gets Detected

### User / Buyer fraud signals

| event_type | Severity | What triggers it | Rule score added |
|---|---|---|---|
| `new_account_surge` | high | Account < 7 days old AND 5+ orders placed | +30 |
| `rapid_orders` | high | 8 or more orders placed in the last 24 hours | +35 |
| `high_refund_rate` | critical | Refund rate ≥ 50% with at least 3 refunds | +45 |
| `refund_abuse` | high | 6 or more total refund requests | +25 |
| `dispute_pattern` | high | 3 or more payment disputes on record | +35 |
| `payment_failure_spike` | medium | 8 or more failed payment attempts | +20 |
| `credit_abuse` | medium | BNPL/credit account is currently suspended | +20 |
| `unverified_high_value` | medium | Unverified account with R5,000+ in total orders | +25 |
| `ml_anomaly` | medium | XGBoost score ≥ 70 but no rules fired — unusual combination detected | bonus only |

### Vendor fraud signals

| event_type | Severity | What triggers it | Rule score added |
|---|---|---|---|
| `suspicious_vendor` | critical | Dispute rate ≥ 15% (platform average is ~2%) | +50 |
| `high_refund_rate` | high | Refund rate ≥ 20% | +35 |
| `new_vendor_surge` | high | Vendor < 14 days old AND 30+ orders | +35 |
| `unverified_active` | medium | Unverified vendor with 20+ orders | +20 |
| `ml_anomaly` | medium | XGBoost score ≥ 70 but no rules fired | bonus only |

---

## 4. Dart Models

### 4.1 FraudProfileSummary

This is the lightweight model returned to the **buyer themselves**. It shows just enough for a transparency screen (e.g. "Your account is in good standing").

```dart
class FraudProfileSummary {
  final int id;
  final double riskScore;      // 0.0 – 100.0
  final RiskLevel riskLevel;   // low | medium | high | critical
  final bool isFlagged;
  final int refundCount;
  final int disputeCount;
  final DateTime? lastScoredAt;

  const FraudProfileSummary({
    required this.id,
    required this.riskScore,
    required this.riskLevel,
    required this.isFlagged,
    required this.refundCount,
    required this.disputeCount,
    this.lastScoredAt,
  });

  factory FraudProfileSummary.fromJson(Map<String, dynamic> json) {
    return FraudProfileSummary(
      id:            json['id'] as int,
      riskScore:     (json['risk_score'] as num).toDouble(),
      riskLevel:     RiskLevel.fromString(json['risk_level'] as String),
      isFlagged:     json['is_flagged'] as bool,
      refundCount:   json['refund_count'] as int,
      disputeCount:  json['dispute_count'] as int,
      lastScoredAt:  json['last_scored_at'] != null
          ? DateTime.parse(json['last_scored_at'] as String)
          : null,
    );
  }
}
```

---

### 4.2 FraudProfile (full)

The full model returned to **admins**. Includes all stats, review state, feature breakdown, and the list of individual events.

```dart
class FraudProfile {
  final int id;
  final int? userId;
  final String? vendorId;     // UUID string
  final String? userEmail;
  final String? vendorName;

  // Risk
  final double riskScore;
  final RiskLevel riskLevel;
  final bool isFlagged;
  final DateTime? autoFlaggedAt;

  // Aggregate stats (read-only, computed by the backend)
  final int totalOrders;
  final double totalOrderValue;
  final int refundCount;
  final int disputeCount;
  final int failedPaymentCount;

  // Admin review
  final bool isReviewed;
  final ReviewOutcome? reviewOutcome;
  final String reviewNotes;
  final DateTime? reviewedAt;

  // Scoring metadata
  final DateTime? lastScoredAt;
  final Map<String, dynamic> scoreFeatures; // raw feature values used in last score
  final List<FraudEvent> events;

  final DateTime createdAt;
  final DateTime updatedAt;

  const FraudProfile({
    required this.id,
    this.userId,
    this.vendorId,
    this.userEmail,
    this.vendorName,
    required this.riskScore,
    required this.riskLevel,
    required this.isFlagged,
    this.autoFlaggedAt,
    required this.totalOrders,
    required this.totalOrderValue,
    required this.refundCount,
    required this.disputeCount,
    required this.failedPaymentCount,
    required this.isReviewed,
    this.reviewOutcome,
    this.reviewNotes = '',
    this.reviewedAt,
    this.lastScoredAt,
    this.scoreFeatures = const {},
    this.events = const [],
    required this.createdAt,
    required this.updatedAt,
  });

  factory FraudProfile.fromJson(Map<String, dynamic> json) {
    return FraudProfile(
      id:                  json['id'] as int,
      userId:              json['user'] as int?,
      vendorId:            json['vendor'] as String?,
      userEmail:           json['user_email'] as String?,
      vendorName:          json['vendor_name'] as String?,
      riskScore:           (json['risk_score'] as num).toDouble(),
      riskLevel:           RiskLevel.fromString(json['risk_level'] as String),
      isFlagged:           json['is_flagged'] as bool,
      autoFlaggedAt:       json['auto_flagged_at'] != null
          ? DateTime.parse(json['auto_flagged_at'] as String) : null,
      totalOrders:         json['total_orders'] as int,
      totalOrderValue:     double.parse(json['total_order_value'].toString()),
      refundCount:         json['refund_count'] as int,
      disputeCount:        json['dispute_count'] as int,
      failedPaymentCount:  json['failed_payment_count'] as int,
      isReviewed:          json['is_reviewed'] as bool,
      reviewOutcome:       json['review_outcome'] != null && (json['review_outcome'] as String).isNotEmpty
          ? ReviewOutcome.fromString(json['review_outcome'] as String) : null,
      reviewNotes:         json['review_notes'] as String? ?? '',
      reviewedAt:          json['reviewed_at'] != null
          ? DateTime.parse(json['reviewed_at'] as String) : null,
      lastScoredAt:        json['last_scored_at'] != null
          ? DateTime.parse(json['last_scored_at'] as String) : null,
      scoreFeatures:       Map<String, dynamic>.from(json['score_features'] as Map? ?? {}),
      events:              (json['events'] as List<dynamic>)
          .map((e) => FraudEvent.fromJson(e as Map<String, dynamic>))
          .toList(),
      createdAt:           DateTime.parse(json['created_at'] as String),
      updatedAt:           DateTime.parse(json['updated_at'] as String),
    );
  }

  /// True if this profile belongs to a buyer account.
  bool get isUserProfile => userId != null;

  /// True if this profile belongs to a vendor.
  bool get isVendorProfile => vendorId != null;

  /// Display name for list screens.
  String get subjectLabel => userEmail ?? vendorName ?? 'Unknown';
}
```

---

### 4.3 FraudEvent

Each individual fraud signal that fired against this profile. A profile can have many events over its lifetime.

```dart
class FraudEvent {
  final String id;          // UUID
  final FraudEventType eventType;
  final RiskLevel severity;
  final String description; // human-readable explanation of why this fired
  final FraudEntityType entityType;
  final String entityId;    // ID of the specific order/user/vendor that triggered it
  final Map<String, dynamic> metadata;  // raw feature values at the time of detection
  final double? mlScore;    // XGBoost probability (0–100), present only for ml_anomaly events
  final bool isFalsePositive;
  final bool isResolved;
  final DateTime? resolvedAt;
  final DateTime createdAt;

  const FraudEvent({
    required this.id,
    required this.eventType,
    required this.severity,
    required this.description,
    required this.entityType,
    required this.entityId,
    this.metadata = const {},
    this.mlScore,
    required this.isFalsePositive,
    required this.isResolved,
    this.resolvedAt,
    required this.createdAt,
  });

  factory FraudEvent.fromJson(Map<String, dynamic> json) {
    return FraudEvent(
      id:               json['id'] as String,
      eventType:        FraudEventType.fromString(json['event_type'] as String),
      severity:         RiskLevel.fromString(json['severity'] as String),
      description:      json['description'] as String,
      entityType:       FraudEntityType.fromString(json['entity_type'] as String),
      entityId:         json['entity_id'] as String,
      metadata:         Map<String, dynamic>.from(json['metadata'] as Map? ?? {}),
      mlScore:          json['ml_score'] != null
          ? (json['ml_score'] as num).toDouble() : null,
      isFalsePositive:  json['is_false_positive'] as bool,
      isResolved:       json['is_resolved'] as bool,
      resolvedAt:       json['resolved_at'] != null
          ? DateTime.parse(json['resolved_at'] as String) : null,
      createdAt:        DateTime.parse(json['created_at'] as String),
    );
  }
}
```

---

### 4.4 Enums

```dart
enum RiskLevel {
  low,
  medium,
  high,
  critical;

  static RiskLevel fromString(String value) => switch (value) {
    'low'      => RiskLevel.low,
    'medium'   => RiskLevel.medium,
    'high'     => RiskLevel.high,
    'critical' => RiskLevel.critical,
    _          => RiskLevel.low,
  };

  /// Colour to use in the UI for this risk level.
  Color get color => switch (this) {
    RiskLevel.low      => const Color(0xFF2E7D32), // green
    RiskLevel.medium   => const Color(0xFFF57C00), // orange
    RiskLevel.high     => const Color(0xFFC62828), // red
    RiskLevel.critical => const Color(0xFF4A148C), // deep purple
  };

  String get label => switch (this) {
    RiskLevel.low      => 'Low',
    RiskLevel.medium   => 'Medium',
    RiskLevel.high     => 'High',
    RiskLevel.critical => 'Critical',
  };
}

// ─────────────────────────────────────────────────────────────────────────────

enum ReviewOutcome {
  cleared,
  confirmed,
  monitoring;

  static ReviewOutcome fromString(String value) => switch (value) {
    'cleared'    => ReviewOutcome.cleared,
    'confirmed'  => ReviewOutcome.confirmed,
    'monitoring' => ReviewOutcome.monitoring,
    _            => ReviewOutcome.monitoring,
  };

  String get label => switch (this) {
    ReviewOutcome.cleared    => 'Cleared',
    ReviewOutcome.confirmed  => 'Confirmed Fraud',
    ReviewOutcome.monitoring => 'Under Monitoring',
  };
}

// ─────────────────────────────────────────────────────────────────────────────

enum FraudEventType {
  rapidOrders,
  highRefundRate,
  refundAbuse,
  disputePattern,
  newAccountSurge,
  suspiciousVendor,
  newVendorSurge,
  mlAnomaly,
  creditAbuse,
  paymentFailureSpike,
  unverifiedHighValue,
  unverifiedActive;

  static FraudEventType fromString(String value) => switch (value) {
    'rapid_orders'           => FraudEventType.rapidOrders,
    'high_refund_rate'       => FraudEventType.highRefundRate,
    'refund_abuse'           => FraudEventType.refundAbuse,
    'dispute_pattern'        => FraudEventType.disputePattern,
    'new_account_surge'      => FraudEventType.newAccountSurge,
    'suspicious_vendor'      => FraudEventType.suspiciousVendor,
    'new_vendor_surge'       => FraudEventType.newVendorSurge,
    'ml_anomaly'             => FraudEventType.mlAnomaly,
    'credit_abuse'           => FraudEventType.creditAbuse,
    'payment_failure_spike'  => FraudEventType.paymentFailureSpike,
    'unverified_high_value'  => FraudEventType.unverifiedHighValue,
    'unverified_active'      => FraudEventType.unverifiedActive,
    _                        => FraudEventType.mlAnomaly,
  };

  String get label => switch (this) {
    FraudEventType.rapidOrders          => 'Rapid Orders',
    FraudEventType.highRefundRate       => 'High Refund Rate',
    FraudEventType.refundAbuse          => 'Refund Abuse',
    FraudEventType.disputePattern       => 'Dispute Pattern',
    FraudEventType.newAccountSurge      => 'New Account Surge',
    FraudEventType.suspiciousVendor     => 'Suspicious Vendor',
    FraudEventType.newVendorSurge       => 'New Vendor Surge',
    FraudEventType.mlAnomaly            => 'ML Anomaly',
    FraudEventType.creditAbuse          => 'Credit Abuse',
    FraudEventType.paymentFailureSpike  => 'Payment Failure Spike',
    FraudEventType.unverifiedHighValue  => 'Unverified High Value',
    FraudEventType.unverifiedActive     => 'Unverified Active Vendor',
  };
}

// ─────────────────────────────────────────────────────────────────────────────

enum FraudEntityType {
  user,
  vendor,
  order,
  transaction,
  refund;

  static FraudEntityType fromString(String value) => switch (value) {
    'user'        => FraudEntityType.user,
    'vendor'      => FraudEntityType.vendor,
    'order'       => FraudEntityType.order,
    'transaction' => FraudEntityType.transaction,
    'refund'      => FraudEntityType.refund,
    _             => FraudEntityType.user,
  };
}
```

---

## 5. Buyer Endpoints

### 5.1 GET /me/ — My Risk Profile

**Who can call it:** Any authenticated buyer.

**What it does:** Returns the buyer's own fraud risk summary. This is intended for a "Your account standing" transparency screen so buyers can see if they have been flagged for unusual behaviour. Importantly, it does **not** reveal which specific events or feature values triggered the score — that detail is reserved for admins.

If no profile exists yet (buyer has never been scored), the backend creates an empty one automatically and returns it with `risk_score: 0.0` and `risk_level: "low"`.

**Request:**
```http
GET /api/fraud/me/
Authorization: Bearer <access_token>
```

**Response `200 OK`:**
```json
{
  "id": 12,
  "risk_score": 8.4,
  "risk_level": "low",
  "is_flagged": false,
  "refund_count": 1,
  "dispute_count": 0,
  "last_scored_at": "2026-05-07T18:30:00Z"
}
```

**Dart usage:**
```dart
Future<FraudProfileSummary> fetchMyFraudProfile(String token) async {
  final response = await http.get(
    Uri.parse('$baseUrl/api/fraud/me/'),
    headers: {'Authorization': 'Bearer $token'},
  );
  if (response.statusCode == 200) {
    return FraudProfileSummary.fromJson(jsonDecode(response.body));
  }
  throw Exception('Failed to fetch fraud profile: ${response.statusCode}');
}
```

**When to call it:**
- On the Account/Profile screen to show a "Standing" badge.
- After a refund is requested to update the displayed standing.
- Do **not** call it on every app open — cache the result for at least 10 minutes.

---

## 6. Admin Endpoints — Profiles

### 6.1 GET /profiles/ — List All Profiles

**Who can call it:** Staff/admin users only (`is_staff = true`).

**What it does:** Returns a paginated list of all fraud profiles across all users and vendors, ordered from highest to lowest risk score. This is the main admin review dashboard — the admin opens this screen, filters by `flagged=true&reviewed=false` to see the queue of accounts that need attention, and works through them one by one.

**Query parameters:**

| Param | Type | Description |
|---|---|---|
| `risk_level` | string | Filter by `low`, `medium`, `high`, or `critical` |
| `flagged` | `true` | Only return profiles where `is_flagged = true` |
| `reviewed` | `false` | Only return flagged profiles not yet reviewed |
| `subject` | `user` or `vendor` | Filter to buyer profiles only or vendor profiles only |

**Request:**
```http
GET /api/fraud/profiles/?flagged=true&reviewed=false
Authorization: Bearer <admin_token>
```

**Response `200 OK`:**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 45,
      "user": 102,
      "vendor": null,
      "user_email": "buyer@example.com",
      "vendor_name": null,
      "risk_score": 80.2,
      "risk_level": "critical",
      "is_flagged": true,
      "auto_flagged_at": "2026-05-07T14:22:11Z",
      "total_orders": 22,
      "total_order_value": "18500.00",
      "refund_count": 11,
      "dispute_count": 4,
      "failed_payment_count": 9,
      "is_reviewed": false,
      "review_outcome": "",
      "review_notes": "",
      "reviewed_at": null,
      "last_scored_at": "2026-05-07T14:22:11Z",
      "score_features": {
        "account_age_days": 3.4,
        "is_verified": 0,
        "refund_rate": 0.5,
        ...
      },
      "events": [
        {
          "id": "a1b2c3d4-...",
          "event_type": "high_refund_rate",
          "severity": "critical",
          "description": "Refund rate 50% across 11 refunds — possible refund abuse",
          "entity_type": "user",
          "entity_id": "102",
          "metadata": { "refund_count": 11, "refund_rate": 0.5 },
          "ml_score": null,
          "is_false_positive": false,
          "is_resolved": false,
          "resolved_at": null,
          "created_at": "2026-05-07T14:22:11Z"
        }
      ],
      "created_at": "2026-05-01T09:00:00Z",
      "updated_at": "2026-05-07T14:22:11Z"
    }
  ]
}
```

**Dart usage:**
```dart
Future<List<FraudProfile>> fetchFlaggedProfiles(String adminToken) async {
  final uri = Uri.parse('$baseUrl/api/fraud/profiles/')
      .replace(queryParameters: {
        'flagged': 'true',
        'reviewed': 'false',
      });

  final response = await http.get(
    uri,
    headers: {'Authorization': 'Bearer $adminToken'},
  );

  if (response.statusCode == 200) {
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final results = body['results'] as List<dynamic>;
    return results
        .map((e) => FraudProfile.fromJson(e as Map<String, dynamic>))
        .toList();
  }
  throw Exception('Failed to fetch fraud profiles');
}
```

---

### 6.2 GET /profiles/{id}/ — Profile Detail

**Who can call it:** Staff/admin users only.

**What it does:** Returns the full fraud profile for a single account, including the complete list of every fraud event that has ever fired on it. Admins use this to understand exactly why an account was flagged before making a review decision. The `score_features` field shows the raw feature values (e.g. `refund_rate: 0.62`, `account_age_days: 4.1`) that the XGBoost model and rules used — this makes the decision fully explainable.

**Request:**
```http
GET /api/fraud/profiles/45/
Authorization: Bearer <admin_token>
```

**Response:** Same structure as a single item from the list above.

**Dart usage:**
```dart
Future<FraudProfile> fetchFraudProfile(int profileId, String adminToken) async {
  final response = await http.get(
    Uri.parse('$baseUrl/api/fraud/profiles/$profileId/'),
    headers: {'Authorization': 'Bearer $adminToken'},
  );
  if (response.statusCode == 200) {
    return FraudProfile.fromJson(jsonDecode(response.body));
  }
  throw Exception('Profile not found');
}
```

---

### 6.3 PATCH /profiles/{id}/ — Submit Review

**Who can call it:** Staff/admin users only.

**What it does:** Records the admin's review decision on a flagged profile. There are three possible outcomes:

- `cleared` — The admin investigated and this is legitimate behaviour. The flag remains in history but the account is no longer in the review queue.
- `confirmed` — Confirmed fraud. This example will be included in the next XGBoost retraining session as a positive (fraud) label, making the model smarter over time.
- `monitoring` — Borderline case. Keep the account on a watchlist but do not take action yet.

When you submit a review, the backend automatically records `reviewed_by` (the admin's user ID) and `reviewed_at` (current timestamp) — you do not need to send those fields.

**Request:**
```http
PATCH /api/fraud/profiles/45/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "is_reviewed": true,
  "review_outcome": "confirmed",
  "review_notes": "Multiple refund requests on single-use accounts. IP matches previous fraudster."
}
```

**Request body fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `is_reviewed` | boolean | Yes | Must be `true` to mark as reviewed |
| `review_outcome` | string | Yes | One of `cleared`, `confirmed`, `monitoring` |
| `review_notes` | string | No | Free-text explanation visible in the admin log |

**Response `200 OK`:** Returns the updated full `FraudProfile` object.

**Dart usage:**
```dart
Future<FraudProfile> submitFraudReview({
  required int profileId,
  required String adminToken,
  required ReviewOutcome outcome,
  String notes = '',
}) async {
  final response = await http.patch(
    Uri.parse('$baseUrl/api/fraud/profiles/$profileId/'),
    headers: {
      'Authorization': 'Bearer $adminToken',
      'Content-Type': 'application/json',
    },
    body: jsonEncode({
      'is_reviewed': true,
      'review_outcome': outcome.name,
      'review_notes': notes,
    }),
  );
  if (response.statusCode == 200) {
    return FraudProfile.fromJson(jsonDecode(response.body));
  }
  throw Exception('Review submission failed: ${response.statusCode}');
}
```

---

## 7. Admin Endpoints — Events

### 7.1 GET /events/ — List Events

**Who can call it:** Staff/admin users only.

**What it does:** Returns a time-ordered list of all individual fraud signals across the platform. Each event represents one rule violation or one ML anomaly detection. This is useful for a real-time activity feed: admins can see the platform-wide fraud signal rate and drill down into specific event types.

The `metadata` field on each event contains the exact feature values that caused the signal to fire — for example, for a `high_refund_rate` event: `{ "refund_count": 11, "refund_rate": 0.62, "order_count_total": 18 }`. For `ml_anomaly` events, `ml_score` contains the raw XGBoost probability (0–100).

**Query parameters:**

| Param | Type | Description |
|---|---|---|
| `event_type` | string | Filter to one event type, e.g. `high_refund_rate` |
| `severity` | string | Filter by `low`, `medium`, `high`, `critical` |
| `resolved` | `true` or `false` | Filter by resolution status |

**Request:**
```http
GET /api/fraud/events/?severity=critical&resolved=false
Authorization: Bearer <admin_token>
```

**Response `200 OK`:**
```json
{
  "count": 2,
  "results": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "event_type": "high_refund_rate",
      "severity": "critical",
      "description": "Refund rate 62% across 11 refunds — possible refund abuse",
      "entity_type": "user",
      "entity_id": "102",
      "metadata": {
        "refund_count": 11,
        "refund_rate": 0.62,
        "order_count_total": 18
      },
      "ml_score": null,
      "is_false_positive": false,
      "is_resolved": false,
      "resolved_at": null,
      "created_at": "2026-05-07T14:22:11Z"
    }
  ]
}
```

**Dart usage:**
```dart
Future<List<FraudEvent>> fetchUnresolvedCriticalEvents(String adminToken) async {
  final uri = Uri.parse('$baseUrl/api/fraud/events/')
      .replace(queryParameters: {
        'severity': 'critical',
        'resolved': 'false',
      });

  final response = await http.get(
    uri,
    headers: {'Authorization': 'Bearer $adminToken'},
  );

  if (response.statusCode == 200) {
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final results = body['results'] as List<dynamic>;
    return results
        .map((e) => FraudEvent.fromJson(e as Map<String, dynamic>))
        .toList();
  }
  throw Exception('Failed to fetch fraud events');
}
```

---

### 7.2 POST /events/{id}/action/ — Resolve Event

**Who can call it:** Staff/admin users only.

**What it does:** Closes an individual fraud event. There are two actions:

- `resolve` — The admin has looked at this event and taken appropriate action (or decided it requires no action). The event stays in the history but is removed from the "unresolved" queue.
- `false_positive` — The event fired incorrectly. It is marked as both resolved and false-positive. The backend records this so false positives can be analysed — if the same rule keeps generating false positives, the threshold can be tuned.

Note: marking an event as false positive does **not** automatically change the profile's `review_outcome`. The admin should also submit a profile review (section 6.3) if they want to clear the flag completely.

**Request:**
```http
POST /api/fraud/events/a1b2c3d4-e5f6-7890-abcd-ef1234567890/action/
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "action": "false_positive"
}
```

**Request body:**

| Field | Type | Description |
|---|---|---|
| `action` | string | `resolve` or `false_positive` |

**Response `200 OK`:** Returns the updated `FraudEvent` object.

**Dart usage:**
```dart
Future<FraudEvent> resolveEvent({
  required String eventId,  // UUID string
  required String adminToken,
  required bool isFalsePositive,
}) async {
  final response = await http.post(
    Uri.parse('$baseUrl/api/fraud/events/$eventId/action/'),
    headers: {
      'Authorization': 'Bearer $adminToken',
      'Content-Type': 'application/json',
    },
    body: jsonEncode({
      'action': isFalsePositive ? 'false_positive' : 'resolve',
    }),
  );
  if (response.statusCode == 200) {
    return FraudEvent.fromJson(jsonDecode(response.body));
  }
  throw Exception('Failed to resolve event: ${response.statusCode}');
}
```

---

## 8. Admin Endpoints — Rescoring

### 8.1 POST /rescore/user/{id}/

**Who can call it:** Staff/admin users only.

**What it does:** Forces an immediate, synchronous rescore of a specific buyer. Normally rescoring happens automatically (signal fires in a background thread after each order/refund/payment). Use this endpoint when you want a fresh score right now without waiting for the next trigger — for example, after manually editing a user's account or after getting a tip-off.

The response is the full updated `FraudProfile` so you can see the new score immediately.

**Request:**
```http
POST /api/fraud/rescore/user/102/
Authorization: Bearer <admin_token>
```

**Response `200 OK`:** Full `FraudProfile` object with updated scores and any new events.

**Dart usage:**
```dart
Future<FraudProfile> rescoreUser(int userId, String adminToken) async {
  final response = await http.post(
    Uri.parse('$baseUrl/api/fraud/rescore/user/$userId/'),
    headers: {'Authorization': 'Bearer $adminToken'},
  );
  if (response.statusCode == 200) {
    return FraudProfile.fromJson(jsonDecode(response.body));
  }
  throw Exception('Rescore failed: ${response.statusCode}');
}
```

---

### 8.2 POST /rescore/vendor/{id}/

**Who can call it:** Staff/admin users only.

**What it does:** Same as the user rescore but for a vendor profile. The `{id}` is the vendor's UUID.

**Request:**
```http
POST /api/fraud/rescore/vendor/550e8400-e29b-41d4-a716-446655440000/
Authorization: Bearer <admin_token>
```

**Response `200 OK`:** Full `FraudProfile` for the vendor.

**Dart usage:**
```dart
Future<FraudProfile> rescoreVendor(String vendorId, String adminToken) async {
  final response = await http.post(
    Uri.parse('$baseUrl/api/fraud/rescore/vendor/$vendorId/'),
    headers: {'Authorization': 'Bearer $adminToken'},
  );
  if (response.statusCode == 200) {
    return FraudProfile.fromJson(jsonDecode(response.body));
  }
  throw Exception('Vendor rescore failed: ${response.statusCode}');
}
```

---

## 9. Admin Endpoints — Model Training

### 9.1 POST /train/

**Who can call it:** Staff/admin users only.

**What it does:** Triggers an immediate retraining of both the user and vendor XGBoost classifiers. This endpoint runs synchronously — the response will not arrive until training is complete (typically 5–15 seconds on a development machine with synthetic data).

Normally you do not need to call this manually because the weekly Celery Beat task (`fraud.retrain_models`) handles it automatically. Use this endpoint when:
- You have just accumulated a significant batch of confirmed fraud labels through admin reviews and want the model to learn from them immediately.
- You suspect the model quality has degraded and want to force a fresh bootstrap.

The backend decides automatically whether to train on real labelled examples (from admin reviews) or fall back to synthetic bootstrap data. The threshold is 50 confirmed user examples and 20 confirmed vendor examples.

**Request:**
```http
POST /api/fraud/train/
Authorization: Bearer <admin_token>
```

**Response `200 OK`:**
```json
{
  "detail": "Fraud models retrained successfully."
}
```

**Response `500 Internal Server Error`** (if training fails):
```json
{
  "detail": "Error message describing what went wrong"
}
```

**Dart usage:**
```dart
Future<void> retrainFraudModels(String adminToken) async {
  final response = await http.post(
    Uri.parse('$baseUrl/api/fraud/train/'),
    headers: {'Authorization': 'Bearer $adminToken'},
  );
  if (response.statusCode != 200) {
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    throw Exception('Retraining failed: ${body['detail']}');
  }
}
```

---

## 10. Integration Guide for Flutter

### Buyer-facing: Account Standing Widget

Show a standing chip on the buyer's profile screen. Use `GET /me/` and cache the result — there is no need to call this on every page navigation.

```dart
class AccountStandingChip extends StatelessWidget {
  final FraudProfileSummary profile;

  const AccountStandingChip({super.key, required this.profile});

  @override
  Widget build(BuildContext context) {
    if (profile.riskLevel == RiskLevel.low) {
      return const Chip(
        label: Text('Account in good standing'),
        backgroundColor: Color(0xFFE8F5E9),
        labelStyle: TextStyle(color: Color(0xFF2E7D32)),
      );
    }
    return Chip(
      label: const Text('Account under review'),
      backgroundColor: const Color(0xFFFFF3E0),
      labelStyle: const TextStyle(color: Color(0xFFF57C00)),
    );
  }
}
```

### Admin-facing: Review Queue Screen

Recommended flow for the admin review queue:

1. Call `GET /profiles/?flagged=true&reviewed=false` to load the queue.
2. Tap a profile → call `GET /profiles/{id}/` for the full detail with all events.
3. Read the `events` list and `score_features` to understand why the account was flagged.
4. Tap "Cleared" / "Confirmed" / "Monitor" → call `PATCH /profiles/{id}/` with the decision.
5. Optionally, resolve individual events via `POST /events/{id}/action/`.

```dart
// Model for the review submission
class ReviewRequest {
  final bool isReviewed;
  final ReviewOutcome outcome;
  final String notes;

  const ReviewRequest({
    required this.isReviewed,
    required this.outcome,
    required this.notes,
  });

  Map<String, dynamic> toJson() => {
    'is_reviewed': isReviewed,
    'review_outcome': outcome.name,
    'review_notes': notes,
  };
}
```

### Polling vs. push

Fraud scores are computed in the background. There is no WebSocket push for fraud events. The recommended pattern is:

- **Admin review screen**: call the list endpoint on screen load and offer a manual refresh button. Do not poll automatically.
- **Buyer standing chip**: refresh when the buyer submits a refund request (since that immediately triggers a background rescore).

### Displaying score features to admins

The `score_features` map uses the same keys as the internal feature extractor. Use this lookup table to display them with human-readable labels:

```dart
const Map<String, String> featureLabels = {
  'account_age_days':       'Account age (days)',
  'is_verified':            'Phone verified',
  'has_profile_pic':        'Has profile photo',
  'order_count_total':      'Total orders',
  'order_count_7d':         'Orders last 7 days',
  'order_count_24h':        'Orders last 24 hours',
  'total_order_value':      'Total order value (R)',
  'avg_order_value':        'Average order value (R)',
  'refund_count':           'Total refunds',
  'refund_rate':            'Refund rate (%)',
  'dispute_count':          'Total disputes',
  'failed_payment_count':   'Failed payments',
  'credit_suspended':       'Credit suspended',
  'unique_address_count':   'Unique shipping addresses',
  // Vendor features
  'vendor_age_days':        'Vendor age (days)',
  'total_orders':           'Total vendor orders',
  'dispute_rate':           'Dispute rate (%)',
  'avg_order_value':        'Avg order value (R)',
  'revenue_30d':            'Revenue last 30 days (R)',
  'unique_buyer_count':     'Unique buyers',
};
```

---

## 11. Error Responses

All error responses follow the standard DRF format:

```json
{ "detail": "Human-readable error message." }
```

| HTTP status | Meaning |
|---|---|
| `401 Unauthorized` | Missing or expired JWT token |
| `403 Forbidden` | Authenticated but not staff — admin endpoint called by a regular user |
| `404 Not Found` | Profile or event ID does not exist |
| `400 Bad Request` | Invalid request body (e.g. unknown `action` value) |
| `500 Internal Server Error` | Returned only by `POST /train/` if model training crashes |

```dart
class FraudApiException implements Exception {
  final int statusCode;
  final String message;
  const FraudApiException(this.statusCode, this.message);

  @override
  String toString() => 'FraudApiException($statusCode): $message';
}

/// Helper to parse a DRF error response body.
FraudApiException parseFraudError(http.Response response) {
  try {
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return FraudApiException(
      response.statusCode,
      body['detail'] as String? ?? 'Unknown error',
    );
  } catch (_) {
    return FraudApiException(response.statusCode, response.body);
  }
}
```

---

*Document generated 2026-05-07. Corresponds to `fraud` app version 1.0 — XGBoost binary classifiers, rule engine v1, two-layer scoring.*
