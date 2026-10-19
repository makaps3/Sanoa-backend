# Transaction Split — How It Works

Base URL: `/api/payments/`

---

## Overview

When a customer pays on Sanoa, Paystack automatically splits the money between:
- **Sanoa's main account** — platform commission
- **Vendor subaccount(s)** — vendor's revenue share

This is done through two Paystack features:
- **Subaccount** (`ACCT_xxx`) — one vendor receives funds directly
- **Split** (`SPL_xxx`) — multiple vendors receive funds automatically on one transaction

---

## The Three Models

```
PaystackSubaccount         TransactionSplit           Transaction
(one per vendor)           (split config)             (one per payment)
       │                          │                          │
       └─── TransactionSplitSubaccount              split ───┘
            (vendor + their share %)          subaccount ───┘
```

| Model | Purpose |
|-------|---------|
| `PaystackSubaccount` | Maps a vendor to their Paystack bank account (`ACCT_xxx`) |
| `TransactionSplit` | Defines how to distribute money across subaccounts (`SPL_xxx`) |
| `TransactionSplitSubaccount` | Junction — which vendor gets what share in a split |
| `Transaction.subaccount` | Links a payment to a single vendor's subaccount |
| `Transaction.split` | Links a payment to a multi-vendor split config |

---

## Who Does What

| Action | Who |
|--------|-----|
| Create a `PaystackSubaccount` (register bank account) | **Vendor** |
| Create a `TransactionSplit` (define split rules) | **Admin only** |
| Add / remove a vendor from a split | **Admin only** |
| Pass `split_code` or `subaccount_code` when paying | **Frontend** (during checkout) |
| `TransactionSplitSubaccount` entries | **Auto-created** when admin sets up a split |
| Disputes / refunds | **System (webhook)** creates; **Admin** resolves |

---

## Step-by-Step Flow

---

### Step 1 — Vendor Registers Their Bank Account

Each vendor must create a `PaystackSubaccount` before they can receive payments.
This registers their bank account on Paystack and returns an `ACCT_xxx` code.

**Who:** Vendor (JWT required)

```
POST /api/payments/subaccounts/
Authorization: Bearer <vendor_token>
Content-Type: application/json
```

**Request body:**
```json
{
  "business_name": "Linda's Fashion Store",
  "settlement_bank": "057",
  "account_number": "0123456789",
  "percentage_charge": 10.00,
  "primary_contact_email": "linda@fashionstore.com"
}
```

| Field | Description |
|-------|-------------|
| `business_name` | Vendor's business name as it appears on Paystack |
| `settlement_bank` | Paystack bank code (get from `GET /api/payments/banks/`) |
| `account_number` | Vendor's bank account number |
| `percentage_charge` | % Sanoa retains from each transaction (e.g. `10.00` = 10%) |
| `primary_contact_email` | Contact email for the subaccount |

