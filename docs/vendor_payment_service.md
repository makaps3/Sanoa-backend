# Vendor Payment Service — Flutter

Base URL: `/api/payments/vendor/<vendor_uuid>/`

All endpoints require a valid JWT (`Authorization: Bearer <token>`).
The `vendor_uuid` is the `VendorProfile.id` (UUID) of the authenticated vendor.

---

## Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/payments/vendor/<vendor_uuid>/transactions/` | List vendor's transactions |
| `GET` | `/api/payments/vendor/<vendor_uuid>/transactions/<id>/` | Get single transaction detail |
| `GET` | `/api/payments/vendor/<vendor_uuid>/refunds/` | List refunds on vendor's transactions |
| `GET` | `/api/payments/vendor/<vendor_uuid>/disputes/` | List disputes on vendor's transactions |
| `GET` | `/api/payments/vendor/<vendor_uuid>/subaccount/` | Get vendor's subaccount — **public, no JWT** |
| `GET` | `/api/payments/subaccounts/<vendor_uuid>/subaccount/` | Get own subaccount — JWT required |
| `POST`| `/api/payments/subaccounts/` | Register vendor's bank account (create subaccount) |
| `PUT` | `/api/payments/subaccounts/<id>/` | Update bank details on existing subaccount |

---

## Query Parameters

### Transactions
| Param | Values | Example |
|-------|--------|---------|
| `status` | `pending`, `success`, `failed`, `abandoned` | `?status=success` |
| `payment_intent` | `order_payment`, `deposit`, `credit_payment` | `?payment_intent=order_payment` |

### Refunds
| Param | Values | Example |
|-------|--------|---------|
| `status` | `pending`, `approved`, `processed`, `failed` | `?status=pending` |

### Disputes
| Param | Values | Example |
|-------|--------|---------|
| `status` | `pending`, `awaiting-merchant-feedback`, `resolved` | `?status=pending` |

---

## Example Responses

### GET transactions list
```json
{
  "count": 12,
  "next": "http://api.sanoa.co.za/api/payments/vendor/<vendor_uuid>/transactions/?page=2",
  "previous": null,
  "results": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "reference": "TXN-20260517-000001",
      "payment_intent": "order_payment",
      "order": "order-uuid",
      "order_number": "ORD-20260517-001",
      "user_email": "customer@example.com",
      "amount": "500.00",
      "currency": "ZAR",
      "paystack_fees": "12.50",
      "net_amount": "487.50",
      "status": "success",
      "channel": "card",
      "card_type": "visa",
      "last4": "4081",
      "paid_at": "2026-05-17T20:00:00Z",
      "created_at": "2026-05-17T19:58:00Z"
    }
  ]
}
```

### GET refunds list
```json
{
  "count": 2,
  "results": [
    {
      "id": "refund-uuid",
      "transaction_reference": "TXN-20260517-000001",
      "amount": "500.00",
      "currency": "ZAR",
      "reason": "customer_request",
      "status": "processed",
      "processed_at": "2026-05-18T10:00:00Z",
      "created_at": "2026-05-17T21:00:00Z"
    }
  ]
}
```

---

## Flutter Service Class

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

// ── Model ─────────────────────────────────────────────────────

class PaystackSubaccount {
  final String id;
  final String subaccountCode;
  final String businessName;
  final String settlementBank;
  final String accountNumber;
  final String? bankName;
  final String? accountName;
  final double percentageCharge;
  final String? primaryContactEmail;
  final bool isActive;

  PaystackSubaccount({
    required this.id,
    required this.subaccountCode,
    required this.businessName,
    required this.settlementBank,
    required this.accountNumber,
    this.bankName,
    this.accountName,
    required this.percentageCharge,
    this.primaryContactEmail,
    required this.isActive,
  });

  factory PaystackSubaccount.fromJson(Map<String, dynamic> json) {
    return PaystackSubaccount(
      id: json['id'] as String,
      subaccountCode: json['subaccount_code'] as String,
      businessName: json['business_name'] as String,
      settlementBank: json['settlement_bank'] as String,
      accountNumber: json['account_number'] as String,
      bankName: json['bank_name'] as String?,
      accountName: json['account_name'] as String?,
      percentageCharge: double.parse(json['percentage_charge'].toString()),
      primaryContactEmail: json['primary_contact_email'] as String?,
      isActive: json['is_active'] as bool? ?? true,
    );
  }
}

// ── Service ───────────────────────────────────────────────────

class VendorPaymentService {
  static const String _base = 'https://api.sanoa.co.za';

  final String token;
  final String vendorUuid;

