# Sanoa Platform - Subscriptions & Tiers API (Paystack Integrated)

**Dart / Flutter Complete Reference**
**Payment Gateway: Paystack**
**Currency: ZAR (South African Rand)**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Customer Endpoints (Plans & Subscriptions)](#2-customer-endpoints)
3. [Vendor Endpoints (Tiers & Tier Subscriptions)](#3-vendor-endpoints)
4. [Admin-Only Endpoints](#4-admin-only-endpoints)
5. [Dart Models](#5-dart-models)
6. [Dart Subscription Service (Customer)](#6-dart-subscription-service-customer)
7. [Dart Tier Service (Vendor)](#7-dart-tier-service-vendor)
8. [Payment & Subscription Flow](#8-payment--subscription-flow)

---

## 1. Overview

- **Plans** → for **customers** (buyer credit plans)
- **Tiers** → for **vendors** (business tier plans)
- Each has its own subscriptions, linked to **Paystack** for payment processing
- Free tiers activate immediately; paid plans/tiers redirect to Paystack checkout
- Plans and paid tiers are **auto-synced to Paystack** on first list request — `paystack_plan_code` is always populated
- A default `callback_url` is returned from plan/tier list endpoints (configured via `PAYSTACK_CALLBACK_URL` env var) and used as fallback when subscribing without providing one

### Configuration

Set the following in your `.env` file:

```env
PAYSTACK_SECRET_KEY=sk_test_xxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx
PAYSTACK_CALLBACK_URL=https://yourapp.com/subscription/callback
```

### All Endpoints

#### Customer Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/subscriptions/plans/` | List credit plans (auto-syncs to Paystack) | Public |
| `GET` | `/api/subscriptions/plans/{slug}/` | Get plan details | Public |
| `GET` | `/api/subscriptions/subscriptions/my-subscription/` | Get my subscription | Yes |
| `POST` | `/api/subscriptions/subscriptions/subscribe/` | Subscribe to plan (Paystack) | Yes |
| `POST` | `/api/subscriptions/subscriptions/cancel/` | Cancel subscription | Yes |
| `GET` | `/api/subscriptions/subscriptions/manage-card/` | Get Paystack card update link | Yes |

#### Vendor Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/tiers/plans/` | List business tiers (auto-syncs paid tiers to Paystack) | Public |
| `GET` | `/api/tiers/plans/{slug}/` | Get tier details | Public |
| `GET` | `/api/tiers/subscriptions/my-tier/` | Get my tier subscription | Yes |
| `POST` | `/api/tiers/subscriptions/subscribe/` | Subscribe to tier (Paystack) | Yes |
| `POST` | `/api/tiers/subscriptions/cancel/` | Cancel tier subscription | Yes |
| `GET` | `/api/tiers/subscriptions/manage-card/` | Get Paystack card update link | Yes |

#### Admin Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/subscriptions/plans/{slug}/sync-paystack/` | Manually sync plan to Paystack |
| `POST` | `/api/tiers/plans/{slug}/sync-paystack/` | Manually sync tier to Paystack |

---

## 2. Customer Endpoints

### 2.1 List Credit Plans

```
GET /api/subscriptions/plans/
```

**Auth:** Public

**Behavior:** Automatically syncs any plans with missing `paystack_plan_code` to Paystack before returning results.

**Response `200 OK`:**

```json
{
  "count": 3,
  "results": [
    {
      "id": "bb0e8400-e29b-41d4-a716-446655440000",
      "name": "Basic Credit",
      "slug": "basic-credit",
      "description": "Entry-level credit plan",
      "plan_tier": "basic",
      "billing_cycle": "monthly",
      "price": "99.00",
      "duration": 30,
      "duration_unit": "days",
      "credit_limit": "2000.00",
      "interest_rate": "5.00",
      "deposit_percent": "15.00",
      "max_items_on_credit": 2,
      "repayment_days": 30,
      "grace_period_days": 3,
      "late_payment_penalty_percent": "2.00",
      "service_fee_discount_percent": "0.00",
      "delivery_fee_discount_percent": "0.00",
      "features": ["Basic credit access", "2 items on credit"],
      "requires_follower": true,
      "trial_days": 0,
      "sort_order": 0,
      "paystack_plan_code": "PLN_xxxxxxxxxxxx",
      "callback_url": "https://yourapp.com/subscription/callback",
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-04-10T00:00:00Z"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `paystack_plan_code` | string | Paystack plan code (auto-synced, never null for active plans) |
| `callback_url` | string/null | Default Paystack callback URL from server config |

### 2.2 Get Plan Detail

```
GET /api/subscriptions/plans/{slug}/
```

**Auth:** Public

**Response:** Same plan object as in list, including `paystack_plan_code` and `callback_url`.

### 2.3 Get My Subscription

```
GET /api/subscriptions/subscriptions/my-subscription/
```

**Auth:** Required (Customer)

**Response (has subscription) `200 OK`:**

```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440000",
  "plan": "bb0e8400-e29b-41d4-a716-446655440000",
  "plan_name": "Premium Credit",
  "plan_price": "199.00",
  "status": "active",
  "is_active": true,
  "started_at": "2026-04-01T00:00:00Z",
  "current_period_start": "2026-04-01T00:00:00Z",
  "current_period_end": "2026-05-01T00:00:00Z",
  "cancelled_at": null,
  "paystack_subscription_code": "SUB_xxxxxxxxxxxx",
  "paystack_customer_code": "CUS_xxxxxxxxxxxx",
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-01T00:00:00Z"
}
```

**Response (no subscription) `200 OK`:**

```json
{
  "status": "none",
  "message": "No active subscription.",
  "available_plans": [ /* Plan objects */ ]
}
```

**Subscription statuses:** `active`, `cancelled`, `expired`, `past_due`, `trialing`

### 2.4 Subscribe to Plan

Subscribes the customer and initializes a Paystack payment.

```
POST /api/subscriptions/subscriptions/subscribe/
```

**Auth:** Required (Customer only)

**Request Body:**

```json
{
  "plan_id": "bb0e8400-e29b-41d4-a716-446655440000",
  "callback_url": "https://yourapp.com/subscription/callback"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `plan_id` | UUID | Yes | Plan to subscribe to |
| `callback_url` | URL | No | Redirect after Paystack payment. Falls back to the server-configured `PAYSTACK_CALLBACK_URL` if omitted. |

**Response `201 Created`:**

```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440000",
  "plan": "bb0e8400-e29b-41d4-a716-446655440000",
  "plan_name": "Premium Credit",
  "plan_price": "199.00",
  "status": "active",
  "is_active": true,
  "started_at": "2026-04-01T00:00:00Z",
  "current_period_start": "2026-04-01T00:00:00Z",
  "current_period_end": "2026-05-01T00:00:00Z",
  "cancelled_at": null,
  "paystack_subscription_code": "",
  "paystack_customer_code": "CUS_xxxxxxxxxxxx",
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-01T00:00:00Z",
  "paystack": {
    "authorization_url": "https://checkout.paystack.com/xxxxxxxxxx",
    "access_code": "xxxxxxxxxxxxxxxxxx",
    "reference": "TXN-20260410-000002"
  }
}
```

> Redirect the user to `paystack.authorization_url` to complete payment.

**Errors:**
- `"Only customers can subscribe to credit plans."` — vendor tried to subscribe
- `"You already have an active subscription."` — already subscribed
- `"Plan not found or not available."` — invalid plan_id

### 2.5 Cancel Subscription

```
POST /api/subscriptions/subscriptions/cancel/
```

**Auth:** Required (Customer)

**Response `200 OK`:** Subscription object with `status: "cancelled"`.

### 2.6 Manage Subscription Card

Get a Paystack-hosted link where the customer can update their payment card.

```
GET /api/subscriptions/subscriptions/manage-card/
```

**Auth:** Required (Customer)

**Response `200 OK`:**

```json
{
  "link": "https://paystack.com/manage/subscriptions/xxxxxxxxxx"
}
```

---

## 3. Vendor Endpoints

### 3.1 List Business Tiers

```
GET /api/tiers/plans/
```

**Auth:** Public

**Behavior:** Automatically syncs any paid tiers with missing `paystack_plan_code` to Paystack before returning results. Free tiers are skipped (they don't need Paystack plans).

**Response `200 OK`:**

```json
{
  "count": 3,
  "results": [
    {
      "id": "cc0e8400-e29b-41d4-a716-446655440000",
      "name": "Starter",
      "slug": "starter",
      "description": "Free tier for new vendors",
      "price": "0.00",
      "tier_level": 0,
      "duration": 30,
      "duration_unit": "days",
      "max_products": 20,
      "product_limit_display": "20",
      "commission_rate": "12.00",
      "search_priority_boost": "0.00",
      "featured_listings": false,
      "features": ["20 product listings", "Basic support"],
      "negotiation_enabled": false,
      "max_markup_percent": "10.00",
      "max_discount_percent": "5.00",
      "trial_days": 0,
      "is_free": true,
      "is_active": true,
      "paystack_plan_code": null,
      "callback_url": "https://yourapp.com/subscription/callback"
    },
    {
      "id": "dd0e8400-e29b-41d4-a716-446655440000",
      "name": "Growth",
      "slug": "growth",
      "description": "For growing businesses",
      "price": "299.00",
      "tier_level": 1,
      "is_free": false,
      "paystack_plan_code": "PLN_xxxxxxxxxxxx",
      "callback_url": "https://yourapp.com/subscription/callback",
      "...other fields..."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `paystack_plan_code` | string/null | Paystack plan code. Auto-synced for paid tiers. `null` for free tiers. |
| `callback_url` | string/null | Default Paystack callback URL from server config |

### 3.2 Get Tier Detail

```
GET /api/tiers/plans/{slug}/
```

**Auth:** Public

**Response:** Same tier object as in list, including `paystack_plan_code` and `callback_url`.

### 3.3 Get My Tier

```
GET /api/tiers/subscriptions/my-tier/
```

**Auth:** Required (Vendor)

**Response (has tier) `200 OK`:**

```json
{
  "id": "ee0e8400-e29b-41d4-a716-446655440000",
  "vendor": 5,
  "tier": "dd0e8400-e29b-41d4-a716-446655440000",
  "tier_name": "Growth",
  "tier_price": "299.00",
  "tier_level": 1,
  "status": "active",
  "is_active": true,
  "started_at": "2026-03-01T00:00:00Z",
  "current_period_start": "2026-04-01T00:00:00Z",
  "current_period_end": "2026-05-01T00:00:00Z",
  "cancelled_at": null,
  "paystack_subscription_code": "SUB_xxxxxxxxxxxx",
  "paystack_customer_code": "CUS_xxxxxxxxxxxx",
  "created_at": "2026-03-01T00:00:00Z",
  "updated_at": "2026-04-01T00:00:00Z"
}
```

**Response (no tier) `200 OK`:**

```json
{
  "detail": "No active tier subscription.",
  "available_tiers": [ /* Tier objects */ ]
}
```

### 3.4 Subscribe to Tier

For **free tiers**, activates immediately. For **paid tiers**, returns a Paystack payment URL.

```
POST /api/tiers/subscriptions/subscribe/
```

**Auth:** Required (Vendor only)

**Request Body:**

```json
{
  "tier_id": "dd0e8400-e29b-41d4-a716-446655440000",
  "callback_url": "https://yourapp.com/tier/callback"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tier_id` | UUID | Yes | Tier to subscribe to |
| `callback_url` | URL | No | Redirect after Paystack payment. Falls back to the server-configured `PAYSTACK_CALLBACK_URL` if omitted. Ignored for free tiers. |

**Response `201 Created` (paid tier):**

```json
{
  "id": "ee0e8400-e29b-41d4-a716-446655440000",
  "vendor": 5,
  "tier": "dd0e8400-e29b-41d4-a716-446655440000",
  "tier_name": "Growth",
  "tier_price": "299.00",
  "tier_level": 1,
  "status": "active",
  "is_active": true,
  "started_at": "2026-03-01T00:00:00Z",
  "current_period_start": "2026-04-01T00:00:00Z",
  "current_period_end": "2026-05-01T00:00:00Z",
  "cancelled_at": null,
  "paystack_subscription_code": "",
  "paystack_customer_code": "CUS_xxxxxxxxxxxx",
  "created_at": "2026-03-01T00:00:00Z",
  "updated_at": "2026-04-01T00:00:00Z",
  "paystack": {
    "authorization_url": "https://checkout.paystack.com/xxxxxxxxxx",
    "access_code": "xxxxxxxxxxxxxxxxxx",
    "reference": "TXN-20260410-000003"
  }
}
```

> Redirect the user to `paystack.authorization_url` to complete payment.

**Response `201 Created` (free tier):** Tier subscription object without `paystack` block.

**Errors:**
- `"Only vendors can subscribe to business tiers."` — customer tried to subscribe
- `"Tier not found or not available."` — invalid tier_id

### 3.5 Cancel Tier

```
POST /api/tiers/subscriptions/cancel/
```

**Auth:** Required (Vendor). Cannot cancel free tiers.

**Response `200 OK`:** Subscription object with `status: "cancelled"`.

### 3.6 Manage Tier Card

```
GET /api/tiers/subscriptions/manage-card/
```

**Auth:** Required (Vendor)

**Response `200 OK`:** `{"link": "https://paystack.com/manage/subscriptions/xxxxxxxxxx"}`

---

## 4. Admin-Only Endpoints

### 4.1 Sync Plan to Paystack

Creates the plan on Paystack and saves the `paystack_plan_code`. Note: plans are auto-synced on list, so this is only needed for manual re-sync.

```
POST /api/subscriptions/plans/{slug}/sync-paystack/
```

**Auth:** Admin only

**Response `200 OK`:**

```json
{
  "message": "Plan synced to Paystack.",
  "paystack_plan_code": "PLN_xxxxxxxxxxxx"
}
```

### 4.2 Sync Tier to Paystack

Creates the tier plan on Paystack. Free tiers are skipped. Note: paid tiers are auto-synced on list, so this is only needed for manual re-sync.

```
POST /api/tiers/plans/{slug}/sync-paystack/
```

**Auth:** Admin only

**Response `200 OK`:**

```json
{
  "message": "Tier synced to Paystack.",
  "paystack_plan_code": "PLN_xxxxxxxxxxxx"
}
```

---

## 5. Dart Models

> See [SANOA_PAYMENTS_API.md - Dart Models](SANOA_PAYMENTS_API.md#30-dart-models) for `SubscriptionPlan`, `CustomerSubscription`, `BusinessTier`, and `VendorTierSubscription` models.

---

## 6. Dart Subscription Service (Customer)

> See [SANOA_PAYMENTS_API.md - Dart Subscription Service](SANOA_PAYMENTS_API.md#34-dart-subscription-service-customer) for the complete Dart service class.

---

## 7. Dart Tier Service (Vendor)

> See [SANOA_PAYMENTS_API.md - Dart Tier Service](SANOA_PAYMENTS_API.md#35-dart-tier-service-vendor) for the complete Dart service class.

---

## 8. Payment & Subscription Flow

### Customer Subscription Flow

```
1. GET  /api/subscriptions/plans/                        → show plans (auto-synced, includes callback_url)
2. POST /api/subscriptions/subscriptions/subscribe/      → get Paystack URL (callback_url auto-applied)
3. Redirect user to authorization_url                    → Paystack checkout
4. User pays → Paystack webhook (charge.success)         → server marks active
5. Paystack webhook (subscription.create)                → server links sub code
6. GET  /api/subscriptions/subscriptions/my-subscription/ → confirm active
```

### Vendor Tier Flow

```
1. GET  /api/tiers/plans/                                → show tiers (paid auto-synced, includes callback_url)
2. POST /api/tiers/subscriptions/subscribe/              → free: instant / paid: Paystack URL (callback_url auto-applied)
3. (Paid) Redirect to authorization_url                  → Paystack checkout
4. User pays → webhook                                  → server activates
5. GET  /api/tiers/subscriptions/my-tier/                → confirm active
```

### Recurring Billing

Paystack handles recurring billing automatically:
- On each billing cycle, Paystack charges the saved card
- If payment succeeds → subscription stays `active`
- If payment fails → `invoice.payment_failed` webhook → status becomes `past_due`
- If subscription cancelled → `subscription.disable` webhook → status becomes `cancelled`

### Card Management

Both customers and vendors can update their payment card:
- `GET /api/subscriptions/subscriptions/manage-card/` (customer)
- `GET /api/tiers/subscriptions/manage-card/` (vendor)
- Returns a Paystack-hosted link to update the card on file