**Response:**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "subaccount_code": "ACCT_abc123xyz",
  "business_name": "Linda's Fashion Store",
  "bank_name": "GTBank",
  "account_name": "LINDA MAKAPS",
  "percentage_charge": "10.00",
  "is_active": true
}
```

> Vendor can retrieve their subaccount at any time:
> `GET /api/payments/subaccounts/my-subaccount/`
> or `GET /api/payments/subaccounts/<vendor_uuid>/subaccount/`

---

### Step 2 — Admin Creates a Transaction Split

A `TransactionSplit` defines the rules for distributing a payment across multiple vendors.
Admin creates this once and reuses it across many transactions.

**Who:** Admin only (JWT + `is_staff` required)

```
POST /api/payments/splits/create_split/
Authorization: Bearer <admin_token>
Content-Type: application/json
```

**Request body:**
```json
{
  "name": "Multi-Vendor Cart Split",
  "split_type": "percentage",
  "currency": "ZAR",
  "bearer_type": "account",
  "subaccounts": [
    { "subaccount": "ACCT_vendor1_code", "share": 80 },
    { "subaccount": "ACCT_vendor2_code", "share": 80 }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | String | Friendly name for this split config |
| `split_type` | `percentage` \| `flat` | How shares are calculated |
| `currency` | String | `ZAR` |
| `bearer_type` | See below | Who pays Paystack's processing fee |
| `subaccounts` | Array | List of vendors and their share values |

**`split_type` options:**

| Value | Meaning |
|-------|---------|
| `percentage` | `share` is a percentage (0–100). E.g. `80` = vendor gets 80% |
| `flat` | `share` is a fixed amount in kobo/cents. E.g. `5000` = R50 |

**`bearer_type` options:**

| Value | Who pays Paystack fees |
|-------|----------------------|
| `account` | Sanoa's main account pays the fees |
| `subaccount` | A specific vendor pays the fees (set `bearer_subaccount`) |
| `all-proportional` | Fees split proportionally among all parties |
| `all` | Fees split equally among all parties |

**Response:**
```json
{
  "id": "abc12345-...",
  "name": "Multi-Vendor Cart Split",
  "paystack_split_code": "SPL_xyz789",
  "split_type": "percentage",
  "currency": "ZAR",
  "bearer_type": "account",
  "subaccounts": [
    { "subaccount": "ACCT_vendor1_code", "share": 80 },
    { "subaccount": "ACCT_vendor2_code", "share": 80 }
  ],
  "is_active": true
}
```

> Save the `paystack_split_code` (`SPL_xxx`) — this is passed during checkout.

---

### Step 3 — Admin Manages Vendors in a Split

Admin can add or remove vendors from an existing split at any time.

**Add a vendor:**
```
POST /api/payments/splits/<split_id>/add-subaccount/
Authorization: Bearer <admin_token>
Content-Type: application/json
```
```json
{
  "subaccount": "ACCT_newvendor_code",
  "share": 75
}
```

**Remove a vendor:**
```
POST /api/payments/splits/<split_id>/remove-subaccount/
Authorization: Bearer <admin_token>
Content-Type: application/json
```
```json
{
  "subaccount": "ACCT_vendor_to_remove"
}
```

---

### Step 4 — Customer Pays (Split Applied Automatically)

During checkout, the frontend initializes a transaction and passes either a
`split_code` (multi-vendor) or `subaccount_code` (single vendor).
Paystack distributes the money automatically — no manual action needed after this.

**Who:** Customer (JWT required)

```
POST /api/payments/transactions/initialize/
Authorization: Bearer <customer_token>
Content-Type: application/json
```

#### Single-vendor order (use `subaccount_code`)

```json
{
  "amount": 500.00,
  "payment_intent": "order_payment",
  "order_id": "<order-uuid>",
  "subaccount_code": "ACCT_vendor1_code",
  "callback_url": "https://yourapp.com/payment/callback"
}
```

#### Multi-vendor cart (use `split_code`)

```json
{
  "amount": 1500.00,
  "payment_intent": "order_payment",
  "order_id": "<order-uuid>",
  "split_code": "SPL_xyz789",
  "callback_url": "https://yourapp.com/payment/callback"
}
```

**Response:**
```json
{
  "authorization_url": "https://checkout.paystack.com/abc123",
  "access_code": "abc123",
  "reference": "TXN-20260517-000001",
  "transaction_id": "<transaction-uuid>"
}
```

> Redirect the customer to `authorization_url` to complete payment.
> After payment, Paystack calls the webhook and updates the transaction status automatically.

---

### Step 5 — Paystack Webhook Confirms Payment

Paystack sends a `charge.success` event to:
```
POST /api/payments/webhook/
```
This is public — no auth required (verified by Paystack signature).

The webhook handler automatically:
1. Updates `Transaction.status` → `success`
2. Records card/channel details
3. Sends payment confirmation email to the customer
4. If `payment_intent` is `credit_payment`, applies repayment to the credit account

> No manual action required. Paystack has already split the money on their end.

---

## Two Routing Patterns

| Pattern | When to use | Field |
|---------|------------|-------|
| `subaccount_code` | Single-vendor order — all funds go to one vendor | `"subaccount_code": "ACCT_xxx"` |
| `split_code` | Multi-vendor cart — auto-distribute among vendors | `"split_code": "SPL_xxx"` |

---

## Money Flow Example

**Customer pays R1,000 on a multi-vendor cart. Split config: 80% to each vendor, Sanoa bears fees.**

```
Customer pays R1,000
        │
        ▼
  Paystack processes
        │
        ├─── Vendor A gets R400 (80% of their R500 share)
        ├─── Vendor B gets R400 (80% of their R500 share)
        └─── Sanoa keeps R200  (20% platform commission) + Paystack fees deducted from Sanoa's share
```

> The exact amounts depend on the `percentage_charge` set on each vendor's subaccount
> and the `share` values in the split config.

---

## Verify a Payment After Redirect

After the customer completes payment on Paystack's hosted page, verify the transaction:

```
GET /api/payments/transactions/verify/<reference>/
Authorization: Bearer <token>
```

**Response includes:**
```json
{
  "id": "<transaction-uuid>",
  "reference": "TXN-20260517-000001",
  "status": "success",
  "amount": "1500.00",
  "channel": "card",
  "paid_at": "2026-05-17T20:00:00Z",
  "split": { "paystack_split_code": "SPL_xyz789", ... },
  "subaccount": null
}
```

---

## Payment Intent Options

| `payment_intent` | Use case | Split/Subaccount applies? |
|-----------------|----------|--------------------------|
| `order_payment` | Customer paying for an order | Yes |
| `deposit` | General deposit | Yes |
| `credit_payment` | Credit repayment | Yes |
| `subscription_payment` | Customer subscription plan | No |
| `tier_payment` | Vendor tier subscription | No |

> Split and subaccount routing only applies to `order_payment`, `deposit`, and `credit_payment`.
> Subscription payments go directly to Sanoa's main account.

---

## Quick Reference — All Split Endpoints

### Admin Endpoints (require `is_staff`)

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/payments/splits/` | List all splits |
| `GET` | `/api/payments/splits/<id>/` | Get split detail |
| `POST` | `/api/payments/splits/create_split/` | Create a new split on Paystack |
| `POST` | `/api/payments/splits/<id>/add-subaccount/` | Add a vendor to a split |
| `POST` | `/api/payments/splits/<id>/remove-subaccount/` | Remove a vendor from a split |

### Vendor Endpoints (require vendor JWT)

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/payments/subaccounts/` | Register bank account (create subaccount) |
| `GET` | `/api/payments/subaccounts/my-subaccount/` | Get own subaccount |
| `GET` | `/api/payments/subaccounts/<vendor_uuid>/subaccount/` | Get subaccount by vendor UUID |
| `PUT/PATCH` | `/api/payments/subaccounts/<id>/` | Update bank details |

### Customer / General Endpoints (require JWT)

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/payments/transactions/initialize/` | Initialize payment (pass split or subaccount) |
| `GET` | `/api/payments/transactions/verify/<reference>/` | Verify payment after redirect |
| `GET` | `/api/payments/transactions/` | List own transactions |
| `POST` | `/api/payments/refunds/request/` | Request a refund |
| `GET` | `/api/payments/banks/` | List supported banks |
| `GET` | `/api/payments/resolve-account/?account_number=&bank_code=` | Verify bank account name |

### Public Endpoints (no auth)

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/payments/webhook/` | Paystack webhook receiver |