  VendorPaymentService({required this.token, required this.vendorUuid});

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      };

  Future<http.Response> _get(String path, {Map<String, String>? query}) {
    final uri = Uri.parse('$_base$path').replace(queryParameters: query);
    return http.get(uri, headers: _headers);
  }

  Future<http.Response> _post(String path, Map<String, dynamic> body) {
    final uri = Uri.parse('$_base$path');
    return http.post(uri, headers: _headers, body: jsonEncode(body));
  }

  Future<http.Response> _put(String path, Map<String, dynamic> body) {
    final uri = Uri.parse('$_base$path');
    return http.put(uri, headers: _headers, body: jsonEncode(body));
  }

  // ── Transactions ─────────────────────────────────────────────

  /// List all transactions for the vendor.
  /// [status]: optional filter — 'pending' | 'success' | 'failed' | 'abandoned'
  /// [paymentIntent]: optional filter — 'order_payment' | 'deposit' | 'credit_payment'
  Future<Map<String, dynamic>> getTransactions({
    String? status,
    String? paymentIntent,
    int page = 1,
  }) async {
    final query = <String, String>{'page': page.toString()};
    if (status != null) query['status'] = status;
    if (paymentIntent != null) query['payment_intent'] = paymentIntent;

    final response = await _get(
      '/api/payments/vendor/$vendorUuid/transactions/',
      query: query,
    );
    return jsonDecode(response.body);
  }

  /// Get a single transaction by its UUID.
  Future<Map<String, dynamic>> getTransaction(String transactionId) async {
    final response = await _get(
      '/api/payments/vendor/$vendorUuid/transactions/$transactionId/',
    );
    return jsonDecode(response.body);
  }

  // ── Refunds ──────────────────────────────────────────────────

  /// List refunds on the vendor's transactions.
  /// [status]: optional filter — 'pending' | 'approved' | 'processed' | 'failed'
  Future<Map<String, dynamic>> getRefunds({
    String? status,
    int page = 1,
  }) async {
    final query = <String, String>{'page': page.toString()};
    if (status != null) query['status'] = status;

    final response = await _get(
      '/api/payments/vendor/$vendorUuid/refunds/',
      query: query,
    );
    return jsonDecode(response.body);
  }

  // ── Disputes ─────────────────────────────────────────────────

  /// List disputes on the vendor's transactions.
  /// [status]: optional filter — 'pending' | 'awaiting-merchant-feedback' | 'resolved'
  Future<Map<String, dynamic>> getDisputes({
    String? status,
    int page = 1,
  }) async {
    final query = <String, String>{'page': page.toString()};
    if (status != null) query['status'] = status;

    final response = await _get(
      '/api/payments/vendor/$vendorUuid/disputes/',
      query: query,
    );
    return jsonDecode(response.body);
  }

  // ── Subaccount ───────────────────────────────────────────────

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

    final response = await _post('/api/payments/subaccounts/', body);

    if (response.statusCode == 201) {
      return PaystackSubaccount.fromJson(jsonDecode(response.body));
    }
    throw Exception(
        jsonDecode(response.body)['error'] ?? 'Failed to create subaccount');
  }

  /// Get the vendor's subaccount — public, no JWT required.
  /// Use this to display vendor bank/payout info to customers or on public pages.
  static Future<PaystackSubaccount?> getPublicSubaccount(String vendorUuid) async {
    final uri = Uri.parse('$_base/api/payments/vendor/$vendorUuid/subaccount/');
    final response = await http.get(uri, headers: {'Content-Type': 'application/json'});
    if (response.statusCode == 200) {
      return PaystackSubaccount.fromJson(jsonDecode(response.body));
    }
    if (response.statusCode == 404) return null;
    throw Exception('Failed to fetch subaccount');
  }

  /// Get the vendor's own subaccount — JWT required.
  Future<PaystackSubaccount?> getMySubaccount() async {
    final response =
        await _get('/api/payments/subaccounts/$vendorUuid/subaccount/');

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

    final response = await _put('/api/payments/subaccounts/$id/', body);

    if (response.statusCode == 200) {
      return PaystackSubaccount.fromJson(jsonDecode(response.body));
    }
    throw Exception(
        jsonDecode(response.body)['error'] ?? 'Update failed');
  }

  // ── Banks ────────────────────────────────────────────────────

  /// List supported banks (get bank codes for subaccount registration).
  Future<List<dynamic>> getBanks() async {
    final response = await _get('/api/payments/banks/');
    final data = jsonDecode(response.body);
    return data['banks'] ?? data;
  }

  /// Verify a bank account number and get the account holder's name.
  Future<Map<String, dynamic>> resolveAccount({
    required String accountNumber,
    required String bankCode,
  }) async {
    final response = await _get(
      '/api/payments/banks/resolve/',
      query: {'account_number': accountNumber, 'bank_code': bankCode},
    );
    return jsonDecode(response.body);
  }
}
```

---

## Error Responses

All endpoints follow the same error format:

| HTTP Status | Body | Meaning |
|-------------|------|---------|
| `401 Unauthorized` | `{"detail": "Authentication credentials were not provided."}` | Missing or invalid JWT |
| `403 Forbidden` | `{"error": "Access denied."}` | Token belongs to a different vendor |
| `404 Not Found` | `{"error": "Vendor not found."}` | Invalid `vendor_uuid` |
| `404 Not Found` | `{"detail": "Transaction not found."}` | Transaction doesn't belong to this vendor |

---

## Auth Pattern

```dart
// Instantiate once after login — token and vendorUuid come from the auth response.
final service = VendorPaymentService(
  token: authToken,         // JWT from login response
  vendorUuid: vendorProfileId, // VendorProfile.id (UUID)
);

// Load transactions
final transactions = await service.getTransactions(status: 'success');

// Load refunds
final refunds = await service.getRefunds();

// Check if vendor has a subaccount registered
final subaccount = await service.getMySubaccount();
if (subaccount == null) {
  // Prompt vendor to register their bank account
  final created = await service.createSubaccount(
    businessName: 'Linda\'s Fashion Store',
    settlementBank: '057',   // from getBanks()
    accountNumber: '0123456789',
    percentageCharge: 10.0,
    primaryContactEmail: 'linda@fashionstore.com',
  );
}

// Update bank details
final updated = await service.updateSubaccount(
  id: subaccount!.id,
  accountNumber: '9876543210',
);
```
