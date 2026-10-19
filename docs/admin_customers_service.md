# Admin Customer Management — Dart Service Reference

Base URL: `POST /api/platform-admin/customers/`  
All requests require `Authorization: Bearer <admin_access_token>`.

---

## Dart Models

```dart
class AdminCustomerProfile {
  final int id;
  final String email;
  final String firstName;
  final String lastName;
  final String phoneNumber;
  final bool isVerified;
  final bool isSuspended;
  final DateTime? suspendedAt;
  final String suspensionReason;
  final String? avatar;
  final String? gender;
  final String bio;
  final double? latitude;
  final double? longitude;
  final String preferredLanguage;
  final bool newsletterSubscription;
  final bool smsNotifications;
  final bool emailNotifications;
  final int loyaltyPoints;
  final DateTime memberSince;
  final DateTime dateJoined;
  final DateTime createdAt;
  final DateTime updatedAt;

  const AdminCustomerProfile({
    required this.id,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.phoneNumber,
    required this.isVerified,
    required this.isSuspended,
    this.suspendedAt,
    required this.suspensionReason,
    this.avatar,
    this.gender,
    required this.bio,
    this.latitude,
    this.longitude,
    required this.preferredLanguage,
    required this.newsletterSubscription,
    required this.smsNotifications,
    required this.emailNotifications,
    required this.loyaltyPoints,
    required this.memberSince,
    required this.dateJoined,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AdminCustomerProfile.fromJson(Map<String, dynamic> json) {
    return AdminCustomerProfile(
      id: json['id'] as int,
      email: json['email'] as String,
      firstName: json['first_name'] as String? ?? '',
      lastName: json['last_name'] as String? ?? '',
      phoneNumber: json['phone_number'] as String? ?? '',
      isVerified: json['is_verified'] as bool,
      isSuspended: json['is_suspended'] as bool,
      suspendedAt: json['suspended_at'] != null
          ? DateTime.parse(json['suspended_at'] as String)
          : null,
      suspensionReason: json['suspension_reason'] as String? ?? '',
      avatar: json['avatar'] as String?,
      gender: json['gender'] as String?,
      bio: json['bio'] as String? ?? '',
      latitude: json['latitude'] != null
          ? double.parse(json['latitude'].toString())
          : null,
      longitude: json['longitude'] != null
          ? double.parse(json['longitude'].toString())
          : null,
      preferredLanguage: json['preferred_language'] as String? ?? 'en',
      newsletterSubscription: json['newsletter_subscription'] as bool,
      smsNotifications: json['sms_notifications'] as bool,
      emailNotifications: json['email_notifications'] as bool,
      loyaltyPoints: json['loyalty_points'] as int,
      memberSince: DateTime.parse(json['member_since'] as String),
      dateJoined: DateTime.parse(json['date_joined'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  String get fullName => '$firstName $lastName'.trim();
}


class AdminCustomerUpdateRequest {
  final String? firstName;
  final String? lastName;
  final String? phoneNumber;
  final String? dateOfBirth;   // 'YYYY-MM-DD'
  final String? gender;        // 'M' | 'F' | 'O' | 'N'
  final String? bio;
  final double? latitude;
  final double? longitude;
  final String? preferredLanguage;
  final bool? newsletterSubscription;
  final bool? smsNotifications;
  final bool? emailNotifications;
  final int? loyaltyPoints;

  const AdminCustomerUpdateRequest({
    this.firstName,
    this.lastName,
    this.phoneNumber,
    this.dateOfBirth,
    this.gender,
    this.bio,
    this.latitude,
    this.longitude,
    this.preferredLanguage,
    this.newsletterSubscription,
    this.smsNotifications,
    this.emailNotifications,
    this.loyaltyPoints,
  });

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{};
    if (firstName != null) map['first_name'] = firstName;
    if (lastName != null) map['last_name'] = lastName;
    if (phoneNumber != null) map['phone_number'] = phoneNumber;
    if (dateOfBirth != null) map['date_of_birth'] = dateOfBirth;
    if (gender != null) map['gender'] = gender;
    if (bio != null) map['bio'] = bio;
    if (latitude != null) map['latitude'] = latitude;
    if (longitude != null) map['longitude'] = longitude;
    if (preferredLanguage != null) map['preferred_language'] = preferredLanguage;
    if (newsletterSubscription != null) map['newsletter_subscription'] = newsletterSubscription;
    if (smsNotifications != null) map['sms_notifications'] = smsNotifications;
    if (emailNotifications != null) map['email_notifications'] = emailNotifications;
    if (loyaltyPoints != null) map['loyalty_points'] = loyaltyPoints;
    return map;
  }
}


class AdminLoyaltyAdjustResult {
  final int loyaltyPoints;
  final int adjustedBy;

  const AdminLoyaltyAdjustResult({
    required this.loyaltyPoints,
    required this.adjustedBy,
  });

  factory AdminLoyaltyAdjustResult.fromJson(Map<String, dynamic> json) {
    return AdminLoyaltyAdjustResult(
      loyaltyPoints: json['loyalty_points'] as int,
      adjustedBy: json['adjusted_by'] as int,
    );
  }
}
```

