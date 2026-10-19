# Sanoa Paystack Payments API - Complete Dart / Flutter Reference

> **Base URL:** `https://your-domain.com/api/`
>
> **Payment Gateway:** Paystack
>
> **Authentication:** JWT Bearer Token (`Authorization: Bearer <access_token>`)
>
> **Currency:** ZAR (South African Rand). Amounts in the API are in **rands** (e.g. `150.00`). Paystack expects **kobo/cents** internally (handled server-side).

---

## Table of Contents

### Customer / Vendor Endpoints
1. [Transactions - Initialize Payment](#1-initialize-transaction)
2. [Transactions - Verify Payment](#2-verify-transaction)
3. [Transactions - Charge Saved Card](#3-charge-saved-card)
4. [Transactions - List My Transactions](#4-list-my-transactions)
5. [Transactions - Get Transaction Detail](#5-get-transaction-detail)
6. [Refunds - Request Refund](#6-request-refund)
7. [Refunds - List My Refunds](#7-list-my-refunds)
8. [Disputes - List My Disputes](#8-list-my-disputes)
9. [Subaccounts - Create Subaccount (Vendor)](#9-create-subaccount-vendor)
10. [Subaccounts - Get My Subaccount (Vendor)](#10-get-my-subaccount-vendor)
11. [Subaccounts - Update My Subaccount (Vendor)](#11-update-my-subaccount-vendor)
12. [Banks - List Banks](#12-list-banks)
13. [Banks - Resolve Account Number](#13-resolve-account-number)
14. [Customer Subscriptions (Plans)](#14-customer-subscriptions-plans)
15. [Vendor Tier Subscriptions](#15-vendor-tier-subscriptions)

### Admin-Only Endpoints
16. [Transactions - List All Transactions](#16-list-all-transactions-admin)
17. [Refunds - List All Refunds](#17-list-all-refunds-admin)
18. [Refunds - Approve Refund](#18-approve-refund-admin)
19. [Disputes - List All Disputes](#19-list-all-disputes-admin)
20. [Disputes - Add Evidence](#20-add-evidence-admin)
21. [Disputes - Resolve Dispute](#21-resolve-dispute-admin)
22. [Disputes - Sync from Paystack](#22-sync-disputes-admin)
23. [Splits - List Splits](#23-list-splits-admin)
24. [Splits - Create Split](#24-create-split-admin)
25. [Splits - Add Subaccount to Split](#25-add-subaccount-to-split-admin)
26. [Splits - Remove Subaccount from Split](#26-remove-subaccount-from-split-admin)
27. [Subaccounts - List All](#27-list-all-subaccounts-admin)
28. [Payment Logs](#28-payment-logs-admin)
29. [Sync Plans/Tiers to Paystack](#29-sync-plans-tiers-admin)

### Dart Integration
30. [Dart Models](#30-dart-models)
31. [Dart Payment Service (Customer)](#31-dart-payment-service-customer)
32. [Dart Vendor Service](#32-dart-vendor-service)
33. [Dart Admin Service](#33-dart-admin-service)
34. [Dart Subscription Service (Customer)](#34-dart-subscription-service-customer)
35. [Dart Tier Service (Vendor)](#35-dart-tier-service-vendor)
36. [Webhook Events Reference](#36-webhook-events-reference)

---

## Endpoint Quick Reference

### Customer / Vendor Endpoints

| Method | Endpoint | Description | User Type |
|--------|----------|-------------|-----------|
| `POST` | `/api/payments/transactions/initialize/` | Initialize a payment | Customer |
| `GET` | `/api/payments/transactions/verify/{reference}/` | Verify a payment | Customer |
| `POST` | `/api/payments/transactions/charge-authorization/` | Charge saved card | Customer |
| `GET` | `/api/payments/transactions/` | List my transactions | Customer |
| `GET` | `/api/payments/transactions/{id}/` | Get transaction detail | Customer |
| `POST` | `/api/payments/refunds/request/` | Request a refund | Customer |
| `GET` | `/api/payments/refunds/` | List my refunds | Customer |
| `GET` | `/api/payments/disputes/` | List my disputes | Customer |
| `POST` | `/api/payments/subaccounts/` | Create subaccount | Vendor |
| `GET` | `/api/payments/subaccounts/my-subaccount/` | Get my subaccount | Vendor |
| `PUT` | `/api/payments/subaccounts/{id}/` | Update my subaccount | Vendor |
| `GET` | `/api/payments/banks/` | List supported banks | Any |
| `GET` | `/api/payments/banks/resolve/` | Resolve account number | Any |
| `GET` | `/api/subscriptions/plans/` | List credit plans | Public |
| `GET` | `/api/subscriptions/plans/{slug}/` | Get plan details | Public |
| `GET` | `/api/subscriptions/subscriptions/my-subscription/` | Get my subscription | Customer |
| `POST` | `/api/subscriptions/subscriptions/subscribe/` | Subscribe to plan | Customer |
| `POST` | `/api/subscriptions/subscriptions/cancel/` | Cancel subscription | Customer |
| `GET` | `/api/subscriptions/subscriptions/manage-card/` | Get card update link | Customer |
| `GET` | `/api/tiers/plans/` | List business tiers | Public |
| `GET` | `/api/tiers/plans/{slug}/` | Get tier details | Public |
| `GET` | `/api/tiers/subscriptions/my-tier/` | Get my tier | Vendor |
| `POST` | `/api/tiers/subscriptions/subscribe/` | Subscribe to tier | Vendor |
| `POST` | `/api/tiers/subscriptions/cancel/` | Cancel tier | Vendor |
| `GET` | `/api/tiers/subscriptions/manage-card/` | Get card update link | Vendor |

### Admin-Only Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/payments/transactions/` | List ALL transactions |
| `GET` | `/api/payments/refunds/` | List ALL refunds |
| `POST` | `/api/payments/refunds/{id}/approve/` | Approve & process refund via Paystack |
| `GET` | `/api/payments/disputes/` | List ALL disputes |
| `POST` | `/api/payments/disputes/{id}/add-evidence/` | Add evidence to dispute |
| `POST` | `/api/payments/disputes/{id}/resolve/` | Resolve a dispute |
| `POST` | `/api/payments/disputes/sync/` | Sync disputes from Paystack |
| `GET` | `/api/payments/splits/` | List transaction splits |
| `POST` | `/api/payments/splits/create_split/` | Create a split |
| `POST` | `/api/payments/splits/{id}/add-subaccount/` | Add subaccount to split |
| `POST` | `/api/payments/splits/{id}/remove-subaccount/` | Remove subaccount from split |
| `GET` | `/api/payments/subaccounts/` | List ALL subaccounts |
| `GET` | `/api/payments/logs/` | List payment logs |
| `POST` | `/api/subscriptions/plans/{slug}/sync-paystack/` | Sync plan to Paystack |
| `POST` | `/api/tiers/plans/{slug}/sync-paystack/` | Sync tier to Paystack |

---

# Customer / Vendor Endpoints

---

## 1. Initialize Transaction

Start a Paystack payment. Returns an `authorization_url` to redirect the customer to Paystack's checkout page.

```
POST /api/payments/transactions/initialize/
```

**Auth:** Required (Customer)

**Request Body:**

```json
{
  "amount": 250.00,
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "payment_intent": "order_payment",
  "callback_url": "https://yourapp.com/payment/callback",
  "channels": ["card", "bank_transfer", "eft"],
  "subaccount_code": "ACCT_xxxxxxxxxxxx",
  "split_code": "SPL_xxxxxxxxxxxx",
  "metadata": {"custom_field": "value"}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `amount` | decimal | Yes | Amount in rands (e.g. `250.00`) |
| `order_id` | UUID | No | Order to link the payment to |
| `payment_intent` | string | No | `order_payment` (default), `subscription`, `deposit` |
| `callback_url` | URL | No | Redirect URL after Paystack checkout |
| `channels` | list | No | Allowed channels: `card`, `bank`, `ussd`, `qr`, `mobile_money`, `bank_transfer`, `eft` |
| `subaccount_code` | string | No | Vendor subaccount code for split payment |
| `split_code` | string | No | Transaction split code for multi-way split |
| `metadata` | object | No | Custom metadata |

**Response `201 Created`:**

```json
{
  "authorization_url": "https://checkout.paystack.com/xxxxxxxxxx",
  "access_code": "xxxxxxxxxxxxxxxxxx",
  "reference": "TXN-20260410-000001",
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 2. Verify Transaction

Verify payment status after customer returns from Paystack checkout.

```
GET /api/payments/transactions/verify/{reference}/
```

**Auth:** Required (Customer)

**Response `200 OK`:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "reference": "TXN-20260410-000001",
  "payment_intent": "order_payment",
  "order": "660e8400-e29b-41d4-a716-446655440000",
  "order_number": "ORD-20260410-001",
  "user": 1,
  "user_email": "customer@example.com",
  "amount": "250.00",
  "currency": "ZAR",
  "paystack_fees": "5.75",
  "net_amount": "244.25",
  "status": "success",
  "channel": "card",
  "gateway_response": "Approved",
  "authorization_url": "",
  "access_code": "",
  "card_type": "visa",
  "last4": "4081",
  "bank": "Test Bank",
  "subaccount": null,
  "split": null,
  "ip_address": "127.0.0.1",
  "metadata": {},
  "paid_at": "2026-04-10T12:30:00Z",
  "created_at": "2026-04-10T12:25:00Z",
  "updated_at": "2026-04-10T12:30:00Z",
  "failure_reason": ""
}
```

**Status values:** `pending`, `success`, `failed`, `abandoned`, `reversed`

---

## 3. Charge Saved Card

Charge a returning customer using a previously saved card authorization code.

```
POST /api/payments/transactions/charge-authorization/
```

**Auth:** Required (Customer)

**Request Body:**

```json
{
  "amount": 150.00,
  "authorization_code": "AUTH_xxxxxxxxxx",
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "payment_intent": "order_payment",
  "subaccount_code": "ACCT_xxxxxxxxxxxx",
  "split_code": "SPL_xxxxxxxxxxxx",
  "metadata": {}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `amount` | decimal | Yes | Amount in rands |
| `authorization_code` | string | Yes | Saved card authorization code from a previous transaction |
| `order_id` | UUID | No | Order to link payment to |
| `payment_intent` | string | No | `order_payment` (default), `subscription`, `deposit` |
| `subaccount_code` | string | No | Vendor subaccount code |
| `split_code` | string | No | Split code |
| `metadata` | object | No | Custom metadata |

**Response `201 Created`:** Same as transaction object in [Verify Transaction](#2-verify-transaction).

---

## 4. List My Transactions

List the authenticated customer's transactions (paginated).

```
GET /api/payments/transactions/
```

**Auth:** Required (Customer)

**Response `200 OK`:**

```json
{
  "count": 15,
  "next": "https://your-domain.com/api/payments/transactions/?page=2",
  "previous": null,
  "results": [
    { /* Transaction object */ }
  ]
}
```

---

## 5. Get Transaction Detail

```
GET /api/payments/transactions/{id}/
```

**Auth:** Required (Owner or Admin)

**Response `200 OK`:** Single transaction object.

---

## 6. Request Refund

Customer requests a refund on a successful transaction. Refund stays `pending` until admin approves.

```
POST /api/payments/refunds/request/
```

**Auth:** Required (Customer)

**Request Body:**

```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": 100.00,
  "reason": "damaged_product",
  "customer_note": "Item arrived broken",
  "merchant_note": ""
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `transaction_id` | UUID | Yes | Transaction to refund |
| `amount` | decimal | No | Partial refund amount (defaults to full amount) |
| `reason` | string | No | `customer_request` (default), `damaged_product`, `wrong_product`, `not_as_described`, `duplicate_payment`, `fraud`, `other` |
| `customer_note` | string | No | Note from customer |
| `merchant_note` | string | No | Note for merchant |

**Response `201 Created`:**

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "paystack_refund_id": null,
  "transaction": "550e8400-e29b-41d4-a716-446655440000",
  "transaction_reference": "TXN-20260410-000001",
  "order": "660e8400-e29b-41d4-a716-446655440000",
  "user": 1,
  "user_email": "customer@example.com",
  "amount": "100.00",
  "currency": "ZAR",
  "reason": "damaged_product",
  "customer_note": "Item arrived broken",
  "merchant_note": "",
  "status": "pending",
  "approved_by": null,
  "admin_notes": "",
  "approved_at": null,
  "failure_reason": "",
  "processed_at": null,
  "created_at": "2026-04-10T14:00:00Z",
  "updated_at": "2026-04-10T14:00:00Z"
}
```

**Refund status values:** `pending`, `processing`, `processed`, `failed`

---

## 7. List My Refunds

```
GET /api/payments/refunds/
```

**Auth:** Required (Customer — sees own; Admin — sees all)

**Response `200 OK`:** Paginated list of refund objects.

---

## 8. List My Disputes

Disputes are created automatically via Paystack webhooks when a customer disputes a charge.

```
GET /api/payments/disputes/
```

**Auth:** Required (Customer — sees own; Admin — sees all)

**Response `200 OK`:**

```json
{
  "count": 1,
  "results": [
    {
      "id": "880e8400-e29b-41d4-a716-446655440000",
      "paystack_dispute_id": 12345,
      "transaction": "550e8400-e29b-41d4-a716-446655440000",
      "transaction_reference": "TXN-20260410-000001",
      "user": 1,
      "user_email": "customer@example.com",
      "amount": "250.00",
      "currency": "ZAR",
      "status": "awaiting-merchant-feedback",
      "category": "product-not-delivered",
      "resolution": "",
      "message": "I never received my order",
      "merchant_response": "",
      "evidence": {},
      "attachments": [],
      "due_at": "2026-04-20T00:00:00Z",
      "resolved_at": null,
      "created_at": "2026-04-10T15:00:00Z",
      "updated_at": "2026-04-10T15:00:00Z"
    }
  ]
}
```

**Dispute statuses:** `awaiting-merchant-feedback`, `awaiting-bank-feedback`, `pending`, `resolved`, `merchant-accepted`, `declined`

**Dispute categories:** `product-not-delivered`, `product-not-as-described`, `unauthorized-transaction`, `duplicate-charge`, `general`

---

## 9. Create Subaccount (Vendor)

Create a Paystack subaccount for the vendor to receive split payments.

```
POST /api/payments/subaccounts/
```

**Auth:** Required (Vendor only)

**Request Body:**

```json
{
  "business_name": "Fresh Produce Store",
  "settlement_bank": "058",
  "account_number": "0123456789",
  "percentage_charge": 5.00,
  "primary_contact_email": "vendor@example.com"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `business_name` | string | Yes | Business name for the subaccount |
| `settlement_bank` | string | Yes | Bank code from Paystack bank list (see [List Banks](#12-list-banks)) |
| `account_number` | string | Yes | Bank account number |
| `percentage_charge` | decimal | No | Percentage fee retained by main account (default `0`) |
| `primary_contact_email` | email | No | Contact email (defaults to vendor's email) |

**Response `201 Created`:**

```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "vendor": 5,
  "vendor_email": "vendor@example.com",
  "subaccount_code": "ACCT_xxxxxxxxxxxx",
  "business_name": "Fresh Produce Store",
  "settlement_bank": "058",
  "account_number": "0123456789",
  "bank_name": "Guaranty Trust Bank",
  "account_name": "FRESH PRODUCE STORE",
  "percentage_charge": "5.00",
  "flat_charge": "0.00",
  "primary_contact_email": "vendor@example.com",
  "is_active": true,
  "metadata": {},
  "created_at": "2026-04-10T10:00:00Z",
  "updated_at": "2026-04-10T10:00:00Z"
}
```

---

## 10. Get My Subaccount (Vendor)

```
GET /api/payments/subaccounts/my-subaccount/
```

**Auth:** Required (Vendor)

**Response `200 OK`:** Subaccount object (same as above).

**Response `404 Not Found`:** `{"detail": "No subaccount found. Create one first."}`

---

## 11. Update My Subaccount (Vendor)

```
PUT /api/payments/subaccounts/{id}/
```

**Auth:** Required (Vendor — own subaccount only)

**Request Body (partial):**

```json
{
  "business_name": "New Business Name",
  "settlement_bank": "058",
  "account_number": "9876543210"
}
```

**Response `200 OK`:** Updated subaccount object.

---

## 12. List Banks

Get list of banks supported by Paystack for subaccount creation.

```
GET /api/payments/banks/?country=south africa
```

**Auth:** Required

**Query Params:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `country` | string | `south africa` | Country to list banks for |

**Response `200 OK`:**

```json
[
  {
    "id": 1,
    "name": "Access Bank",
    "slug": "access-bank",
    "code": "044",
    "country": "South Africa",
    "currency": "ZAR",
    "type": "nuban"
  }
]
```

---

## 13. Resolve Account Number

Verify a bank account number and get the account holder's name before creating a subaccount.

```
GET /api/payments/banks/resolve/?account_number=0123456789&bank_code=058
```

**Auth:** Required

**Query Params:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `account_number` | string | Yes | Bank account number |
| `bank_code` | string | Yes | Bank code from [List Banks](#12-list-banks) |

**Response `200 OK`:**

```json
{
  "account_number": "0123456789",
  "account_name": "JOHN DOE",
  "bank_id": 1
}
```

---

## 14. Customer Subscriptions (Plans)

### 14.1 List Credit Plans

```
GET /api/subscriptions/plans/
```

**Auth:** Public

### 14.2 Get Plan Detail

```
GET /api/subscriptions/plans/{slug}/
```

**Auth:** Public

### 14.3 Get My Subscription

```
GET /api/subscriptions/subscriptions/my-subscription/
```

**Auth:** Required (Customer)

**Response (active subscription) `200 OK`:**

```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440000",
  "plan": "bb0e8400-e29b-41d4-a716-446655440000",
  "plan_name": "Premium",
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

### 14.4 Subscribe to Plan

Subscribes the customer and returns a Paystack payment URL.

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

**Response `201 Created`:**

```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440000",
  "plan": "bb0e8400-e29b-41d4-a716-446655440000",
  "plan_name": "Premium",
  "plan_price": "199.00",
  "status": "active",
  "is_active": true,
  "paystack_subscription_code": "",
  "paystack_customer_code": "CUS_xxxxxxxxxxxx",
  "paystack": {
    "authorization_url": "https://checkout.paystack.com/xxxxxxxxxx",
    "access_code": "xxxxxxxxxxxxxxxxxx",
    "reference": "TXN-20260410-000002"
  },
  "...other fields..."
}
```

> **Important:** Redirect the user to `paystack.authorization_url` to complete payment. The subscription activates after Paystack confirms payment via webhook.

### 14.5 Cancel Subscription

```
POST /api/subscriptions/subscriptions/cancel/
```

**Auth:** Required (Customer)

**Response `200 OK`:** Updated subscription object with `status: "cancelled"`.

### 14.6 Manage Subscription Card

Get a Paystack-hosted link to update the card on file.

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

## 15. Vendor Tier Subscriptions

### 15.1 List Business Tiers

```
GET /api/tiers/plans/
```

**Auth:** Public

### 15.2 Get Tier Detail

```
GET /api/tiers/plans/{slug}/
```

**Auth:** Public

### 15.3 Get My Tier

```
GET /api/tiers/subscriptions/my-tier/
```

**Auth:** Required (Vendor)

### 15.4 Subscribe to Tier

For paid tiers, returns a Paystack payment URL. Free tiers activate immediately.

```
POST /api/tiers/subscriptions/subscribe/
```

**Auth:** Required (Vendor only)

**Request Body:**

```json
{
  "tier_id": "cc0e8400-e29b-41d4-a716-446655440000",
  "callback_url": "https://yourapp.com/tier/callback"
}
```

**Response `201 Created`:** Tier subscription object with optional `paystack` block (same shape as plan subscribe).

### 15.5 Cancel Tier

```
POST /api/tiers/subscriptions/cancel/
```

**Auth:** Required (Vendor). Cannot cancel free tiers.

### 15.6 Manage Tier Card

```
GET /api/tiers/subscriptions/manage-card/
```

**Auth:** Required (Vendor)

**Response `200 OK`:** `{"link": "https://paystack.com/manage/subscriptions/xxxxxxxxxx"}`

---

# Admin-Only Endpoints

> All admin endpoints require `Authorization: Bearer <admin_access_token>` and the user must be `is_staff=True`.

---

## 16. List All Transactions (Admin)

Admins see all transactions across all users.

```
GET /api/payments/transactions/
```

**Response `200 OK`:** Paginated list of all transaction objects.

---

## 17. List All Refunds (Admin)

```
GET /api/payments/refunds/
```

**Response `200 OK`:** Paginated list of all refund objects.

---

## 18. Approve Refund (Admin)

Approve a pending refund and process it via Paystack. The refund is sent to Paystack immediately.

```
POST /api/payments/refunds/{id}/approve/
```

**Request Body (optional):**

```json
{
  "admin_notes": "Approved – customer provided photo evidence"
}
```

**Response `200 OK`:**

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "paystack_refund_id": 67890,
  "status": "processing",
  "approved_by": 1,
  "approved_at": "2026-04-10T16:00:00Z",
  "admin_notes": "Approved – customer provided photo evidence",
  "...other fields..."
}
```

**Error `400`:** `{"error": "Only pending refunds can be approved."}`

---

## 19. List All Disputes (Admin)

```
GET /api/payments/disputes/
```

**Response `200 OK`:** Paginated list of all dispute objects.

---

## 20. Add Evidence (Admin)

Add evidence to a dispute for Paystack review.

```
POST /api/payments/disputes/{id}/add-evidence/
```

**Request Body:**

```json
{
  "customer_email": "customer@example.com",
  "customer_name": "John Doe",
  "customer_phone": "+27123456789",
  "service_details": "Order #ORD-20260410-001 shipped on 2026-04-05",
  "delivery_address": "123 Main St, Cape Town",
  "description": "Item was delivered and signed for on 2026-04-07"
}
```

All fields are optional. Include as much evidence as possible.

**Response `200 OK`:** Updated dispute object with evidence.

---

## 21. Resolve Dispute (Admin)

```
POST /api/payments/disputes/{id}/resolve/
```

**Request Body:**

```json
{
  "resolution": "merchant-accepted",
  "message": "We accept this dispute and will refund the customer.",
  "refund_amount": 250.00,
  "upload_url": "https://example.com/evidence.pdf"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `resolution` | string | Yes | `merchant-accepted` or `declined` |
| `message` | string | Yes | Resolution message |
| `refund_amount` | decimal | No | Amount to refund (if accepting) |
| `upload_url` | URL | No | Evidence document URL |

**Response `200 OK`:** Updated dispute object with `status: "resolved"`.

---

## 22. Sync Disputes (Admin)

Pull latest disputes from Paystack and create local records for any new ones.

```
POST /api/payments/disputes/sync/
```

**Response `200 OK`:**

```json
{
  "synced": 3
}
```

---

## 23. List Splits (Admin)

```
GET /api/payments/splits/
```

**Response `200 OK`:**

```json
{
  "results": [
    {
      "id": "dd0e8400-e29b-41d4-a716-446655440000",
      "name": "Marketplace Split",
      "paystack_split_code": "SPL_xxxxxxxxxxxx",
      "split_type": "percentage",
      "currency": "ZAR",
      "bearer_type": "account",
      "bearer_subaccount": "",
      "is_active": true,
      "subaccounts": [
        {
          "id": 1,
          "subaccount": "990e8400-e29b-41d4-a716-446655440000",
          "subaccount_code": "ACCT_xxxxxxxxxxxx",
          "business_name": "Fresh Produce Store",
          "share": 80
        }
      ],
      "created_at": "2026-04-10T10:00:00Z",
      "updated_at": "2026-04-10T10:00:00Z"
    }
  ]
}
```

---

## 24. Create Split (Admin)

```
POST /api/payments/splits/create_split/
```

**Request Body:**

```json
{
  "name": "Marketplace Split",
  "split_type": "percentage",
  "currency": "ZAR",
  "bearer_type": "account",
  "bearer_subaccount": "",
  "subaccounts": [
    {"subaccount": "ACCT_xxxxxxxxxxxx", "share": 80},
    {"subaccount": "ACCT_yyyyyyyyyyyy", "share": 20}
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Split name |
| `split_type` | string | Yes | `percentage` or `flat` |
| `currency` | string | No | Default `ZAR` |
| `bearer_type` | string | No | `account` (default), `subaccount`, `all-proportional`, `all` |
| `bearer_subaccount` | string | No | Subaccount code if bearer_type is `subaccount` |
| `subaccounts` | list | Yes | Array of `{subaccount: "<code>", share: <int>}` |

**Response `201 Created`:** Split object.

---

## 25. Add Subaccount to Split (Admin)

```
POST /api/payments/splits/{id}/add-subaccount/
```

**Request Body:**

```json
{
  "subaccount": "ACCT_xxxxxxxxxxxx",
  "share": 30
}
```

**Response `200 OK`:** Updated split object.

---

## 26. Remove Subaccount from Split (Admin)

```
POST /api/payments/splits/{id}/remove-subaccount/
```

**Request Body:**

```json
{
  "subaccount": "ACCT_xxxxxxxxxxxx"
}
```

**Response `200 OK`:** Updated split object.

---

## 27. List All Subaccounts (Admin)

```
GET /api/payments/subaccounts/
```

**Response `200 OK`:** Paginated list of all vendor subaccounts.

---

## 28. Payment Logs (Admin)

```
GET /api/payments/logs/
```

**Response `200 OK`:**

```json
{
  "results": [
    {
      "id": 1,
      "transaction": "550e8400-e29b-41d4-a716-446655440000",
      "refund": null,
      "dispute": null,
      "log_type": "transaction_success",
      "message": "Payment successful via webhook: TXN-20260410-000001",
      "http_status_code": null,
      "ip_address": "127.0.0.1",
      "created_at": "2026-04-10T12:30:00Z"
    }
  ]
}
```

**Log types:** `transaction_initialized`, `transaction_verified`, `transaction_success`, `transaction_failed`, `charge_authorization`, `refund_requested`, `refund_processed`, `refund_failed`, `dispute_created`, `dispute_resolved`, `subaccount_created`, `split_created`, `subscription_created`, `webhook_received`, `api_call`, `error`

---

## 29. Sync Plans/Tiers (Admin)

### Sync a Customer Plan to Paystack

```
POST /api/subscriptions/plans/{slug}/sync-paystack/
```

**Response `200 OK`:**

```json
{
  "message": "Plan synced to Paystack.",
  "paystack_plan_code": "PLN_xxxxxxxxxxxx"
}
```

### Sync a Vendor Tier to Paystack

```
POST /api/tiers/plans/{slug}/sync-paystack/
```

**Response `200 OK`:**

```json
{
  "message": "Tier synced to Paystack.",
  "paystack_plan_code": "PLN_xxxxxxxxxxxx"
}
```

---

# Dart Integration

---

## 30. Dart Models

```dart
class PaystackTransaction {
  final String id;
  final String reference;
  final String paymentIntent;
  final String? orderId;
  final String? orderNumber;
  final int userId;
  final String userEmail;
  final double amount;
  final String currency;
  final double paystackFees;
  final double netAmount;
  final String status;
  final String channel;
  final String gatewayResponse;
  final String? authorizationUrl;
  final String? accessCode;
  final String? cardType;
  final String? last4;
  final String? bank;
  final String? subaccount;
  final String? split;
  final String? ipAddress;
  final Map<String, dynamic> metadata;
  final DateTime? paidAt;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String? failureReason;

  PaystackTransaction({
    required this.id,
    required this.reference,
    required this.paymentIntent,
    this.orderId,
    this.orderNumber,
    required this.userId,
    required this.userEmail,
    required this.amount,
    required this.currency,
    required this.paystackFees,
    required this.netAmount,
    required this.status,
    required this.channel,
    required this.gatewayResponse,
    this.authorizationUrl,
    this.accessCode,
    this.cardType,
    this.last4,
    this.bank,
    this.subaccount,
    this.split,
    this.ipAddress,
    required this.metadata,
    this.paidAt,
    required this.createdAt,
    required this.updatedAt,
    this.failureReason,
  });

  bool get isSuccessful => status == 'success';
  bool get isPending => status == 'pending';
  bool get isFailed => status == 'failed';

  factory PaystackTransaction.fromJson(Map<String, dynamic> json) {
    return PaystackTransaction(
      id: json['id'],
      reference: json['reference'],
      paymentIntent: json['payment_intent'],
      orderId: json['order'],
      orderNumber: json['order_number'],
      userId: json['user'],
      userEmail: json['user_email'],
      amount: double.parse(json['amount'].toString()),
      currency: json['currency'],
      paystackFees: double.parse(json['paystack_fees'].toString()),
      netAmount: double.parse(json['net_amount'].toString()),
      status: json['status'],
      channel: json['channel'] ?? '',
      gatewayResponse: json['gateway_response'] ?? '',
      authorizationUrl: json['authorization_url'],
      accessCode: json['access_code'],
      cardType: json['card_type'],
      last4: json['last4'],
      bank: json['bank'],
      subaccount: json['subaccount']?.toString(),
      split: json['split']?.toString(),
      ipAddress: json['ip_address'],
      metadata: Map<String, dynamic>.from(json['metadata'] ?? {}),
      paidAt: json['paid_at'] != null ? DateTime.parse(json['paid_at']) : null,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
      failureReason: json['failure_reason'],
    );
  }
}

class InitializeResponse {
  final String authorizationUrl;
  final String accessCode;
  final String reference;
  final String transactionId;

  InitializeResponse({
    required this.authorizationUrl,
    required this.accessCode,
    required this.reference,
    required this.transactionId,
  });

  factory InitializeResponse.fromJson(Map<String, dynamic> json) {
    return InitializeResponse(
      authorizationUrl: json['authorization_url'],
      accessCode: json['access_code'],
      reference: json['reference'],
      transactionId: json['transaction_id'],
    );
  }
}

class PaystackRefund {
  final String id;
  final int? paystackRefundId;
  final String transactionId;
  final String transactionReference;
  final String? orderId;
  final int userId;
  final String userEmail;
  final double amount;
  final String currency;
  final String reason;
  final String customerNote;
  final String merchantNote;
  final String status;
  final int? approvedBy;
  final String adminNotes;
  final DateTime? approvedAt;
  final String failureReason;
  final DateTime? processedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  PaystackRefund({
    required this.id,
    this.paystackRefundId,
    required this.transactionId,
    required this.transactionReference,
    this.orderId,
    required this.userId,
    required this.userEmail,
    required this.amount,
    required this.currency,
    required this.reason,
    required this.customerNote,
    required this.merchantNote,
    required this.status,
    this.approvedBy,
    required this.adminNotes,
    this.approvedAt,
    required this.failureReason,
    this.processedAt,
    required this.createdAt,
    required this.updatedAt,
  });

  bool get isPending => status == 'pending';
  bool get isProcessed => status == 'processed';

  factory PaystackRefund.fromJson(Map<String, dynamic> json) {
    return PaystackRefund(
      id: json['id'],
      paystackRefundId: json['paystack_refund_id'],
      transactionId: json['transaction'],
      transactionReference: json['transaction_reference'],
      orderId: json['order'],
      userId: json['user'],
      userEmail: json['user_email'],
      amount: double.parse(json['amount'].toString()),
      currency: json['currency'],
      reason: json['reason'],
      customerNote: json['customer_note'] ?? '',
      merchantNote: json['merchant_note'] ?? '',
      status: json['status'],
      approvedBy: json['approved_by'],
      adminNotes: json['admin_notes'] ?? '',
      approvedAt: json['approved_at'] != null ? DateTime.parse(json['approved_at']) : null,
      failureReason: json['failure_reason'] ?? '',
      processedAt: json['processed_at'] != null ? DateTime.parse(json['processed_at']) : null,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

class PaystackDispute {
  final String id;
  final int? paystackDisputeId;
  final String transactionId;
  final String transactionReference;
  final int userId;
  final String userEmail;
  final double amount;
  final String currency;
  final String status;
  final String category;
  final String resolution;
  final String message;
  final String merchantResponse;
  final Map<String, dynamic> evidence;
  final List<dynamic> attachments;
  final DateTime? dueAt;
  final DateTime? resolvedAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  PaystackDispute({
    required this.id,
    this.paystackDisputeId,
    required this.transactionId,
    required this.transactionReference,
    required this.userId,
    required this.userEmail,
    required this.amount,
    required this.currency,
    required this.status,
    required this.category,
    required this.resolution,
    required this.message,
    required this.merchantResponse,
    required this.evidence,
    required this.attachments,
    this.dueAt,
    this.resolvedAt,
    required this.createdAt,
    required this.updatedAt,
  });

  factory PaystackDispute.fromJson(Map<String, dynamic> json) {
    return PaystackDispute(
      id: json['id'],
      paystackDisputeId: json['paystack_dispute_id'],
      transactionId: json['transaction'],
      transactionReference: json['transaction_reference'],
      userId: json['user'],
      userEmail: json['user_email'],
      amount: double.parse(json['amount'].toString()),
      currency: json['currency'],
      status: json['status'],
      category: json['category'],
      resolution: json['resolution'] ?? '',
      message: json['message'] ?? '',
      merchantResponse: json['merchant_response'] ?? '',
      evidence: Map<String, dynamic>.from(json['evidence'] ?? {}),
      attachments: List<dynamic>.from(json['attachments'] ?? []),
      dueAt: json['due_at'] != null ? DateTime.parse(json['due_at']) : null,
      resolvedAt: json['resolved_at'] != null ? DateTime.parse(json['resolved_at']) : null,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

class PaystackSubaccount {
  final String id;
  final int vendorId;
  final String vendorEmail;
  final String subaccountCode;
  final String businessName;
  final String settlementBank;
  final String accountNumber;
  final String bankName;
  final String accountName;
  final double percentageCharge;
  final double flatCharge;
  final String primaryContactEmail;
  final bool isActive;
  final DateTime createdAt;
  final DateTime updatedAt;

  PaystackSubaccount({
    required this.id,
    required this.vendorId,
    required this.vendorEmail,
    required this.subaccountCode,
    required this.businessName,
    required this.settlementBank,
    required this.accountNumber,
    required this.bankName,
    required this.accountName,
    required this.percentageCharge,
    required this.flatCharge,
    required this.primaryContactEmail,
    required this.isActive,
    required this.createdAt,
    required this.updatedAt,
  });

  factory PaystackSubaccount.fromJson(Map<String, dynamic> json) {
    return PaystackSubaccount(
      id: json['id'],
      vendorId: json['vendor'],
      vendorEmail: json['vendor_email'],
      subaccountCode: json['subaccount_code'],
      businessName: json['business_name'],
      settlementBank: json['settlement_bank'],
      accountNumber: json['account_number'],
      bankName: json['bank_name'] ?? '',
      accountName: json['account_name'] ?? '',
      percentageCharge: double.parse(json['percentage_charge'].toString()),
      flatCharge: double.parse(json['flat_charge'].toString()),
      primaryContactEmail: json['primary_contact_email'] ?? '',
      isActive: json['is_active'],
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

class PaystackBank {
  final int id;
  final String name;
  final String slug;
  final String code;
  final String country;
  final String currency;
  final String type;

  PaystackBank({
    required this.id,
    required this.name,
    required this.slug,
    required this.code,
    required this.country,
    required this.currency,
    required this.type,
  });

  factory PaystackBank.fromJson(Map<String, dynamic> json) {
    return PaystackBank(
      id: json['id'],
      name: json['name'],
      slug: json['slug'],
      code: json['code'],
      country: json['country'] ?? '',
      currency: json['currency'] ?? '',
      type: json['type'] ?? '',
    );
  }
}

class ResolvedAccount {
  final String accountNumber;
  final String accountName;
  final int bankId;

  ResolvedAccount({
    required this.accountNumber,
    required this.accountName,
    required this.bankId,
  });

  factory ResolvedAccount.fromJson(Map<String, dynamic> json) {
    return ResolvedAccount(
      accountNumber: json['account_number'],
      accountName: json['account_name'],
      bankId: json['bank_id'] ?? 0,
    );
  }
}

class TransactionSplit {
  final String id;
  final String name;
  final String paystackSplitCode;
  final String splitType;
  final String currency;
  final String bearerType;
  final String bearerSubaccount;
  final bool isActive;
  final List<SplitSubaccountEntry> subaccounts;
  final DateTime createdAt;
  final DateTime updatedAt;

  TransactionSplit({
    required this.id,
    required this.name,
    required this.paystackSplitCode,
    required this.splitType,
    required this.currency,
    required this.bearerType,
    required this.bearerSubaccount,
    required this.isActive,
    required this.subaccounts,
    required this.createdAt,
    required this.updatedAt,
  });

  factory TransactionSplit.fromJson(Map<String, dynamic> json) {
    return TransactionSplit(
      id: json['id'],
      name: json['name'],
      paystackSplitCode: json['paystack_split_code'] ?? '',
      splitType: json['split_type'],
      currency: json['currency'],
      bearerType: json['bearer_type'],
      bearerSubaccount: json['bearer_subaccount'] ?? '',
      isActive: json['is_active'],
      subaccounts: (json['subaccounts'] as List? ?? [])
          .map((e) => SplitSubaccountEntry.fromJson(e))
          .toList(),
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

class SplitSubaccountEntry {
  final int id;
  final String subaccountId;
  final String subaccountCode;
  final String businessName;
  final int share;

  SplitSubaccountEntry({
    required this.id,
    required this.subaccountId,
    required this.subaccountCode,
    required this.businessName,
    required this.share,
  });

  factory SplitSubaccountEntry.fromJson(Map<String, dynamic> json) {
    return SplitSubaccountEntry(
      id: json['id'],
      subaccountId: json['subaccount'],
      subaccountCode: json['subaccount_code'],
      businessName: json['business_name'],
      share: json['share'],
    );
  }
}

class SubscriptionPlan {
  final String id;
  final String name;
  final String slug;
  final String description;
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
  final List<dynamic> features;
  final bool requiresFollower;
  final int trialDays;
  final int sortOrder;
  final String? paystackPlanCode;

  SubscriptionPlan({
    required this.id,
    required this.name,
    required this.slug,
    required this.description,
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
    this.paystackPlanCode,
  });

  factory SubscriptionPlan.fromJson(Map<String, dynamic> json) {
    return SubscriptionPlan(
      id: json['id'],
      name: json['name'],
      slug: json['slug'],
      description: json['description'] ?? '',
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
      latePaymentPenaltyPercent: double.parse(json['late_payment_penalty_percent'].toString()),
      serviceFeeDiscountPercent: double.parse(json['service_fee_discount_percent'].toString()),
      deliveryFeeDiscountPercent: double.parse(json['delivery_fee_discount_percent'].toString()),
      features: json['features'] ?? [],
      requiresFollower: json['requires_follower'],
      trialDays: json['trial_days'],
      sortOrder: json['sort_order'],
      paystackPlanCode: json['paystack_plan_code'],
    );
  }
}

class CustomerSubscription {
  final String id;
  final String planId;
  final String planName;
  final double planPrice;
  final String status;
  final bool isActive;
  final DateTime startedAt;
  final DateTime currentPeriodStart;
  final DateTime currentPeriodEnd;
  final DateTime? cancelledAt;
  final String paystackSubscriptionCode;
  final String paystackCustomerCode;
  final DateTime createdAt;
  final DateTime updatedAt;

  CustomerSubscription({
    required this.id,
    required this.planId,
    required this.planName,
    required this.planPrice,
    required this.status,
    required this.isActive,
    required this.startedAt,
    required this.currentPeriodStart,
    required this.currentPeriodEnd,
    this.cancelledAt,
    required this.paystackSubscriptionCode,
    required this.paystackCustomerCode,
    required this.createdAt,
    required this.updatedAt,
  });

  factory CustomerSubscription.fromJson(Map<String, dynamic> json) {
    return CustomerSubscription(
      id: json['id'],
      planId: json['plan'],
      planName: json['plan_name'],
      planPrice: double.parse(json['plan_price'].toString()),
      status: json['status'],
      isActive: json['is_active'],
      startedAt: DateTime.parse(json['started_at']),
      currentPeriodStart: DateTime.parse(json['current_period_start']),
      currentPeriodEnd: DateTime.parse(json['current_period_end']),
      cancelledAt: json['cancelled_at'] != null ? DateTime.parse(json['cancelled_at']) : null,
      paystackSubscriptionCode: json['paystack_subscription_code'] ?? '',
      paystackCustomerCode: json['paystack_customer_code'] ?? '',
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

class BusinessTier {
  final String id;
  final String name;
  final String slug;
  final String description;
  final double price;
  final int tierLevel;
  final int duration;
  final String durationUnit;
  final int maxProducts;
  final String productLimitDisplay;
  final double commissionRate;
  final double searchPriorityBoost;
  final bool featuredListings;
  final List<dynamic> features;
  final bool negotiationEnabled;
  final double maxMarkupPercent;
  final double maxDiscountPercent;
  final int trialDays;
  final bool isFree;
  final bool isActive;
  final String? paystackPlanCode;

  BusinessTier({
    required this.id,
    required this.name,
    required this.slug,
    required this.description,
    required this.price,
    required this.tierLevel,
    required this.duration,
    required this.durationUnit,
    required this.maxProducts,
    required this.productLimitDisplay,
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
    this.paystackPlanCode,
  });

  factory BusinessTier.fromJson(Map<String, dynamic> json) {
    return BusinessTier(
      id: json['id'],
      name: json['name'],
      slug: json['slug'],
      description: json['description'] ?? '',
      price: double.parse(json['price'].toString()),
      tierLevel: json['tier_level'],
      duration: json['duration'],
      durationUnit: json['duration_unit'],
      maxProducts: json['max_products'],
      productLimitDisplay: json['product_limit_display'],
      commissionRate: double.parse(json['commission_rate'].toString()),
      searchPriorityBoost: double.parse(json['search_priority_boost'].toString()),
      featuredListings: json['featured_listings'],
      features: json['features'] ?? [],
      negotiationEnabled: json['negotiation_enabled'],
      maxMarkupPercent: double.parse(json['max_markup_percent'].toString()),
      maxDiscountPercent: double.parse(json['max_discount_percent'].toString()),
      trialDays: json['trial_days'],
      isFree: json['is_free'],
      isActive: json['is_active'],
      paystackPlanCode: json['paystack_plan_code'],
    );
  }
}

class VendorTierSubscription {
  final String id;
  final int vendorId;
  final String tierId;
  final String tierName;
  final double tierPrice;
  final int tierLevel;
  final String status;
  final bool isActive;
  final DateTime startedAt;
  final DateTime currentPeriodStart;
  final DateTime currentPeriodEnd;
  final DateTime? cancelledAt;
  final String paystackSubscriptionCode;
  final String paystackCustomerCode;
  final DateTime createdAt;
  final DateTime updatedAt;

  VendorTierSubscription({
    required this.id,
    required this.vendorId,
    required this.tierId,
    required this.tierName,
    required this.tierPrice,
    required this.tierLevel,
    required this.status,
    required this.isActive,
    required this.startedAt,
    required this.currentPeriodStart,
    required this.currentPeriodEnd,
    this.cancelledAt,
    required this.paystackSubscriptionCode,
    required this.paystackCustomerCode,
    required this.createdAt,
    required this.updatedAt,
  });

  factory VendorTierSubscription.fromJson(Map<String, dynamic> json) {
    return VendorTierSubscription(
      id: json['id'],
      vendorId: json['vendor'],
      tierId: json['tier'],
      tierName: json['tier_name'],
      tierPrice: double.parse(json['tier_price'].toString()),
      tierLevel: json['tier_level'],
      status: json['status'],
      isActive: json['is_active'],
      startedAt: DateTime.parse(json['started_at']),
      currentPeriodStart: DateTime.parse(json['current_period_start']),
      currentPeriodEnd: DateTime.parse(json['current_period_end']),
      cancelledAt: json['cancelled_at'] != null ? DateTime.parse(json['cancelled_at']) : null,
      paystackSubscriptionCode: json['paystack_subscription_code'] ?? '',
      paystackCustomerCode: json['paystack_customer_code'] ?? '',
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}
```

---

## 31. Dart Payment Service (Customer)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class PaymentService {
  final String baseUrl;
  final String token;

  PaymentService({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  // ── Transactions ────────────────────────────────────────

  /// Initialize a Paystack transaction. Returns authorization_url to redirect user.
  Future<InitializeResponse> initializeTransaction({
    required double amount,
    String? orderId,
    String paymentIntent = 'order_payment',
    String? callbackUrl,
    List<String>? channels,
    String? subaccountCode,
    String? splitCode,
    Map<String, dynamic>? metadata,
  }) async {
    final body = <String, dynamic>{
      'amount': amount,
      'payment_intent': paymentIntent,
    };
    if (orderId != null) body['order_id'] = orderId;
    if (callbackUrl != null) body['callback_url'] = callbackUrl;
    if (channels != null) body['channels'] = channels;
    if (subaccountCode != null) body['subaccount_code'] = subaccountCode;
    if (splitCode != null) body['split_code'] = splitCode;
    if (metadata != null) body['metadata'] = metadata;

    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/transactions/initialize/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 201) {
      return InitializeResponse.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to initialize');
  }

  /// Verify a transaction after customer returns from Paystack checkout.
  Future<PaystackTransaction> verifyTransaction(String reference) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/payments/transactions/verify/$reference/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return PaystackTransaction.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Verification failed');
  }

  /// Charge a saved card (recurring payment).
  Future<PaystackTransaction> chargeAuthorization({
    required double amount,
    required String authorizationCode,
    String? orderId,
    String paymentIntent = 'order_payment',
    String? subaccountCode,
    String? splitCode,
    Map<String, dynamic>? metadata,
  }) async {
    final body = <String, dynamic>{
      'amount': amount,
      'authorization_code': authorizationCode,
      'payment_intent': paymentIntent,
    };
    if (orderId != null) body['order_id'] = orderId;
    if (subaccountCode != null) body['subaccount_code'] = subaccountCode;
    if (splitCode != null) body['split_code'] = splitCode;
    if (metadata != null) body['metadata'] = metadata;

    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/transactions/charge-authorization/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 201) {
      return PaystackTransaction.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Charge failed');
  }

  /// List the customer's transactions (paginated).
  Future<List<PaystackTransaction>> listTransactions({int page = 1}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/payments/transactions/?page=$page'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['results'] as List)
          .map((e) => PaystackTransaction.fromJson(e))
          .toList();
    }
    throw Exception('Failed to fetch transactions');
  }

  /// Get a single transaction.
  Future<PaystackTransaction> getTransaction(String id) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/payments/transactions/$id/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return PaystackTransaction.fromJson(jsonDecode(response.body));
    }
    throw Exception('Transaction not found');
  }

  // ── Refunds ─────────────────────────────────────────────

  /// Request a refund on a transaction.
  Future<PaystackRefund> requestRefund({
    required String transactionId,
    double? amount,
    String reason = 'customer_request',
    String? customerNote,
  }) async {
    final body = <String, dynamic>{
      'transaction_id': transactionId,
      'reason': reason,
    };
    if (amount != null) body['amount'] = amount;
    if (customerNote != null) body['customer_note'] = customerNote;

    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/refunds/request/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 201) {
      return PaystackRefund.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Refund request failed');
  }

  /// List the customer's refunds (paginated).
  Future<List<PaystackRefund>> listRefunds({int page = 1}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/payments/refunds/?page=$page'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['results'] as List)
          .map((e) => PaystackRefund.fromJson(e))
          .toList();
    }
    throw Exception('Failed to fetch refunds');
  }

  // ── Disputes ────────────────────────────────────────────

  /// List the customer's disputes (paginated).
  Future<List<PaystackDispute>> listDisputes({int page = 1}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/payments/disputes/?page=$page'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['results'] as List)
          .map((e) => PaystackDispute.fromJson(e))
          .toList();
    }
    throw Exception('Failed to fetch disputes');
  }

  // ── Banks ───────────────────────────────────────────────

  /// List banks supported by Paystack.
  Future<List<PaystackBank>> listBanks({String country = 'south africa'}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/payments/banks/?country=$country'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as List;
      return data.map((e) => PaystackBank.fromJson(e)).toList();
    }
    throw Exception('Failed to fetch banks');
  }

  /// Resolve a bank account number to verify the account name.
  Future<ResolvedAccount> resolveAccount({
    required String accountNumber,
    required String bankCode,
  }) async {
    final response = await http.get(
      Uri.parse(
        '$baseUrl/api/payments/banks/resolve/?account_number=$accountNumber&bank_code=$bankCode',
      ),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return ResolvedAccount.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Could not resolve account');
  }
}
```

---

## 32. Dart Vendor Service

```dart
class VendorPaymentService {
  final String baseUrl;
  final String token;

  VendorPaymentService({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  // ── Subaccount ──────────────────────────────────────────

  /// Create a Paystack subaccount for the vendor.
  Future<PaystackSubaccount> createSubaccount({
    required String businessName,
    required String settlementBank,
    required String accountNumber,
    double percentageCharge = 0,
    String? primaryContactEmail,
  }) async {
    final body = <String, dynamic>{
      'business_name': businessName,
      'settlement_bank': settlementBank,
      'account_number': accountNumber,
      'percentage_charge': percentageCharge,
    };
    if (primaryContactEmail != null) {
      body['primary_contact_email'] = primaryContactEmail;
    }

    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/subaccounts/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 201) {
      return PaystackSubaccount.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to create subaccount');
  }

  /// Get the vendor's own subaccount.
  Future<PaystackSubaccount?> getMySubaccount() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/payments/subaccounts/my-subaccount/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return PaystackSubaccount.fromJson(jsonDecode(response.body));
    }
    if (response.statusCode == 404) return null;
    throw Exception('Failed to fetch subaccount');
  }

  /// Update the vendor's subaccount.
  Future<PaystackSubaccount> updateSubaccount({
    required String id,
    String? businessName,
    String? settlementBank,
    String? accountNumber,
    double? percentageCharge,
  }) async {
    final body = <String, dynamic>{};
    if (businessName != null) body['business_name'] = businessName;
    if (settlementBank != null) body['settlement_bank'] = settlementBank;
    if (accountNumber != null) body['account_number'] = accountNumber;
    if (percentageCharge != null) body['percentage_charge'] = percentageCharge;

    final response = await http.put(
      Uri.parse('$baseUrl/api/payments/subaccounts/$id/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      return PaystackSubaccount.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Update failed');
  }
}
```

---

## 33. Dart Admin Service

```dart
class AdminPaymentService {
  final String baseUrl;
  final String token;

  AdminPaymentService({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  // ── Refund Approval ─────────────────────────────────────

  /// Approve and process a refund via Paystack.
  Future<PaystackRefund> approveRefund(String refundId, {String? adminNotes}) async {
    final body = <String, dynamic>{};
    if (adminNotes != null) body['admin_notes'] = adminNotes;

    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/refunds/$refundId/approve/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      return PaystackRefund.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Approve failed');
  }

  // ── Disputes ────────────────────────────────────────────

  /// Add evidence to a dispute.
  Future<PaystackDispute> addEvidence(
    String disputeId, {
    String? customerEmail,
    String? customerName,
    String? customerPhone,
    String? serviceDetails,
    String? deliveryAddress,
    String? description,
  }) async {
    final body = <String, dynamic>{};
    if (customerEmail != null) body['customer_email'] = customerEmail;
    if (customerName != null) body['customer_name'] = customerName;
    if (customerPhone != null) body['customer_phone'] = customerPhone;
    if (serviceDetails != null) body['service_details'] = serviceDetails;
    if (deliveryAddress != null) body['delivery_address'] = deliveryAddress;
    if (description != null) body['description'] = description;

    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/disputes/$disputeId/add-evidence/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      return PaystackDispute.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to add evidence');
  }

  /// Resolve a dispute.
  Future<PaystackDispute> resolveDispute(
    String disputeId, {
    required String resolution,
    required String message,
    double? refundAmount,
    String? uploadUrl,
  }) async {
    final body = <String, dynamic>{
      'resolution': resolution,
      'message': message,
    };
    if (refundAmount != null) body['refund_amount'] = refundAmount;
    if (uploadUrl != null) body['upload_url'] = uploadUrl;

    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/disputes/$disputeId/resolve/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      return PaystackDispute.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to resolve dispute');
  }

  /// Sync disputes from Paystack.
  Future<int> syncDisputes() async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/disputes/sync/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)['synced'];
    }
    throw Exception('Failed to sync disputes');
  }

  // ── Splits ──────────────────────────────────────────────

  /// List all transaction splits.
  Future<List<TransactionSplit>> listSplits() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/payments/splits/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['results'] as List)
          .map((e) => TransactionSplit.fromJson(e))
          .toList();
    }
    throw Exception('Failed to fetch splits');
  }

  /// Create a transaction split.
  Future<TransactionSplit> createSplit({
    required String name,
    required String splitType,
    required List<Map<String, dynamic>> subaccounts,
    String currency = 'ZAR',
    String bearerType = 'account',
    String? bearerSubaccount,
  }) async {
    final body = <String, dynamic>{
      'name': name,
      'split_type': splitType,
      'currency': currency,
      'bearer_type': bearerType,
      'subaccounts': subaccounts,
    };
    if (bearerSubaccount != null) body['bearer_subaccount'] = bearerSubaccount;

    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/splits/create_split/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 201) {
      return TransactionSplit.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to create split');
  }

  /// Add a subaccount to a split.
  Future<TransactionSplit> addSubaccountToSplit(
    String splitId, {
    required String subaccount,
    required int share,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/splits/$splitId/add-subaccount/'),
      headers: _headers,
      body: jsonEncode({'subaccount': subaccount, 'share': share}),
    );

    if (response.statusCode == 200) {
      return TransactionSplit.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to add subaccount');
  }

  /// Remove a subaccount from a split.
  Future<TransactionSplit> removeSubaccountFromSplit(
    String splitId, {
    required String subaccount,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/payments/splits/$splitId/remove-subaccount/'),
      headers: _headers,
      body: jsonEncode({'subaccount': subaccount}),
    );

    if (response.statusCode == 200) {
      return TransactionSplit.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to remove subaccount');
  }

  // ── Sync Plans/Tiers ────────────────────────────────────

  /// Sync a customer plan to Paystack.
  Future<String> syncPlanToPaystack(String slug) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/subscriptions/plans/$slug/sync-paystack/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)['paystack_plan_code'];
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to sync plan');
  }

  /// Sync a vendor tier to Paystack.
  Future<String> syncTierToPaystack(String slug) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/tiers/plans/$slug/sync-paystack/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)['paystack_plan_code'];
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Failed to sync tier');
  }
}
```

---

## 34. Dart Subscription Service (Customer)

```dart
class SubscriptionService {
  final String baseUrl;
  final String token;

  SubscriptionService({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  /// List available credit plans.
  Future<List<SubscriptionPlan>> listPlans() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/subscriptions/plans/'),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['results'] as List)
          .map((e) => SubscriptionPlan.fromJson(e))
          .toList();
    }
    throw Exception('Failed to fetch plans');
  }

  /// Get the customer's current subscription.
  /// Returns null if no subscription exists.
  Future<CustomerSubscription?> getMySubscription() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/subscriptions/subscriptions/my-subscription/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      if (data['status'] == 'none') return null;
      return CustomerSubscription.fromJson(data);
    }
    throw Exception('Failed to fetch subscription');
  }

  /// Subscribe to a credit plan. Returns subscription + Paystack payment URL.
  /// Redirect user to the authorization_url to complete payment.
  Future<Map<String, dynamic>> subscribe({
    required String planId,
    String? callbackUrl,
  }) async {
    final body = <String, dynamic>{'plan_id': planId};
    if (callbackUrl != null) body['callback_url'] = callbackUrl;

    final response = await http.post(
      Uri.parse('$baseUrl/api/subscriptions/subscriptions/subscribe/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body);
      return {
        'subscription': CustomerSubscription.fromJson(data),
        'authorization_url': data['paystack']?['authorization_url'],
        'reference': data['paystack']?['reference'],
      };
    }
    throw Exception('Failed to subscribe');
  }

  /// Cancel the current subscription.
  Future<CustomerSubscription> cancel() async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/subscriptions/subscriptions/cancel/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return CustomerSubscription.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['error'] ?? 'Cancel failed');
  }

  /// Get a Paystack link to update the subscription card.
  Future<String?> getManageCardLink() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/subscriptions/subscriptions/manage-card/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)['link'];
    }
    return null;
  }
}
```

---

## 35. Dart Tier Service (Vendor)

```dart
class TierService {
  final String baseUrl;
  final String token;

  TierService({required this.baseUrl, required this.token});

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  /// List available business tiers.
  Future<List<BusinessTier>> listTiers() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/tiers/plans/'),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return (data['results'] as List)
          .map((e) => BusinessTier.fromJson(e))
          .toList();
    }
    throw Exception('Failed to fetch tiers');
  }

  /// Get the vendor's current tier subscription.
  Future<VendorTierSubscription?> getMyTier() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/tiers/subscriptions/my-tier/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      if (data.containsKey('detail')) return null;
      return VendorTierSubscription.fromJson(data);
    }
    throw Exception('Failed to fetch tier');
  }

  /// Subscribe to a business tier. Free tiers activate immediately.
  /// Paid tiers return a Paystack authorization_url.
  Future<Map<String, dynamic>> subscribe({
    required String tierId,
    String? callbackUrl,
  }) async {
    final body = <String, dynamic>{'tier_id': tierId};
    if (callbackUrl != null) body['callback_url'] = callbackUrl;

    final response = await http.post(
      Uri.parse('$baseUrl/api/tiers/subscriptions/subscribe/'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body);
      return {
        'subscription': VendorTierSubscription.fromJson(data),
        'authorization_url': data['paystack']?['authorization_url'],
        'reference': data['paystack']?['reference'],
      };
    }
    throw Exception('Failed to subscribe');
  }

  /// Cancel the current tier subscription.
  Future<VendorTierSubscription> cancel() async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/tiers/subscriptions/cancel/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return VendorTierSubscription.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['detail'] ?? 'Cancel failed');
  }

  /// Get a Paystack link to update the tier subscription card.
  Future<String?> getManageCardLink() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/tiers/subscriptions/manage-card/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body)['link'];
    }
    return null;
  }
}
```

---

## 36. Webhook Events Reference

The Paystack webhook endpoint is:

```
POST /api/payments/webhooks/paystack/
```

> This is a **public** endpoint (no auth). Paystack signs payloads with HMAC SHA-512. The server verifies the `X-Paystack-Signature` header.

### Events Handled

| Event | Action |
|-------|--------|
| `charge.success` | Marks transaction as `success`, saves card details, sends confirmation email |
| `refund.processed` | Marks refund as `processed`, updates transaction status |
| `refund.failed` | Marks refund as `failed` |
| `subscription.create` | Links Paystack subscription code to local subscription |
| `subscription.disable` | Marks subscription as `cancelled` |
| `subscription.not_renew` | Marks subscription as `cancelled` |
| `invoice.create` | Logged |
| `invoice.payment_failed` | Marks subscription as `past_due` |
| `charge.dispute.create` | Creates local dispute record |
| `charge.dispute.remind` | Logged |
| `charge.dispute.resolve` | Updates dispute status to `resolved` |
| `transfer.success` | Logged |
| `transfer.failed` | Logged |

### Payment Flow

```
1. Client calls POST /transactions/initialize/
2. Client redirects user to authorization_url (Paystack checkout)
3. User completes payment on Paystack
4. Paystack sends charge.success webhook → server updates transaction
5. Paystack redirects user to callback_url
6. Client calls GET /transactions/verify/{reference}/ to confirm
7. Client shows success/failure to user
```

### Subscription Flow

```
1. Client calls POST /subscriptions/subscriptions/subscribe/
2. Client redirects user to paystack.authorization_url
3. User pays on Paystack → subscription starts
4. Paystack sends subscription.create webhook → server links codes
5. Paystack auto-charges on each billing cycle
6. If charge fails → invoice.payment_failed → status becomes past_due
7. To cancel: POST /subscriptions/subscriptions/cancel/
```
