# Sanoa Platform - Authentication & Business API Documentation

**Dart / Flutter Complete Reference**
**Currency: ZAR (South African Rand)**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Dart Models](#2-dart-models)
3. [Dart / Flutter Setup](#3-dart--flutter-setup)
4. [Customer Registration](#4-customer-registration)
5. [Vendor Registration (Account Only)](#5-vendor-registration-account-only)
6. [OTP Verification](#6-otp-verification)
7. [Fetch All Categories](#7-fetch-all-categories)
8. [Create Individual Vendor Profile](#8-create-individual-vendor-profile)
9. [Create Business Vendor Profile](#9-create-business-vendor-profile)
10. [Login (Obtain JWT Tokens)](#10-login-obtain-jwt-tokens)
11. [Token Refresh](#11-token-refresh)
12. [Token Verify](#12-token-verify)
13. [Get Current User Profile](#13-get-current-user-profile)
14. [Update User Profile](#14-update-user-profile)
15. [Update Vendor Profiles](#15-update-vendor-profiles)
16. [Addresses](#16-addresses)
17. [Complete AuthService Class](#17-complete-authservice-class)
18. [Error Handling](#18-error-handling)
19. [Best Practices](#19-best-practices)

---

## 1. Overview

Sanoa uses **JWT (JSON Web Token)** authentication via Django REST Framework SimpleJWT. All authenticated requests must include the access token in the `Authorization` header as: `Bearer <token>`.

- **Base URL:** `https://your-domain.com` (replace with your server)
- **All monetary values are in ZAR (South African Rand)**

### App Structure

| App | Responsibility |
|-----|---------------|
| `accounts` | User registration, login, customer profiles, API tokens |
| `business` | Vendor profiles (individual & business), addresses, vetting, documents, followers, store discovery |
| `otp` | OTP code generation, verification, and resend for account verification |

### User Types

| Type | Description |
|------|-------------|
| `customer` | App buyers/users. CustomerProfile auto-created on registration. |
| `vendor` (individual) | Informal traders: tuck shops, street vendors, freelancers. Create IndividualVendorProfile after registration. |
| `vendor` (business) | CIPC-registered businesses. Create BusinessVendorProfile after registration. |
| `admin` | Platform administrators. |

### Authentication Flow

1. **Register** account (customer or vendor) → receive JWT tokens immediately
2. **Verify account** via OTP sent to email (6-digit code, valid 10 minutes)
3. **For vendors:** create vendor profile (individual OR business) → triggers vetting
4. Use **access token** for authenticated requests (valid **60 minutes**)
5. **Refresh** token when expired (valid **7 days**, rotates on use)

### All Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/accounts/register/` | Register (customer or vendor) | No |
| `POST` | `/api/otp/send/` | Send OTP to email | No |
| `POST` | `/api/otp/verify/` | Verify OTP code | No |
| `POST` | `/api/otp/resend/` | Resend OTP (rate-limited) | No |
| `POST` | `/api/auth/token/` | Login - obtain JWT tokens | No |
| `POST` | `/api/auth/token/refresh/` | Refresh access token | No |
| `POST` | `/api/auth/token/verify/` | Verify token validity | No |
| `GET` | `/api/accounts/me/` | Get current user profile | Yes |
| `PATCH` | `/api/accounts/me/` | Update user profile | Yes |
| `POST` | `/api/business/profiles/vendor/individual/` | Create individual vendor profile | Yes |
| `POST` | `/api/business/profiles/vendor/business/` | Create business vendor profile | Yes |
| `GET` | `/api/business/profiles/vendor/individual/{id}/` | Get individual vendor profile | Yes |
| `GET` | `/api/business/profiles/vendor/business/{id}/` | Get business vendor profile | Yes |
| `PATCH` | `/api/business/profiles/vendor/individual/{id}/` | Update individual vendor profile | Yes |
| `PATCH` | `/api/business/profiles/vendor/business/{id}/` | Update business vendor profile | Yes |
| `GET` | `/api/business/addresses/` | List user addresses | Yes |
| `POST` | `/api/business/addresses/` | Create address | Yes |
| `PATCH` | `/api/business/addresses/{id}/` | Update address | Yes |
| `DELETE` | `/api/business/addresses/{id}/` | Delete address | Yes |

---

## 2. Dart Models

### 2.1 AuthTokens

```dart
class AuthTokens {
  final String access;
  final String refresh;

  AuthTokens({required this.access, required this.refresh});

  factory AuthTokens.fromJson(Map<String, dynamic> json) {
    return AuthTokens(
      access: json['access'] as String,
      refresh: json['refresh'] as String,
    );
  }

  Map<String, dynamic> toJson() => {'access': access, 'refresh': refresh};
}
```

### 2.2 User

```dart
class User {
  final String id;
  final String email;
  final String? username;
  final String firstName;
  final String lastName;
  final String? phoneNumber;
  final String userType;
  final bool isVerified;
  final String? dateOfBirth;
  final bool isActive;
  final String dateJoined;
  final String createdAt;
  final String updatedAt;
  final CustomerProfile? customerProfile;
  final IndividualVendorProfile? individualVendorProfile;
  final BusinessVendorProfile? businessVendorProfile;
  final List<Address>? addresses;

  User({
    required this.id,
    required this.email,
    this.username,
    required this.firstName,
    required this.lastName,
    this.phoneNumber,
    required this.userType,
    required this.isVerified,
    this.dateOfBirth,
    required this.isActive,
    required this.dateJoined,
    required this.createdAt,
    required this.updatedAt,
    this.customerProfile,
    this.individualVendorProfile,
    this.businessVendorProfile,
    this.addresses,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'].toString(),
      email: json['email'] as String,
      username: json['username'] as String?,
      firstName: json['first_name'] as String,
      lastName: json['last_name'] as String,
      phoneNumber: json['phone_number'] as String?,
      userType: json['user_type'] as String,
      isVerified: json['is_verified'] as bool,
      dateOfBirth: json['date_of_birth'] as String?,
      isActive: json['is_active'] as bool,
      dateJoined: json['date_joined'] as String,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
      customerProfile: json['customer_profile'] != null
          ? CustomerProfile.fromJson(json['customer_profile'])
          : null,
      individualVendorProfile: json['individual_vendor_profile'] != null
          ? IndividualVendorProfile.fromJson(json['individual_vendor_profile'])
          : null,
      businessVendorProfile: json['business_vendor_profile'] != null
          ? BusinessVendorProfile.fromJson(json['business_vendor_profile'])
          : null,
      addresses: json['addresses'] != null
          ? (json['addresses'] as List).map((a) => Address.fromJson(a)).toList()
          : null,
    );
  }
}
```

### 2.3 RegisterResponse

```dart
class RegisterResponse {
  final User user;
  final AuthTokens tokens;

  RegisterResponse({required this.user, required this.tokens});

  factory RegisterResponse.fromJson(Map<String, dynamic> json) {
    return RegisterResponse(
      user: User.fromJson(json['user']),
      tokens: AuthTokens.fromJson(json['tokens']),
    );
  }
}
```

### 2.4 CustomerProfile

```dart
class CustomerProfile {
  final String id;
  final String userEmail;
  final String? avatar;
  final String? gender;
  final String? bio;
  final List<int>? interestCategories;
  final double? latitude;
  final double? longitude;
  final String preferredLanguage;
  final bool newsletterSubscription;
  final bool smsNotifications;
  final bool emailNotifications;
  final int loyaltyPoints;
  final String memberSince;

  CustomerProfile({
    required this.id,
    required this.userEmail,
    this.avatar,
    this.gender,
    this.bio,
    this.interestCategories,
    this.latitude,
    this.longitude,
    required this.preferredLanguage,
    required this.newsletterSubscription,
    required this.smsNotifications,
    required this.emailNotifications,
    required this.loyaltyPoints,
    required this.memberSince,
  });

  factory CustomerProfile.fromJson(Map<String, dynamic> json) {
    return CustomerProfile(
      id: json['id'].toString(),
      userEmail: json['user_email'] as String,
      avatar: json['avatar'] as String?,
      gender: json['gender'] as String?,
      bio: json['bio'] as String?,
      interestCategories: json['interest_categories'] != null
          ? List<int>.from(json['interest_categories'])
          : null,
      latitude: json['latitude'] != null
          ? double.parse(json['latitude'].toString())
          : null,
      longitude: json['longitude'] != null
          ? double.parse(json['longitude'].toString())
          : null,
      preferredLanguage: json['preferred_language'] as String,
      newsletterSubscription: json['newsletter_subscription'] as bool,
      smsNotifications: json['sms_notifications'] as bool,
      emailNotifications: json['email_notifications'] as bool,
      loyaltyPoints: json['loyalty_points'] as int,
      memberSince: json['member_since'] as String,
    );
  }
}
```

### 2.5 CategorySummary

```dart
class CategorySummary {
  final int id;
  final String name;
  final String slug;

  CategorySummary({required this.id, required this.name, required this.slug});

  factory CategorySummary.fromJson(Map<String, dynamic> json) {
    return CategorySummary(
      id: json['id'] as int,
      name: json['name'] as String,
      slug: json['slug'] as String,
    );
  }
}
```

### 2.6 IndividualVendorProfile

```dart
class IndividualVendorProfile {
  final String id;
  final String userEmail;
  final String? ownerName;
  final String storeName;
  final String? storeDescription;
  final String? storeLogo;
  final List<CategorySummary> categories;
  final String? qrCode;
  final String? qrCodeIdentifier;
  final String idNumber;
  final String? idDocument;
  final String? proofOfAddress;
  final String? selfieWithId;
  final String? tradingAddress;
  final String? tradingCity;
  final String? tradingProvince;
  final String? tradingPostalCode;
  final String? bankName;
  final String? bankAccountNumber;
  final String? bankBranchCode;
  final String? bankAccountHolder;
  final String verificationStatus;
  final String? rejectionReason;
  final String? verifiedAt;
  final bool isVerified;
  final String totalSales;
  final int totalOrders;
  final String averageRating;
  final int totalReviews;
  final String commissionRate;
  final bool storeActive;
  final bool acceptsReturns;
  final int returnWindowDays;
  final String createdAt;
  final String updatedAt;

  IndividualVendorProfile({
    required this.id,
    required this.userEmail,
    this.ownerName,
    required this.storeName,
    this.storeDescription,
    this.storeLogo,
    required this.categories,
    this.qrCode,
    this.qrCodeIdentifier,
    required this.idNumber,
    this.idDocument,
    this.proofOfAddress,
    this.selfieWithId,
    this.tradingAddress,
    this.tradingCity,
    this.tradingProvince,
    this.tradingPostalCode,
    this.bankName,
    this.bankAccountNumber,
    this.bankBranchCode,
    this.bankAccountHolder,
    required this.verificationStatus,
    this.rejectionReason,
    this.verifiedAt,
    required this.isVerified,
    required this.totalSales,
    required this.totalOrders,
    required this.averageRating,
    required this.totalReviews,
    required this.commissionRate,
    required this.storeActive,
    required this.acceptsReturns,
    required this.returnWindowDays,
    required this.createdAt,
    required this.updatedAt,
  });

  factory IndividualVendorProfile.fromJson(Map<String, dynamic> json) {
    return IndividualVendorProfile(
      id: json['id'].toString(),
      userEmail: json['user_email'] as String,
      ownerName: json['owner_name'] as String?,
      storeName: json['store_name'] as String,
      storeDescription: json['store_description'] as String?,
      storeLogo: json['store_logo'] as String?,
      categories: (json['categories'] as List<dynamic>?)
          ?.map((e) => CategorySummary.fromJson(e))
          .toList() ?? [],
      qrCode: json['qr_code'] as String?,
      qrCodeIdentifier: json['qr_code_identifier'] as String?,
      idNumber: json['id_number'] as String,
      idDocument: json['id_document'] as String?,
      proofOfAddress: json['proof_of_address'] as String?,
      selfieWithId: json['selfie_with_id'] as String?,
      tradingAddress: json['trading_address'] as String?,
      tradingCity: json['trading_city'] as String?,
      tradingProvince: json['trading_province'] as String?,
      tradingPostalCode: json['trading_postal_code'] as String?,
      bankName: json['bank_name'] as String?,
      bankAccountNumber: json['bank_account_number'] as String?,
      bankBranchCode: json['bank_branch_code'] as String?,
      bankAccountHolder: json['bank_account_holder'] as String?,
      verificationStatus: json['verification_status'] as String,
      rejectionReason: json['rejection_reason'] as String?,
      verifiedAt: json['verified_at'] as String?,
      isVerified: json['is_verified'] as bool,
      totalSales: json['total_sales'] as String,
      totalOrders: json['total_orders'] as int,
      averageRating: json['average_rating'] as String,
      totalReviews: json['total_reviews'] as int,
      commissionRate: json['commission_rate'] as String,
      storeActive: json['store_active'] as bool,
      acceptsReturns: json['accepts_returns'] as bool,
      returnWindowDays: json['return_window_days'] as int,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }
}
```

### 2.6 BusinessVendorProfile

```dart
class BusinessVendorProfile {
  final String id;
  final String userEmail;
  final String businessName;
  final String? businessTradingName;
  final String businessType;
  final String? businessDescription;
  final String? businessLogo;
  final String? businessWebsite;
  final List<CategorySummary> categories;
  final String? qrCode;
  final String? qrCodeIdentifier;
  final String cipcRegistrationNumber;
  final String? cipcDocument;
  final String? taxNumber;
  final String? taxClearanceCertificate;
  final String? vatNumber;
  final String? beeCertificate;
  final String ownerFullName;
  final String ownerIdNumber;
  final String? ownerIdDocument;
  final String? ownerProofOfAddress;
  final String businessStreetAddress;
  final String businessCity;
  final String businessProvince;
  final String businessPostalCode;
  final String businessCountry;
  final String bankName;
  final String bankAccountNumber;
  final String bankBranchCode;
  final String bankAccountHolder;
  final String verificationStatus;
  final bool ownerVettingPassed;
  final bool businessVettingPassed;
  final String? rejectionReason;
  final String? verifiedAt;
  final bool isVerified;
  final bool isFullyVetted;
  final String totalSales;
  final int totalOrders;
  final String averageRating;
  final int totalReviews;
  final String commissionRate;
  final bool storeActive;
  final bool acceptsReturns;
  final int returnWindowDays;
  final String createdAt;
  final String updatedAt;

  BusinessVendorProfile({
    required this.id,
    required this.userEmail,
    required this.businessName,
    this.businessTradingName,
    required this.businessType,
    this.businessDescription,
    this.businessLogo,
    this.businessWebsite,
    required this.categories,
    this.qrCode,
    this.qrCodeIdentifier,
    required this.cipcRegistrationNumber,
    this.cipcDocument,
    this.taxNumber,
    this.taxClearanceCertificate,
    this.vatNumber,
    this.beeCertificate,
    required this.ownerFullName,
    required this.ownerIdNumber,
    this.ownerIdDocument,
    this.ownerProofOfAddress,
    required this.businessStreetAddress,
    required this.businessCity,
    required this.businessProvince,
    required this.businessPostalCode,
    required this.businessCountry,
    required this.bankName,
    required this.bankAccountNumber,
    required this.bankBranchCode,
    required this.bankAccountHolder,
    required this.verificationStatus,
    required this.ownerVettingPassed,
    required this.businessVettingPassed,
    this.rejectionReason,
    this.verifiedAt,
    required this.isVerified,
    required this.isFullyVetted,
    required this.totalSales,
    required this.totalOrders,
    required this.averageRating,
    required this.totalReviews,
    required this.commissionRate,
    required this.storeActive,
    required this.acceptsReturns,
    required this.returnWindowDays,
    required this.createdAt,
    required this.updatedAt,
  });

  factory BusinessVendorProfile.fromJson(Map<String, dynamic> json) {
    return BusinessVendorProfile(
      id: json['id'].toString(),
      userEmail: json['user_email'] as String,
      businessName: json['business_name'] as String,
      businessTradingName: json['business_trading_name'] as String?,
      businessType: json['business_type'] as String,
      businessDescription: json['business_description'] as String?,
      businessLogo: json['business_logo'] as String?,
      businessWebsite: json['business_website'] as String?,
      categories: (json['categories'] as List<dynamic>?)
          ?.map((e) => CategorySummary.fromJson(e))
          .toList() ?? [],
      qrCode: json['qr_code'] as String?,
      qrCodeIdentifier: json['qr_code_identifier'] as String?,
      cipcRegistrationNumber: json['cipc_registration_number'] as String,
      cipcDocument: json['cipc_document'] as String?,
      taxNumber: json['tax_number'] as String?,
      taxClearanceCertificate: json['tax_clearance_certificate'] as String?,
      vatNumber: json['vat_number'] as String?,
      beeCertificate: json['bee_certificate'] as String?,
      ownerFullName: json['owner_full_name'] as String,
      ownerIdNumber: json['owner_id_number'] as String,
      ownerIdDocument: json['owner_id_document'] as String?,
      ownerProofOfAddress: json['owner_proof_of_address'] as String?,
      businessStreetAddress: json['business_street_address'] as String,
      businessCity: json['business_city'] as String,
      businessProvince: json['business_province'] as String,
      businessPostalCode: json['business_postal_code'] as String,
      businessCountry: json['business_country'] as String,
      bankName: json['bank_name'] as String,
      bankAccountNumber: json['bank_account_number'] as String,
      bankBranchCode: json['bank_branch_code'] as String,
      bankAccountHolder: json['bank_account_holder'] as String,
      verificationStatus: json['verification_status'] as String,
      ownerVettingPassed: json['owner_vetting_passed'] as bool,
      businessVettingPassed: json['business_vetting_passed'] as bool,
      rejectionReason: json['rejection_reason'] as String?,
      verifiedAt: json['verified_at'] as String?,
      isVerified: json['is_verified'] as bool,
      isFullyVetted: json['is_fully_vetted'] as bool,
      totalSales: json['total_sales'] as String,
      totalOrders: json['total_orders'] as int,
      averageRating: json['average_rating'] as String,
      totalReviews: json['total_reviews'] as int,
      commissionRate: json['commission_rate'] as String,
      storeActive: json['store_active'] as bool,
      acceptsReturns: json['accepts_returns'] as bool,
      returnWindowDays: json['return_window_days'] as int,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }
}
```

### 2.7 OTPResponse

```dart
class OTPResponse {
  final String detail;
  final AuthTokens? tokens;
  final int? remainingAttempts;

  OTPResponse({required this.detail, this.tokens, this.remainingAttempts});

  factory OTPResponse.fromJson(Map<String, dynamic> json) {
    return OTPResponse(
      detail: json['detail'] as String,
      tokens: json['tokens'] != null
          ? AuthTokens.fromJson(json['tokens'])
          : null,
      remainingAttempts: json['remaining_attempts'] as int?,
    );
  }
}
```

### 2.8 Address

```dart
class Address {
  final String id;
  final String addressType;
  final String fullName;
  final String phoneNumber;
  final String streetAddress;
  final String? apartmentNumber;
  final String city;
  final String stateProvince;
  final String postalCode;
  final String country;
  final bool isDefault;
  final String? deliveryInstructions;
  final String createdAt;
  final String updatedAt;

  Address({
    required this.id,
    required this.addressType,
    required this.fullName,
    required this.phoneNumber,
    required this.streetAddress,
    this.apartmentNumber,
    required this.city,
    required this.stateProvince,
    required this.postalCode,
    required this.country,
    required this.isDefault,
    this.deliveryInstructions,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Address.fromJson(Map<String, dynamic> json) {
    return Address(
      id: json['id'].toString(),
      addressType: json['address_type'] as String,
      fullName: json['full_name'] as String,
      phoneNumber: json['phone_number'] as String,
      streetAddress: json['street_address'] as String,
      apartmentNumber: json['apartment_number'] as String?,
      city: json['city'] as String,
      stateProvince: json['state_province'] as String,
      postalCode: json['postal_code'] as String,
      country: json['country'] as String,
      isDefault: json['is_default'] as bool,
      deliveryInstructions: json['delivery_instructions'] as String?,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
    'address_type': addressType,
    'full_name': fullName,
    'phone_number': phoneNumber,
    'street_address': streetAddress,
    'apartment_number': apartmentNumber,
    'city': city,
    'state_province': stateProvince,
    'postal_code': postalCode,
    'country': country,
    'is_default': isDefault,
    'delivery_instructions': deliveryInstructions,
  };
}
```

### 2.9 ApiError

```dart
class ApiError {
  final String detail;
  final Map<String, List<String>>? fieldErrors;

  ApiError({required this.detail, this.fieldErrors});

  factory ApiError.fromJson(Map<String, dynamic> json) {
    if (json.containsKey('detail')) {
      return ApiError(detail: json['detail'] as String);
    }
    final fieldErrors = <String, List<String>>{};
    json.forEach((key, value) {
      if (value is List) {
        fieldErrors[key] = value.map((e) => e.toString()).toList();
      }
    });
    return ApiError(
      detail: fieldErrors.values.expand((e) => e).join(', '),
      fieldErrors: fieldErrors,
    );
  }
}
```

---

## 3. Dart / Flutter Setup

### 3.1 Dependencies (`pubspec.yaml`)

```yaml
dependencies:
  http: ^1.2.0
  flutter_secure_storage: ^9.0.0
```

### 3.2 Base API Client

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  static const String baseUrl = 'https://your-domain.com';
  final _storage = const FlutterSecureStorage();

  Future<Map<String, String>> _headers({bool auth = true}) async {
    final headers = {'Content-Type': 'application/json'};
    if (auth) {
      final token = await _storage.read(key: 'access_token');
      if (token != null) headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<http.Response> get(String path, {bool auth = true}) async {
    return http.get(
      Uri.parse('$baseUrl$path'),
      headers: await _headers(auth: auth),
    );
  }

  Future<http.Response> post(String path, Map<String, dynamic> body, {bool auth = true}) async {
    return http.post(
      Uri.parse('$baseUrl$path'),
      headers: await _headers(auth: auth),
      body: jsonEncode(body),
    );
  }

  Future<http.Response> patch(String path, Map<String, dynamic> body, {bool auth = true}) async {
    return http.patch(
      Uri.parse('$baseUrl$path'),
      headers: await _headers(auth: auth),
      body: jsonEncode(body),
    );
  }

  Future<http.Response> delete(String path, {bool auth = true}) async {
    return http.delete(
      Uri.parse('$baseUrl$path'),
      headers: await _headers(auth: auth),
    );
  }

  /// For multipart/form-data uploads (vendor profile creation with documents)
  Future<http.StreamedResponse> multipartPost(
    String path,
    Map<String, String> fields,
    Map<String, String> filePaths,
  ) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl$path'));
    final token = await _storage.read(key: 'access_token');
    if (token != null) request.headers['Authorization'] = 'Bearer $token';

    fields.forEach((key, value) => request.fields[key] = value);

    for (final entry in filePaths.entries) {
      request.files.add(await http.MultipartFile.fromPath(entry.key, entry.value));
    }

    return request.send();
  }
}
```

---

## 4. Customer Registration

### `POST /api/accounts/register/`

**Auth required:** No

### Dart Request

```dart
Future<RegisterResponse> registerCustomer({
  required String email,
  required String username,
  required String firstName,
  required String lastName,
  required String phoneNumber,
  required String password,
  required String passwordConfirm,
  List<int>? interestCategories,
  double? latitude,
  double? longitude,
}) async {
  final body = {
    'email': email,
    'username': username,
    'first_name': firstName,
    'last_name': lastName,
    'phone_number': phoneNumber,
    'user_type': 'customer',
    'password': password,
    'password_confirm': passwordConfirm,
    if (interestCategories != null) 'interest_categories': interestCategories,
    if (latitude != null) 'latitude': latitude,
    if (longitude != null) 'longitude': longitude,
  };

  final response = await apiClient.post('/api/accounts/register/', body, auth: false);

  if (response.statusCode == 201) {
    return RegisterResponse.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### Request Body

```json
{
  "email": "customer@example.com",
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+27821234567",
  "user_type": "customer",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!",
  "interest_categories": [1, 3, 5],
  "latitude": -26.2041,
  "longitude": 28.0473
}
```

### Response Body (`201 Created`)

```json
{
  "user": {
    "id": 1,
    "email": "customer@example.com",
    "username": "johndoe",
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": "+27821234567",
    "user_type": "customer",
    "is_verified": false,
    "date_of_birth": null,
    "is_active": true,
    "date_joined": "2026-03-08T10:00:00Z",
    "created_at": "2026-03-08T10:00:00Z",
    "updated_at": "2026-03-08T10:00:00Z"
  },
  "tokens": {
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

---

## 5. Vendor Registration (Account Only)

### `POST /api/accounts/register/`

**Auth required:** No

Same endpoint as customer registration. Set `user_type` to `"vendor"`. After registration, you must create either an Individual or Business vendor profile (sections 7 & 8).

### Dart Request

```dart
Future<RegisterResponse> registerVendor({
  required String email,
  required String username,
  required String firstName,
  required String lastName,
  required String phoneNumber,
  required String password,
  required String passwordConfirm,
}) async {
  final body = {
    'email': email,
    'username': username,
    'first_name': firstName,
    'last_name': lastName,
    'phone_number': phoneNumber,
    'user_type': 'vendor',
    'password': password,
    'password_confirm': passwordConfirm,
  };

  final response = await apiClient.post('/api/accounts/register/', body, auth: false);

  if (response.statusCode == 201) {
    return RegisterResponse.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### Request Body

```json
{
  "email": "vendor@example.com",
  "username": "myshop",
  "first_name": "Sipho",
  "last_name": "Nkosi",
  "phone_number": "+27831234567",
  "user_type": "vendor",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!"
}
```

### Response Body (`201 Created`)

```json
{
  "user": {
    "id": 2,
    "email": "vendor@example.com",
    "username": "myshop",
    "first_name": "Sipho",
    "last_name": "Nkosi",
    "phone_number": "+27831234567",
    "user_type": "vendor",
    "is_verified": false,
    "date_of_birth": null,
    "is_active": true,
    "date_joined": "2026-03-08T10:00:00Z",
    "created_at": "2026-03-08T10:00:00Z",
    "updated_at": "2026-03-08T10:00:00Z"
  },
  "tokens": {
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

---

## 6. OTP Verification

After registration, users must verify their account using a 6-digit OTP code sent to their email.

### 6.1 Send OTP

#### `POST /api/otp/send/`

**Auth required:** No

```dart
Future<OTPResponse> sendOTP({
  required String email,
  String purpose = 'verification',
}) async {
  final body = {
    'email': email,
    'purpose': purpose,
  };

  final response = await apiClient.post('/api/otp/send/', body, auth: false);

  if (response.statusCode == 200) {
    return OTPResponse.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

#### Request Body

```json
{
  "email": "customer@example.com",
  "purpose": "verification"
}
```

**Purpose options:** `"verification"`, `"password_reset"`, `"login"`

#### Response Body (`200 OK`)

```json
{
  "detail": "OTP has been sent to your email address."
}
```

### 6.2 Verify OTP

#### `POST /api/otp/verify/`

**Auth required:** No

On successful verification with purpose `"verification"`, the user's `is_verified` field is set to `true` and JWT tokens are returned.

```dart
Future<OTPResponse> verifyOTP({
  required String email,
  required String code,
  required String purpose,
}) async {
  final body = {
    'email': email,
    'code': code,
    'purpose': purpose,
  };

  final response = await apiClient.post('/api/otp/verify/', body, auth: false);

  if (response.statusCode == 200) {
    final otpResponse = OTPResponse.fromJson(jsonDecode(response.body));
    // Save tokens if returned
    if (otpResponse.tokens != null) {
      await _storage.write(key: 'access_token', value: otpResponse.tokens!.access);
      await _storage.write(key: 'refresh_token', value: otpResponse.tokens!.refresh);
    }
    return otpResponse;
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

#### Request Body

```json
{
  "email": "customer@example.com",
  "code": "482913",
  "purpose": "verification"
}
```

#### Response Body - Success (`200 OK`)

```json
{
  "detail": "OTP verified successfully.",
  "tokens": {
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

#### Response Body - Invalid Code (`400 Bad Request`)

```json
{
  "detail": "Invalid OTP code.",
  "remaining_attempts": 2
}
```

#### Response Body - Expired (`400 Bad Request`)

```json
{
  "detail": "OTP has expired. Please request a new one."
}
```

#### Response Body - Max Attempts (`400 Bad Request`)

```json
{
  "detail": "Maximum verification attempts exceeded. Please request a new OTP."
}
```

### 6.3 Resend OTP

#### `POST /api/otp/resend/`

**Auth required:** No

Rate-limited: maximum **3 OTP requests per 10 minutes**.

```dart
Future<OTPResponse> resendOTP({
  required String email,
  String purpose = 'verification',
}) async {
  final body = {
    'email': email,
    'purpose': purpose,
  };

  final response = await apiClient.post('/api/otp/resend/', body, auth: false);

  if (response.statusCode == 200) {
    return OTPResponse.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

#### Response Body - Success (`200 OK`)

```json
{
  "detail": "OTP has been resent to your email address."
}
```

#### Response Body - Rate Limited (`429 Too Many Requests`)

```json
{
  "detail": "Too many OTP requests. Please try again later."
}
```

---

## 7. Fetch All Categories

### `GET /api/products/categories/`

**Auth required:** No (public endpoint)

Use this endpoint to get all available product categories. You'll need the category `id` values when creating vendor profiles (sections 8 & 9).

### Dart Request

```dart
Future<List<CategorySummary>> fetchAllCategories() async {
  final response = await apiClient.get('/api/products/categories/', auth: false);

  if (response.statusCode == 200) {
    final List<dynamic> data = jsonDecode(response.body)['results'];
    return data.map((e) => CategorySummary.fromJson(e)).toList();
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### Response Body (`200 OK`)

```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Electronics",
      "slug": "electronics",
      "description": "Electronic devices and accessories",
      "parent": null,
      "image": null,
      "is_active": true,
      "sort_order": 0,
      "full_path": "Electronics",
      "children_count": 2,
      "products_count": 10
    },
    {
      "id": 2,
      "name": "Smartphones",
      "slug": "smartphones",
      "description": "Mobile phones and tablets",
      "parent": 1,
      "image": null,
      "is_active": true,
      "sort_order": 1,
      "full_path": "Electronics > Smartphones",
      "children_count": 0,
      "products_count": 5
    },
    {
      "id": 3,
      "name": "Snacks & Beverages",
      "slug": "snacks-beverages",
      "description": "Food and drink items",
      "parent": null,
      "image": null,
      "is_active": true,
      "sort_order": 2,
      "full_path": "Snacks & Beverages",
      "children_count": 0,
      "products_count": 15
    }
  ]
}
```

> **Note:** Categories with a `parent` field are subcategories. Pass any category `id` (parent or child) in the `category_ids` list when creating a vendor profile.

---

## 8. Create Individual Vendor Profile

### `POST /api/business/profiles/vendor/individual/`

**Auth required:** Yes
**Content-Type:** `multipart/form-data` (file uploads)

Creates an individual vendor profile for informal traders (tuck shops, street vendors, freelancers, etc.). Automatically generates a QR code and triggers owner vetting.

### Dart Request

```dart
Future<IndividualVendorProfile> createIndividualVendorProfile({
  required String storeName,
  String? storeDescription,
  String? storeLogoPath,
  List<int>? categoryIds,
  required String idNumber,
  required String idDocumentPath,
  required String proofOfAddressPath,
  String? selfieWithIdPath,
  String? tradingAddress,
  String? tradingCity,
  String? tradingProvince,
  String? tradingPostalCode,
  String? bankName,
  String? bankAccountNumber,
  String? bankBranchCode,
  String? bankAccountHolder,
}) async {
  final request = http.MultipartRequest(
    'POST',
    Uri.parse('${ApiClient.baseUrl}/api/business/profiles/vendor/individual/'),
  );

  final token = await _storage.read(key: 'access_token');
  if (token != null) request.headers['Authorization'] = 'Bearer $token';

  // Text fields
  request.fields['store_name'] = storeName;
  if (storeDescription != null) request.fields['store_description'] = storeDescription;
  request.fields['id_number'] = idNumber;
  if (tradingAddress != null) request.fields['trading_address'] = tradingAddress;
  if (tradingCity != null) request.fields['trading_city'] = tradingCity;
  if (tradingProvince != null) request.fields['trading_province'] = tradingProvince;
  if (tradingPostalCode != null) request.fields['trading_postal_code'] = tradingPostalCode;
  if (bankName != null) request.fields['bank_name'] = bankName;
  if (bankAccountNumber != null) request.fields['bank_account_number'] = bankAccountNumber;
  if (bankBranchCode != null) request.fields['bank_branch_code'] = bankBranchCode;
  if (bankAccountHolder != null) request.fields['bank_account_holder'] = bankAccountHolder;

  // Category IDs (sent as repeated form fields)
  if (categoryIds != null) {
    for (final id in categoryIds) {
      request.fields.addEntries([MapEntry('category_ids', id.toString())]);
    }
  }

  // File uploads
  request.files.add(await http.MultipartFile.fromPath('id_document', idDocumentPath));
  request.files.add(await http.MultipartFile.fromPath('proof_of_address', proofOfAddressPath));
  if (storeLogoPath != null) {
    request.files.add(await http.MultipartFile.fromPath('store_logo', storeLogoPath));
  }
  if (selfieWithIdPath != null) {
    request.files.add(await http.MultipartFile.fromPath('selfie_with_id', selfieWithIdPath));
  }

  final response = await request.send();
  final body = await response.stream.bytesToString();
  if (response.statusCode == 201) {
    return IndividualVendorProfile.fromJson(jsonDecode(body));
  }
  throw ApiError.fromJson(jsonDecode(body));
}
```

### Request Fields (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `store_name` | string | Yes | Name of the store/business |
| `store_description` | string | No | Description of the store |
| `store_logo` | file | No | Store logo image |
| `category_ids` | list of int | No | Product category IDs this vendor offers (get from `GET /api/products/categories/`) |
| `id_number` | string | Yes | SA ID number |
| `id_document` | file | Yes | Scan/photo of ID document |
| `proof_of_address` | file | Yes | Proof of address document |
| `selfie_with_id` | file | No | Selfie holding ID document |
| `trading_address` | string | No | Trading location address |
| `trading_city` | string | No | Trading city |
| `trading_province` | string | No | Trading province |
| `trading_postal_code` | string | No | Trading postal code |
| `bank_name` | string | No | Bank name |
| `bank_account_number` | string | No | Bank account number |
| `bank_branch_code` | string | No | Bank branch code |
| `bank_account_holder` | string | No | Account holder name |

### Response Body (`201 Created`)

```json
{
  "id": 1,
  "user_email": "vendor@example.com",
  "owner_name": "Sipho Nkosi",
  "store_name": "Sipho's Tuck Shop",
  "store_description": "Best snacks in Soweto",
  "categories": [
    {"id": 3, "name": "Snacks & Beverages", "slug": "snacks-beverages"},
    {"id": 1, "name": "Electronics", "slug": "electronics"}
  ],
  "store_logo": "http://localhost:8101/media/logos/vendors/individual/logo.jpg",
  "qr_code": "http://localhost:8101/media/qrcodes/vendors/individual/vendor_individual_abc123.png",
  "qr_code_identifier": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "id_number": "9001015800089",
  "id_document": "http://localhost:8101/media/documents/vendors/individual/id/id.pdf",
  "proof_of_address": "http://localhost:8101/media/documents/vendors/individual/address/poa.pdf",
  "selfie_with_id": null,
  "trading_address": "123 Main Road, Soweto",
  "trading_city": "Johannesburg",
  "trading_province": "Gauteng",
  "trading_postal_code": "1804",
  "bank_name": "FNB",
  "bank_account_number": "62000000000",
  "bank_branch_code": "250655",
  "bank_account_holder": "Sipho Nkosi",
  "verification_status": "pending",
  "rejection_reason": "",
  "verified_at": null,
  "is_verified": false,
  "total_sales": "0.00",
  "total_orders": 0,
  "average_rating": "0.00",
  "total_reviews": 0,
  "commission_rate": "8.00",
  "store_active": false,
  "accepts_returns": true,
  "return_window_days": 14,
  "created_at": "2026-03-08T10:30:00Z",
  "updated_at": "2026-03-08T10:30:00Z"
}
```

---

## 9. Create Business Vendor Profile

### `POST /api/business/profiles/vendor/business/`

**Auth required:** Yes
**Content-Type:** `multipart/form-data` (file uploads)

Creates a business vendor profile for CIPC-registered businesses. Automatically generates a QR code and triggers **both** owner and business entity vetting.

### Dart Request

```dart
Future<BusinessVendorProfile> createBusinessVendorProfile({
  required String businessName,
  String? businessTradingName,
  required String businessType,
  String? businessDescription,
  String? businessLogoPath,
  String? businessWebsite,
  List<int>? categoryIds,
  required String cipcRegistrationNumber,
  required String cipcDocumentPath,
  String? taxNumber,
  String? taxClearanceCertificatePath,
  String? vatNumber,
  String? beeCertificatePath,
  required String ownerFullName,
  required String ownerIdNumber,
  required String ownerIdDocumentPath,
  required String ownerProofOfAddressPath,
  required String businessStreetAddress,
  required String businessCity,
  required String businessProvince,
  required String businessPostalCode,
  String businessCountry = 'South Africa',
  required String bankName,
  required String bankAccountNumber,
  required String bankBranchCode,
  required String bankAccountHolder,
}) async {
  final request = http.MultipartRequest(
    'POST',
    Uri.parse('${ApiClient.baseUrl}/api/business/profiles/vendor/business/'),
  );

  final token = await _storage.read(key: 'access_token');
  if (token != null) request.headers['Authorization'] = 'Bearer $token';

  // Text fields
  request.fields['business_name'] = businessName;
  if (businessTradingName != null) request.fields['business_trading_name'] = businessTradingName;
  request.fields['business_type'] = businessType;
  if (businessDescription != null) request.fields['business_description'] = businessDescription;
  if (businessWebsite != null) request.fields['business_website'] = businessWebsite;
  request.fields['cipc_registration_number'] = cipcRegistrationNumber;
  if (taxNumber != null) request.fields['tax_number'] = taxNumber;
  if (vatNumber != null) request.fields['vat_number'] = vatNumber;
  request.fields['owner_full_name'] = ownerFullName;
  request.fields['owner_id_number'] = ownerIdNumber;
  request.fields['business_street_address'] = businessStreetAddress;
  request.fields['business_city'] = businessCity;
  request.fields['business_province'] = businessProvince;
  request.fields['business_postal_code'] = businessPostalCode;
  request.fields['business_country'] = businessCountry;
  request.fields['bank_name'] = bankName;
  request.fields['bank_account_number'] = bankAccountNumber;
  request.fields['bank_branch_code'] = bankBranchCode;
  request.fields['bank_account_holder'] = bankAccountHolder;

  // Category IDs (sent as repeated form fields)
  if (categoryIds != null) {
    for (final id in categoryIds) {
      request.fields.addEntries([MapEntry('category_ids', id.toString())]);
    }
  }

  // File uploads
  request.files.add(await http.MultipartFile.fromPath('cipc_document', cipcDocumentPath));
  request.files.add(await http.MultipartFile.fromPath('owner_id_document', ownerIdDocumentPath));
  request.files.add(await http.MultipartFile.fromPath('owner_proof_of_address', ownerProofOfAddressPath));
  if (businessLogoPath != null) {
    request.files.add(await http.MultipartFile.fromPath('business_logo', businessLogoPath));
  }
  if (taxClearanceCertificatePath != null) {
    request.files.add(await http.MultipartFile.fromPath('tax_clearance_certificate', taxClearanceCertificatePath));
  }
  if (beeCertificatePath != null) {
    request.files.add(await http.MultipartFile.fromPath('bee_certificate', beeCertificatePath));
  }

  final response = await request.send();
  final body = await response.stream.bytesToString();
  if (response.statusCode == 201) {
    return BusinessVendorProfile.fromJson(jsonDecode(body));
  }
  throw ApiError.fromJson(jsonDecode(body));
}
```

### Request Fields (multipart/form-data)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `business_name` | string | Yes | Registered business name |
| `business_trading_name` | string | No | Trading-as name |
| `business_type` | string | Yes | One of: `sole_proprietor`, `partnership`, `pty_ltd`, `cc`, `npc`, `cooperative`, `other` |
| `business_description` | string | No | Description |
| `business_logo` | file | No | Business logo |
| `business_website` | string | No | Website URL |
| `category_ids` | list of int | No | Product category IDs this business offers (get from `GET /api/products/categories/`) |
| `cipc_registration_number` | string | Yes | CIPC registration number |
| `cipc_document` | file | Yes | CIPC certificate scan |
| `tax_number` | string | No | SARS tax number |
| `tax_clearance_certificate` | file | No | Tax clearance certificate |
| `vat_number` | string | No | VAT registration number |
| `bee_certificate` | file | No | B-BBEE certificate |
| `owner_full_name` | string | Yes | Business owner full name |
| `owner_id_number` | string | Yes | Owner SA ID number |
| `owner_id_document` | file | Yes | Owner ID document scan |
| `owner_proof_of_address` | file | Yes | Owner proof of address |
| `business_street_address` | string | Yes | Business address |
| `business_city` | string | Yes | Business city |
| `business_province` | string | Yes | Business province |
| `business_postal_code` | string | Yes | Business postal code |
| `business_country` | string | No | Default: `South Africa` |
| `bank_name` | string | Yes | Bank name |
| `bank_account_number` | string | Yes | Bank account number |
| `bank_branch_code` | string | Yes | Bank branch code |
| `bank_account_holder` | string | Yes | Account holder name |

### Response Body (`201 Created`)

```json
{
  "id": 1,
  "user_email": "business@example.com",
  "business_name": "Nkosi Trading (Pty) Ltd",
  "business_trading_name": "Nkosi Traders",
  "business_type": "pty_ltd",
  "business_description": "Premium wholesale distribution",
  "business_logo": "http://localhost:8101/media/logos/vendors/business/logo.png",
  "categories": [
    {"id": 1, "name": "Electronics", "slug": "electronics"},
    {"id": 5, "name": "Wholesale Goods", "slug": "wholesale-goods"}
  ],
  "qr_code": "http://localhost:8101/media/qrcodes/vendors/business/vendor_business_xyz789.png",
  "qr_code_identifier": "x7y8z9a0-b1c2-3456-defg-hij7890abcde",
  "cipc_registration_number": "2024/123456/07",
  "cipc_document": "http://localhost:8101/media/documents/vendors/business/cipc/cert.pdf",
  "tax_number": "9876543210",
  "tax_clearance_certificate": null,
  "vat_number": "4567890123",
  "bee_certificate": null,
  "owner_full_name": "Sipho Nkosi",
  "owner_id_number": "9001015800089",
  "owner_id_document": "http://localhost:8101/media/documents/vendors/business/owner_id/id.pdf",
  "owner_proof_of_address": "http://localhost:8101/media/documents/vendors/business/owner_address/poa.pdf",
  "business_street_address": "45 Commissioner Street",
  "business_city": "Johannesburg",
  "business_province": "Gauteng",
  "business_postal_code": "2001",
  "business_country": "South Africa",
  "bank_name": "Standard Bank",
  "bank_account_number": "000000000",
  "bank_branch_code": "051001",
  "bank_account_holder": "Nkosi Trading (Pty) Ltd",
  "verification_status": "pending",
  "owner_vetting_passed": false,
  "business_vetting_passed": false,
  "rejection_reason": "",
  "verified_at": null,
  "is_verified": false,
  "is_fully_vetted": false,
  "total_sales": "0.00",
  "total_orders": 0,
  "average_rating": "0.00",
  "total_reviews": 0,
  "commission_rate": "5.00",
  "store_active": false,
  "accepts_returns": true,
  "return_window_days": 30,
  "created_at": "2026-03-08T10:30:00Z",
  "updated_at": "2026-03-08T10:30:00Z"
}
```

---

## 10. Login (Obtain JWT Tokens)

### `POST /api/auth/token/`

**Auth required:** No

```dart
Future<AuthTokens> login({
  required String email,
  required String password,
}) async {
  final response = await apiClient.post('/api/auth/token/', {
    'email': email,
    'password': password,
  }, auth: false);

  if (response.statusCode == 200) {
    final tokens = AuthTokens.fromJson(jsonDecode(response.body));
    await _storage.write(key: 'access_token', value: tokens.access);
    await _storage.write(key: 'refresh_token', value: tokens.refresh);
    return tokens;
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### Request Body

```json
{
  "email": "customer@example.com",
  "password": "SecurePass123!"
}
```

### Response Body (`200 OK`)

```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Response Body - Invalid Credentials (`401 Unauthorized`)

```json
{
  "detail": "No active account found with the given credentials"
}
```

---

## 11. Token Refresh

### `POST /api/auth/token/refresh/`

**Auth required:** No

Access tokens expire after **60 minutes**. Use the refresh token (valid **7 days**) to get a new pair. Refresh tokens rotate on use.

```dart
Future<AuthTokens> refreshToken() async {
  final refreshToken = await _storage.read(key: 'refresh_token');
  if (refreshToken == null) throw Exception('No refresh token found');

  final response = await apiClient.post('/api/auth/token/refresh/', {
    'refresh': refreshToken,
  }, auth: false);

  if (response.statusCode == 200) {
    final tokens = AuthTokens.fromJson(jsonDecode(response.body));
    await _storage.write(key: 'access_token', value: tokens.access);
    await _storage.write(key: 'refresh_token', value: tokens.refresh);
    return tokens;
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### Request Body

```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Response Body (`200 OK`)

```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

---

## 12. Token Verify

### `POST /api/auth/token/verify/`

**Auth required:** No

```dart
Future<bool> verifyToken(String token) async {
  final response = await apiClient.post('/api/auth/token/verify/', {
    'token': token,
  }, auth: false);

  return response.statusCode == 200;
}
```

### Request Body

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### Response Body - Valid (`200 OK`)

```json
{}
```

### Response Body - Invalid (`401 Unauthorized`)

```json
{
  "detail": "Token is invalid or expired",
  "code": "token_not_valid"
}
```

---

## 13. Get Current User Profile

### `GET /api/accounts/me/`

**Auth required:** Yes

Returns the full user profile including customer profile, vendor profiles (if any), and addresses.

```dart
Future<User> getCurrentUser() async {
  final response = await apiClient.get('/api/accounts/me/');

  if (response.statusCode == 200) {
    return User.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### Response Body (`200 OK`) - Customer

```json
{
  "id": 1,
  "email": "customer@example.com",
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+27821234567",
  "user_type": "customer",
  "is_verified": true,
  "date_of_birth": null,
  "is_active": true,
  "customer_profile": {
    "id": 1,
    "user_email": "customer@example.com",
    "avatar": null,
    "gender": "M",
    "bio": "",
    "interest_categories": [1, 3, 5],
    "latitude": "-26.204100",
    "longitude": "28.047300",
    "preferred_language": "en",
    "newsletter_subscription": true,
    "sms_notifications": true,
    "email_notifications": true,
    "loyalty_points": 0,
    "member_since": "2026-03-08T10:00:00Z",
    "created_at": "2026-03-08T10:00:00Z",
    "updated_at": "2026-03-08T10:00:00Z"
  },
  "individual_vendor_profile": null,
  "business_vendor_profile": null,
  "addresses": [],
  "date_joined": "2026-03-08T10:00:00Z",
  "created_at": "2026-03-08T10:00:00Z",
  "updated_at": "2026-03-08T10:00:00Z"
}
```

### Response Body (`200 OK`) - Vendor with Individual Profile

```json
{
  "id": 2,
  "email": "vendor@example.com",
  "username": "myshop",
  "first_name": "Sipho",
  "last_name": "Nkosi",
  "phone_number": "+27831234567",
  "user_type": "vendor",
  "is_verified": true,
  "date_of_birth": null,
  "is_active": true,
  "customer_profile": null,
  "individual_vendor_profile": {
    "id": 1,
    "user_email": "vendor@example.com",
    "owner_name": "Sipho Nkosi",
    "store_name": "Sipho's Tuck Shop",
    "vendor_category": "tuck_shop",
    "verification_status": "verified",
    "is_verified": true,
    "qr_code": "http://localhost:8101/media/qrcodes/vendors/individual/vendor_individual_abc123.png",
    "qr_code_identifier": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "store_active": true,
    "..."
  },
  "business_vendor_profile": null,
  "addresses": [
    {
      "id": 1,
      "address_type": "both",
      "full_name": "Sipho Nkosi",
      "phone_number": "+27831234567",
      "street_address": "123 Main Road",
      "apartment_number": "",
      "city": "Johannesburg",
      "state_province": "Gauteng",
      "postal_code": "2001",
      "country": "South Africa",
      "is_default": true,
      "delivery_instructions": "",
      "created_at": "2026-03-08T10:00:00Z",
      "updated_at": "2026-03-08T10:00:00Z"
    }
  ],
  "date_joined": "2026-03-08T10:00:00Z",
  "created_at": "2026-03-08T10:00:00Z",
  "updated_at": "2026-03-08T10:00:00Z"
}
```

---

## 14. Update User Profile

### `PATCH /api/accounts/me/`

**Auth required:** Yes

```dart
Future<User> updateProfile({
  String? firstName,
  String? lastName,
  String? phoneNumber,
  String? dateOfBirth,
}) async {
  final body = {
    if (firstName != null) 'first_name': firstName,
    if (lastName != null) 'last_name': lastName,
    if (phoneNumber != null) 'phone_number': phoneNumber,
    if (dateOfBirth != null) 'date_of_birth': dateOfBirth,
  };

  final response = await apiClient.patch('/api/accounts/me/', body);

  if (response.statusCode == 200) {
    return User.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### Request Body

```json
{
  "first_name": "Jonathan",
  "phone_number": "+27829876543",
  "date_of_birth": "1990-01-15"
}
```

### Response Body (`200 OK`)

Returns the full updated user object (same structure as Section 12).

---

## 15. Update Vendor Profiles

### 14.1 Update Individual Vendor Profile

#### `PATCH /api/business/profiles/vendor/individual/{id}/`

**Auth required:** Yes

```dart
Future<IndividualVendorProfile> updateIndividualProfile(
  String profileId,
  Map<String, dynamic> updates,
) async {
  final response = await apiClient.patch(
    '/api/business/profiles/vendor/individual/$profileId/',
    updates,
  );

  if (response.statusCode == 200) {
    return IndividualVendorProfile.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

#### Request Body

```json
{
  "store_name": "Sipho's Premium Tuck Shop",
  "store_description": "Best snacks and drinks in Soweto - now with delivery!",
  "trading_address": "456 New Road, Soweto",
  "accepts_returns": true,
  "return_window_days": 7
}
```

### 14.2 Update Business Vendor Profile

#### `PATCH /api/business/profiles/vendor/business/{id}/`

**Auth required:** Yes

```dart
Future<BusinessVendorProfile> updateBusinessProfile(
  String profileId,
  Map<String, dynamic> updates,
) async {
  final response = await apiClient.patch(
    '/api/business/profiles/vendor/business/$profileId/',
    updates,
  );

  if (response.statusCode == 200) {
    return BusinessVendorProfile.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

#### Request Body

```json
{
  "business_trading_name": "Nkosi Premium Traders",
  "business_description": "Premium wholesale distribution across Gauteng",
  "business_website": "https://nkositraders.co.za"
}
```

---

## 16. Addresses

### 16.1 List Addresses

#### `GET /api/business/addresses/`

**Auth required:** Yes

```dart
Future<List<Address>> getAddresses() async {
  final response = await apiClient.get('/api/business/addresses/');

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    final results = data['results'] as List;
    return results.map((a) => Address.fromJson(a)).toList();
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### 16.2 Create Address

#### `POST /api/business/addresses/`

**Auth required:** Yes

```dart
Future<Address> createAddress({
  required String addressType,
  required String fullName,
  required String phoneNumber,
  required String streetAddress,
  String? apartmentNumber,
  required String city,
  required String stateProvince,
  required String postalCode,
  String country = 'South Africa',
  bool isDefault = false,
  String? deliveryInstructions,
}) async {
  final body = {
    'address_type': addressType,
    'full_name': fullName,
    'phone_number': phoneNumber,
    'street_address': streetAddress,
    if (apartmentNumber != null) 'apartment_number': apartmentNumber,
    'city': city,
    'state_province': stateProvince,
    'postal_code': postalCode,
    'country': country,
    'is_default': isDefault,
    if (deliveryInstructions != null) 'delivery_instructions': deliveryInstructions,
  };

  final response = await apiClient.post('/api/business/addresses/', body);

  if (response.statusCode == 201) {
    return Address.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

#### Request Body

```json
{
  "address_type": "shipping",
  "full_name": "John Doe",
  "phone_number": "+27821234567",
  "street_address": "123 Main Road",
  "apartment_number": "Unit 4B",
  "city": "Cape Town",
  "state_province": "Western Cape",
  "postal_code": "8001",
  "country": "South Africa",
  "is_default": true,
  "delivery_instructions": "Ring the bell at the gate"
}
```

#### Response Body (`201 Created`)

```json
{
  "id": 1,
  "address_type": "shipping",
  "full_name": "John Doe",
  "phone_number": "+27821234567",
  "street_address": "123 Main Road",
  "apartment_number": "Unit 4B",
  "city": "Cape Town",
  "state_province": "Western Cape",
  "postal_code": "8001",
  "country": "South Africa",
  "is_default": true,
  "delivery_instructions": "Ring the bell at the gate",
  "created_at": "2026-03-08T10:00:00Z",
  "updated_at": "2026-03-08T10:00:00Z"
}
```

### 16.3 Update Address

#### `PATCH /api/business/addresses/{id}/`

**Auth required:** Yes

```dart
Future<Address> updateAddress(String addressId, Map<String, dynamic> updates) async {
  final response = await apiClient.patch('/api/business/addresses/$addressId/', updates);

  if (response.statusCode == 200) {
    return Address.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

### 16.4 Delete Address

#### `DELETE /api/business/addresses/{id}/`

**Auth required:** Yes

```dart
Future<void> deleteAddress(String addressId) async {
  final response = await apiClient.delete('/api/business/addresses/$addressId/');

  if (response.statusCode != 204) {
    throw ApiError.fromJson(jsonDecode(response.body));
  }
}
```

### 16.5 Set Default Address

#### `POST /api/business/addresses/{id}/set_default/`

**Auth required:** Yes

```dart
Future<Address> setDefaultAddress(String addressId) async {
  final response = await apiClient.post(
    '/api/business/addresses/$addressId/set_default/',
    {},
  );

  if (response.statusCode == 200) {
    return Address.fromJson(jsonDecode(response.body));
  }
  throw ApiError.fromJson(jsonDecode(response.body));
}
```

**Address types:** `"billing"`, `"shipping"`, `"both"`

---

## 17. Complete AuthService Class

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthService {
  static const String baseUrl = 'https://your-domain.com';
  final _storage = const FlutterSecureStorage();

  // ---- Helpers ----

  Future<Map<String, String>> _headers({bool auth = true}) async {
    final headers = {'Content-Type': 'application/json'};
    if (auth) {
      final token = await _storage.read(key: 'access_token');
      if (token != null) headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<http.Response> _post(String path, Map<String, dynamic> body, {bool auth = true}) async {
    return http.post(
      Uri.parse('$baseUrl$path'),
      headers: await _headers(auth: auth),
      body: jsonEncode(body),
    );
  }

  Future<http.Response> _get(String path) async {
    return http.get(Uri.parse('$baseUrl$path'), headers: await _headers());
  }

  Future<http.Response> _patch(String path, Map<String, dynamic> body) async {
    return http.patch(
      Uri.parse('$baseUrl$path'),
      headers: await _headers(),
      body: jsonEncode(body),
    );
  }

  Future<http.StreamedResponse> _multipartPost(
    String path,
    Map<String, String> fields,
    Map<String, String> filePaths,
  ) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl$path'));
    final token = await _storage.read(key: 'access_token');
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    fields.forEach((key, value) => request.fields[key] = value);
    for (final entry in filePaths.entries) {
      request.files.add(await http.MultipartFile.fromPath(entry.key, entry.value));
    }
    return request.send();
  }

  // ---- Token Management ----

  Future<void> _saveTokens(AuthTokens tokens) async {
    await _storage.write(key: 'access_token', value: tokens.access);
    await _storage.write(key: 'refresh_token', value: tokens.refresh);
  }

  Future<void> clearTokens() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }

  Future<bool> isLoggedIn() async {
    final token = await _storage.read(key: 'access_token');
    return token != null;
  }

  // ---- Registration ----

  Future<RegisterResponse> registerCustomer({
    required String email,
    required String username,
    required String firstName,
    required String lastName,
    required String phoneNumber,
    required String password,
    required String passwordConfirm,
    List<int>? interestCategories,
    double? latitude,
    double? longitude,
  }) async {
    final body = {
      'email': email,
      'username': username,
      'first_name': firstName,
      'last_name': lastName,
      'phone_number': phoneNumber,
      'user_type': 'customer',
      'password': password,
      'password_confirm': passwordConfirm,
      if (interestCategories != null) 'interest_categories': interestCategories,
      if (latitude != null) 'latitude': latitude,
      if (longitude != null) 'longitude': longitude,
    };
    final response = await _post('/api/accounts/register/', body, auth: false);
    if (response.statusCode == 201) {
      final result = RegisterResponse.fromJson(jsonDecode(response.body));
      await _saveTokens(result.tokens);
      return result;
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  Future<RegisterResponse> registerVendor({
    required String email,
    required String username,
    required String firstName,
    required String lastName,
    required String phoneNumber,
    required String password,
    required String passwordConfirm,
  }) async {
    final body = {
      'email': email,
      'username': username,
      'first_name': firstName,
      'last_name': lastName,
      'phone_number': phoneNumber,
      'user_type': 'vendor',
      'password': password,
      'password_confirm': passwordConfirm,
    };
    final response = await _post('/api/accounts/register/', body, auth: false);
    if (response.statusCode == 201) {
      final result = RegisterResponse.fromJson(jsonDecode(response.body));
      await _saveTokens(result.tokens);
      return result;
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  // ---- OTP Verification ----

  Future<OTPResponse> sendOTP({
    required String email,
    String purpose = 'verification',
  }) async {
    final response = await _post('/api/otp/send/', {
      'email': email,
      'purpose': purpose,
    }, auth: false);
    if (response.statusCode == 200) {
      return OTPResponse.fromJson(jsonDecode(response.body));
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  Future<OTPResponse> verifyOTP({
    required String email,
    required String code,
    required String purpose,
  }) async {
    final response = await _post('/api/otp/verify/', {
      'email': email,
      'code': code,
      'purpose': purpose,
    }, auth: false);
    if (response.statusCode == 200) {
      final result = OTPResponse.fromJson(jsonDecode(response.body));
      if (result.tokens != null) await _saveTokens(result.tokens!);
      return result;
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  Future<OTPResponse> resendOTP({
    required String email,
    String purpose = 'verification',
  }) async {
    final response = await _post('/api/otp/resend/', {
      'email': email,
      'purpose': purpose,
    }, auth: false);
    if (response.statusCode == 200) {
      return OTPResponse.fromJson(jsonDecode(response.body));
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  // ---- Login / Tokens ----

  Future<AuthTokens> login({
    required String email,
    required String password,
  }) async {
    final response = await _post('/api/auth/token/', {
      'email': email,
      'password': password,
    }, auth: false);
    if (response.statusCode == 200) {
      final tokens = AuthTokens.fromJson(jsonDecode(response.body));
      await _saveTokens(tokens);
      return tokens;
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  Future<AuthTokens> refreshToken() async {
    final refreshToken = await _storage.read(key: 'refresh_token');
    if (refreshToken == null) throw Exception('No refresh token');
    final response = await _post('/api/auth/token/refresh/', {
      'refresh': refreshToken,
    }, auth: false);
    if (response.statusCode == 200) {
      final tokens = AuthTokens.fromJson(jsonDecode(response.body));
      await _saveTokens(tokens);
      return tokens;
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  Future<bool> verifyToken(String token) async {
    final response = await _post('/api/auth/token/verify/', {
      'token': token,
    }, auth: false);
    return response.statusCode == 200;
  }

  // ---- User Profile ----

  Future<User> getCurrentUser() async {
    final response = await _get('/api/accounts/me/');
    if (response.statusCode == 200) {
      return User.fromJson(jsonDecode(response.body));
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  Future<User> updateProfile(Map<String, dynamic> updates) async {
    final response = await _patch('/api/accounts/me/', updates);
    if (response.statusCode == 200) {
      return User.fromJson(jsonDecode(response.body));
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  // ---- Vendor Profiles (under /api/business/) ----

  Future<IndividualVendorProfile> createIndividualVendorProfile({
    required Map<String, String> fields,
    required Map<String, String> filePaths,
  }) async {
    final response = await _multipartPost(
      '/api/business/profiles/vendor/individual/',
      fields,
      filePaths,
    );
    final body = await response.stream.bytesToString();
    if (response.statusCode == 201) {
      return IndividualVendorProfile.fromJson(jsonDecode(body));
    }
    throw ApiError.fromJson(jsonDecode(body));
  }

  Future<BusinessVendorProfile> createBusinessVendorProfile({
    required Map<String, String> fields,
    required Map<String, String> filePaths,
  }) async {
    final response = await _multipartPost(
      '/api/business/profiles/vendor/business/',
      fields,
      filePaths,
    );
    final body = await response.stream.bytesToString();
    if (response.statusCode == 201) {
      return BusinessVendorProfile.fromJson(jsonDecode(body));
    }
    throw ApiError.fromJson(jsonDecode(body));
  }

  // ---- Addresses (under /api/business/) ----

  Future<List<Address>> getAddresses() async {
    final response = await _get('/api/business/addresses/');
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final results = data['results'] as List;
      return results.map((a) => Address.fromJson(a)).toList();
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  Future<Address> createAddress(Map<String, dynamic> data) async {
    final response = await _post('/api/business/addresses/', data);
    if (response.statusCode == 201) {
      return Address.fromJson(jsonDecode(response.body));
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  Future<Address> updateAddress(String id, Map<String, dynamic> updates) async {
    final response = await _patch('/api/business/addresses/$id/', updates);
    if (response.statusCode == 200) {
      return Address.fromJson(jsonDecode(response.body));
    }
    throw ApiError.fromJson(jsonDecode(response.body));
  }

  // ---- Logout ----

  Future<void> logout() async {
    await clearTokens();
  }
}
```

---

## 18. Error Handling

### Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | Success |
| `201` | Created |
| `204` | No Content (deleted) |
| `400` | Bad Request - validation errors |
| `401` | Unauthorized - invalid/missing token |
| `403` | Forbidden - no permission |
| `404` | Not Found |
| `429` | Too Many Requests (rate limited) |

### Dart Error Handling Pattern

```dart
try {
  final user = await authService.login(
    email: 'test@example.com',
    password: 'password123',
  );
  print('Logged in as ${user.email}');
} on ApiError catch (e) {
  // Field-specific errors
  if (e.fieldErrors != null) {
    e.fieldErrors!.forEach((field, errors) {
      print('$field: ${errors.join(", ")}');
    });
  } else {
    print('Error: ${e.detail}');
  }
} catch (e) {
  print('Network error: $e');
}
```

### Auto Token Refresh Interceptor

```dart
Future<http.Response> authenticatedRequest(
  Future<http.Response> Function() request,
) async {
  var response = await request();

  if (response.statusCode == 401) {
    try {
      await authService.refreshToken();
      response = await request();
    } catch (_) {
      await authService.logout();
      // Navigate to login screen
      rethrow;
    }
  }

  return response;
}
```

---

## 19. Best Practices

### Registration & Verification Flow

```
1. Register  →  POST /api/accounts/register/
2. Send OTP  →  POST /api/otp/send/
3. User enters 6-digit code from email
4. Verify    →  POST /api/otp/verify/
5. User is now verified (is_verified = true)
```

### Vendor Onboarding Flow

```
1. Register as vendor  →  POST /api/accounts/register/  (user_type: "vendor")
2. Verify via OTP      →  POST /api/otp/verify/
3. Create profile      →  POST /api/business/profiles/vendor/individual/
                       OR  POST /api/business/profiles/vendor/business/
4. Vetting happens automatically (verification_status: "pending")
5. Admin reviews and approves → vendor can start selling
```

### Token Lifecycle

- **Access token:** expires in **60 minutes**
- **Refresh token:** expires in **7 days**, rotates on use
- Always store tokens securely using `flutter_secure_storage`
- Implement auto-refresh on 401 responses
- Clear tokens on logout

### OTP Rules

- OTP codes are **6 digits**, valid for **10 minutes**
- Maximum **3 failed verification attempts** per code
- Maximum **3 OTP requests per 10 minutes** (rate limiting)
- Previous unused OTPs are invalidated when a new one is sent

### Security Tips

- Never log or print JWT tokens in production
- Use HTTPS for all API calls
- Validate certificates in production
- Handle token expiration gracefully with auto-refresh
- Store sensitive data only in secure storage