---

## Service Class

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class AdminCustomersService {
  final String baseUrl;
  final String Function() getToken;

  const AdminCustomersService({
    required this.baseUrl,
    required this.getToken,
  });

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ${getToken()}',
      };

  Uri _uri(String path, [Map<String, String>? params]) {
    final uri = Uri.parse('$baseUrl/api/platform-admin/customers$path');
    return params != null ? uri.replace(queryParameters: params) : uri;
  }

  // ── List all customers ───────────────────────────────────────────────────────

  /// [search]       Filter by email, first name, last name, or phone.
  /// [isSuspended]  Pass true/false to filter by suspension status.
  /// [isVerified]   Pass true/false to filter by verification status.
  Future<List<AdminCustomerProfile>> listCustomers({
    String? search,
    bool? isSuspended,
    bool? isVerified,
  }) async {
    final params = <String, String>{};
    if (search != null && search.isNotEmpty) params['search'] = search;
    if (isSuspended != null) params['is_suspended'] = isSuspended.toString();
    if (isVerified != null) params['is_verified'] = isVerified.toString();

    final response = await http.get(_uri('/', params), headers: _headers);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data
          .map((e) => AdminCustomerProfile.fromJson(e as Map<String, dynamic>))
          .toList();
    }
    throw Exception('Failed to fetch customers: ${response.body}');
  }

  // ── Get single customer ──────────────────────────────────────────────────────

  Future<AdminCustomerProfile> getCustomer(int customerId) async {
    final response = await http.get(_uri('/$customerId/'), headers: _headers);

    if (response.statusCode == 200) {
      return AdminCustomerProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to fetch customer: ${response.body}');
  }

  // ── Update customer ──────────────────────────────────────────────────────────

  Future<AdminCustomerProfile> updateCustomer(
    int customerId,
    AdminCustomerUpdateRequest data,
  ) async {
    final response = await http.patch(
      _uri('/$customerId/'),
      headers: _headers,
      body: jsonEncode(data.toJson()),
    );

    if (response.statusCode == 200) {
      return AdminCustomerProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to update customer: ${response.body}');
  }

  // ── Delete customer ──────────────────────────────────────────────────────────

  Future<void> deleteCustomer(int customerId) async {
    final response = await http.delete(_uri('/$customerId/'), headers: _headers);

    if (response.statusCode != 204) {
      throw Exception('Failed to delete customer: ${response.body}');
    }
  }

  // ── Suspend customer ─────────────────────────────────────────────────────────

  Future<AdminCustomerProfile> suspendCustomer(
    int customerId, {
    String reason = '',
  }) async {
    final response = await http.post(
      _uri('/$customerId/suspend/'),
      headers: _headers,
      body: jsonEncode({'reason': reason}),
    );

    if (response.statusCode == 200) {
      return AdminCustomerProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to suspend customer: ${response.body}');
  }

  // ── Unsuspend customer ───────────────────────────────────────────────────────

  Future<AdminCustomerProfile> unsuspendCustomer(int customerId) async {
    final response = await http.post(
      _uri('/$customerId/unsuspend/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return AdminCustomerProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to unsuspend customer: ${response.body}');
  }

  // ── Verify customer ──────────────────────────────────────────────────────────

  Future<AdminCustomerProfile> verifyCustomer(int customerId) async {
    final response = await http.post(
      _uri('/$customerId/verify/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return AdminCustomerProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to verify customer: ${response.body}');
  }

  // ── Unverify customer ────────────────────────────────────────────────────────

  Future<AdminCustomerProfile> unverifyCustomer(int customerId) async {
    final response = await http.post(
      _uri('/$customerId/unverify/'),
      headers: _headers,
    );

    if (response.statusCode == 200) {
      return AdminCustomerProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to unverify customer: ${response.body}');
  }

  // ── Adjust loyalty points ────────────────────────────────────────────────────

  /// Pass a positive [points] to add, negative to deduct.
  /// Points can never go below 0.
  Future<AdminLoyaltyAdjustResult> adjustLoyaltyPoints(
    int customerId, {
    required int points,
  }) async {
    final response = await http.post(
      _uri('/$customerId/adjust-loyalty/'),
      headers: _headers,
      body: jsonEncode({'points': points}),
    );

    if (response.statusCode == 200) {
      return AdminLoyaltyAdjustResult.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to adjust loyalty points: ${response.body}');
  }
}
```

---

## Endpoint Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/platform-admin/customers/` | List all customer profiles |
| `GET` | `/api/platform-admin/customers/{id}/` | Get one customer |
| `PATCH` | `/api/platform-admin/customers/{id}/` | Update profile/user fields |
| `DELETE` | `/api/platform-admin/customers/{id}/` | Delete customer account |
| `POST` | `/api/platform-admin/customers/{id}/suspend/` | Suspend customer |
| `POST` | `/api/platform-admin/customers/{id}/unsuspend/` | Unsuspend customer |
| `POST` | `/api/platform-admin/customers/{id}/verify/` | Mark as verified |
| `POST` | `/api/platform-admin/customers/{id}/unverify/` | Mark as unverified |
| `POST` | `/api/platform-admin/customers/{id}/adjust-loyalty/` | Add or deduct loyalty points |

---

## Query Parameters — `GET /customers/`

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `search` | string | `?search=linda` | Email, first name, last name, or phone |
| `is_suspended` | bool | `?is_suspended=true` | Filter suspended customers |
| `is_verified` | bool | `?is_verified=false` | Filter unverified customers |

---

## Request Bodies

### `PATCH /customers/{id}/`
Send only the fields to update — all fields are optional.

```json
{
  "first_name": "Linda",
  "last_name": "Makaps",
  "phone_number": "+27811234567",
  "date_of_birth": "1995-03-15",
  "gender": "F",
  "bio": "Loves fresh produce.",
  "latitude": -26.2041,
  "longitude": 28.0473,
  "preferred_language": "en",
  "newsletter_subscription": true,
  "sms_notifications": false,
  "email_notifications": true,
  "loyalty_points": 500
}
```

### `POST /customers/{id}/suspend/`
```json
{ "reason": "Overdue credit payments." }
```

### `POST /customers/{id}/adjust-loyalty/`
```json
{ "points": 100 }
```
```json
{ "points": -50 }
```

---

## Response Bodies

### `AdminCustomerProfile` (returned by GET, PATCH, suspend, unsuspend, verify, unverify)

```json
{
  "id": 12,
  "email": "customer@example.com",
  "first_name": "Linda",
  "last_name": "Makaps",
  "phone_number": "+27811234567",
  "is_verified": true,
  "is_suspended": false,
  "suspended_at": null,
  "suspension_reason": "",
  "avatar": "http://example.com/media/avatars/customers/photo.jpg",
  "gender": "F",
  "bio": "Loves fresh produce.",
  "latitude": "-26.204100",
  "longitude": "28.047300",
  "preferred_language": "en",
  "newsletter_subscription": true,
  "sms_notifications": true,
  "email_notifications": true,
  "loyalty_points": 350,
  "member_since": "2025-01-10T08:00:00Z",
  "date_joined": "2025-01-10T08:00:00Z",
  "created_at": "2025-01-10T08:00:00Z",
  "updated_at": "2026-05-22T21:00:00Z"
}
```

### `AdminLoyaltyAdjustResult` (returned by adjust-loyalty)

```json
{
  "loyalty_points": 450,
  "adjusted_by": 100
}
```

### `DELETE` — returns `204 No Content` with empty body.

---

## Error Responses

| Status | Body | Cause |
|--------|------|-------|
| `400` | `{"detail": "Customer is already suspended."}` | Suspend already-suspended customer |
| `400` | `{"detail": "Customer is not suspended."}` | Unsuspend non-suspended customer |
| `400` | `{"detail": "Customer is already verified."}` | Verify already-verified customer |
| `400` | `{"detail": "A valid integer value for points is required."}` | Missing/invalid points value |
| `403` | `{"detail": "Forbidden."}` | Caller is not a platform admin |
| `404` | `{"detail": "No CustomerProfile matches the given query."}` | Customer ID not found |
