# Sanoa Platform - Business API Documentation

**Dart / Flutter Complete Reference**
**Currency: ZAR (South African Rand)**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Dart Models](#2-dart-models)
3. [Dart / Flutter Setup](#3-dart--flutter-setup)
4. [Individual Vendor Profiles](#4-individual-vendor-profiles)
5. [Business Vendor Profiles](#5-business-vendor-profiles)
6. [Vetting Applications](#6-vetting-applications)
7. [Vendor Documents](#7-vendor-documents)
8. [Addresses](#8-addresses)
9. [Business Followers](#9-business-followers)
10. [Store Discovery](#10-store-discovery)
11. [Complete BusinessService Class](#11-complete-businessservice-class)
12. [Error Handling](#12-error-handling)
13. [Best Practices](#13-best-practices)

---

## 1. Overview

Sanoa uses **JWT (JSON Web Token)** authentication via Django REST Framework SimpleJWT. All authenticated requests must include the access token in the `Authorization` header as: `Bearer <token>`.

- **Base URL:** `https://your-domain.com` (replace with your server)
- **All monetary values are in ZAR (South African Rand)**

### App Structure

| App | Responsibility |
|-----|---------------|
| `business` | Vendor profiles (individual & business), vetting process, addresses, followers, store discovery |

### Vendor Types

| Type | Description | Vetting Process |
|------|-------------|----------------|
| `individual` | Informal traders without CIPC registration (tuck shops, street vendors, freelancers) | Owner vetting only |
| `business` | CIPC-registered businesses | Owner vetting + Business entity vetting |

### Vetting Process

1. **Profile Creation** → Auto-generates vetting applications
2. **Document Review** → Admin reviews submitted documents
3. **Verification** → ID, address, business docs, banking verified
4. **Approval/Rejection** → Store activated or rejection with reason
5. **Resubmission** → Vendors can resubmit documents if requested

### All Endpoints

| Method | Endpoint | Description | Auth | User Type |
|--------|----------|-------------|------|-----------|
| `GET` | `/api/business/profiles/vendor/individual/` | List individual vendor profiles | Yes | Vendor/Admin |
| `POST` | `/api/business/profiles/vendor/individual/` | Create individual vendor profile | Yes | Vendor |
| `GET` | `/api/business/profiles/vendor/individual/{id}/` | Get individual vendor profile | Yes | Vendor/Admin |
| `PUT` | `/api/business/profiles/vendor/individual/{id}/` | Update individual vendor profile | Yes | Vendor/Admin |
| `PATCH` | `/api/business/profiles/vendor/individual/{id}/` | Partial update individual vendor profile | Yes | Vendor/Admin |
| `DELETE` | `/api/business/profiles/vendor/individual/{id}/` | Delete individual vendor profile | Yes | Vendor/Admin |
| `GET` | `/api/business/profiles/vendor/individual/{id}/vetting-status/` | Get vetting status | Yes | Vendor/Admin |
| `GET` | `/api/business/profiles/vendor/individual/{id}/documents/` | List vendor documents | Yes | Vendor/Admin |
| `POST` | `/api/business/profiles/vendor/individual/{id}/upload-document/` | Upload document | Yes | Vendor/Admin |
| `GET` | `/api/business/profiles/vendor/business/` | List business vendor profiles | Yes | Vendor/Admin |
| `POST` | `/api/business/profiles/vendor/business/` | Create business vendor profile | Yes | Vendor |
| `GET` | `/api/business/profiles/vendor/business/{id}/` | Get business vendor profile | Yes | Vendor/Admin |
| `PUT` | `/api/business/profiles/vendor/business/{id}/` | Update business vendor profile | Yes | Vendor/Admin |
| `PATCH` | `/api/business/profiles/vendor/business/{id}/` | Partial update business vendor profile | Yes | Vendor/Admin |
| `DELETE` | `/api/business/profiles/vendor/business/{id}/` | Delete business vendor profile | Yes | Vendor/Admin |
| `GET` | `/api/business/profiles/vendor/business/{id}/vetting-status/` | Get vetting status | Yes | Vendor/Admin |
| `GET` | `/api/business/profiles/vendor/business/{id}/documents/` | List vendor documents | Yes | Vendor/Admin |
| `POST` | `/api/business/profiles/vendor/business/{id}/upload-document/` | Upload document | Yes | Vendor/Admin |
| `GET` | `/api/business/vetting/` | List vetting applications | Yes | Vendor/Admin |
| `GET` | `/api/business/vetting/{id}/` | Get vetting application | Yes | Vendor/Admin |
| `PUT` | `/api/business/vetting/{id}/` | Update vetting application | Yes | Admin |
| `PATCH` | `/api/business/vetting/{id}/` | Partial update vetting application | Yes | Admin |
| `POST` | `/api/business/vetting/{id}/approve/` | Approve vetting application | Yes | Admin |
| `POST` | `/api/business/vetting/{id}/reject/` | Reject vetting application | Yes | Admin |
| `POST` | `/api/business/vetting/{id}/request-resubmission/` | Request resubmission | Yes | Admin |
| `GET` | `/api/business/vendor-documents/` | List vendor documents | Yes | Admin |
| `GET` | `/api/business/vendor-documents/{id}/` | Get vendor document | Yes | Admin |
| `PUT` | `/api/business/vendor-documents/{id}/` | Update vendor document | Yes | Admin |
| `PATCH` | `/api/business/vendor-documents/{id}/` | Partial update vendor document | Yes | Admin |
| `DELETE` | `/api/business/vendor-documents/{id}/` | Delete vendor document | Yes | Admin |
| `POST` | `/api/business/vendor-documents/{id}/approve/` | Approve document | Yes | Admin |
| `POST` | `/api/business/vendor-documents/{id}/reject/` | Reject document | Yes | Admin |
| `GET` | `/api/business/addresses/` | List user addresses | Yes | Any |
| `POST` | `/api/business/addresses/` | Create address | Yes | Any |
| `GET` | `/api/business/addresses/{id}/` | Get address | Yes | Any |
| `PUT` | `/api/business/addresses/{id}/` | Update address | Yes | Any |
| `PATCH` | `/api/business/addresses/{id}/` | Partial update address | Yes | Any |
| `DELETE` | `/api/business/addresses/{id}/` | Delete address | Yes | Any |
| `POST` | `/api/business/addresses/{id}/set-default/` | Set as default address | Yes | Any |
| `GET` | `/api/business/followers/my-following/` | List followed businesses | Yes | Customer |
| `POST` | `/api/business/followers/follow/` | Follow a business | Yes | Customer |
| `POST` | `/api/business/followers/unfollow/` | Unfollow a business | Yes | Customer |
| `GET` | `/api/business/followers/followers/{vendor_id}/` | Get follower count | No | Any |
| `GET` | `/api/business/discover-stores/` | Discover stores | Yes | Any |

---

## 2. Dart Models

### 2.1 CategorySummary

```dart
class CategorySummary {
  final int id;
  final String name;
  final String slug;
  final String description;
  final String? image;

  CategorySummary({
    required this.id,
    required this.name,
    required this.slug,
    required this.description,
    this.image,
  });

  factory CategorySummary.fromJson(Map<String, dynamic> json) {
    return CategorySummary(
      id: json['id'] as int,
      name: json['name'] as String,
      slug: json['slug'] as String,
      description: json['description'] as String,
      image: json['image'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'slug': slug,
    'description': description,
    'image': image,
  };
}
```

### 2.2 IndividualVendorProfile

```dart
class IndividualVendorProfile {
  final int id;
  final String userEmail;
  final String ownerName;
  final bool isVerified;
  final String vendorType;
  final String storeName;
  final String storeDescription;
  final String? storeLogo;
  final List<CategorySummary> categories;
  final String? qrCode;
  final String qrCodeIdentifier;
  final String idNumber;
  final String idDocument;
  final String proofOfAddress;
  final String? selfieWithId;
  final String? tradingAddress;
  final String? tradingCity;
  final String? tradingProvince;
  final String? tradingPostalCode;
  final String bankName;
  final String bankAccountNumber;
  final String bankBranchCode;
  final String bankAccountHolder;
  final String verificationStatus;
  final String? rejectionReason;
  final DateTime? verifiedAt;
  final double totalSales;
  final int totalOrders;
  final double averageRating;
  final int totalReviews;
  final double commissionRate;
  final bool storeActive;
  final bool acceptsReturns;
  final int returnWindowDays;
  final DateTime createdAt;
  final DateTime updatedAt;

  IndividualVendorProfile({
    required this.id,
    required this.userEmail,
    required this.ownerName,
    required this.isVerified,
    required this.vendorType,
    required this.storeName,
    required this.storeDescription,
    this.storeLogo,
    required this.categories,
    this.qrCode,
    required this.qrCodeIdentifier,
    required this.idNumber,
    required this.idDocument,
    required this.proofOfAddress,
    this.selfieWithId,
    this.tradingAddress,
    this.tradingCity,
    this.tradingProvince,
    this.tradingPostalCode,
    required this.bankName,
    required this.bankAccountNumber,
    required this.bankBranchCode,
    required this.bankAccountHolder,
    required this.verificationStatus,
    this.rejectionReason,
    this.verifiedAt,
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
      id: json['id'] as int,
      userEmail: json['user_email'] as String,
      ownerName: json['owner_name'] as String,
      isVerified: json['is_verified'] as bool,
      vendorType: json['vendor_type'] as String,
      storeName: json['store_name'] as String,
      storeDescription: json['store_description'] as String,
      storeLogo: json['store_logo'] as String?,
      categories: (json['categories'] as List<dynamic>?)
          ?.map((e) => CategorySummary.fromJson(e as Map<String, dynamic>))
          .toList() ?? [],
      qrCode: json['qr_code'] as String?,
      qrCodeIdentifier: json['qr_code_identifier'] as String,
      idNumber: json['id_number'] as String,
      idDocument: json['id_document'] as String,
      proofOfAddress: json['proof_of_address'] as String,
      selfieWithId: json['selfie_with_id'] as String?,
      tradingAddress: json['trading_address'] as String?,
      tradingCity: json['trading_city'] as String?,
      tradingProvince: json['trading_province'] as String?,
      tradingPostalCode: json['trading_postal_code'] as String?,
      bankName: json['bank_name'] as String,
      bankAccountNumber: json['bank_account_number'] as String,
      bankBranchCode: json['bank_branch_code'] as String,
      bankAccountHolder: json['bank_account_holder'] as String,
      verificationStatus: json['verification_status'] as String,
      rejectionReason: json['rejection_reason'] as String?,
      verifiedAt: json['verified_at'] != null ? DateTime.parse(json['verified_at'] as String) : null,
      totalSales: (json['total_sales'] as num).toDouble(),
      totalOrders: json['total_orders'] as int,
      averageRating: (json['average_rating'] as num).toDouble(),
      totalReviews: json['total_reviews'] as int,
      commissionRate: (json['commission_rate'] as num).toDouble(),
      storeActive: json['store_active'] as bool,
      acceptsReturns: json['accepts_returns'] as bool,
      returnWindowDays: json['return_window_days'] as int,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'user_email': userEmail,
    'owner_name': ownerName,
    'is_verified': isVerified,
    'vendor_type': vendorType,
    'store_name': storeName,
    'store_description': storeDescription,
    'store_logo': storeLogo,
    'categories': categories.map((e) => e.toJson()).toList(),
    'qr_code': qrCode,
    'qr_code_identifier': qrCodeIdentifier,
    'id_number': idNumber,
    'id_document': idDocument,
    'proof_of_address': proofOfAddress,
    'selfie_with_id': selfieWithId,
    'trading_address': tradingAddress,
    'trading_city': tradingCity,
    'trading_province': tradingProvince,
    'trading_postal_code': tradingPostalCode,
    'bank_name': bankName,
    'bank_account_number': bankAccountNumber,
    'bank_branch_code': bankBranchCode,
    'bank_account_holder': bankAccountHolder,
    'verification_status': verificationStatus,
    'rejection_reason': rejectionReason,
    'verified_at': verifiedAt?.toIso8601String(),
    'total_sales': totalSales,
    'total_orders': totalOrders,
    'average_rating': averageRating,
    'total_reviews': totalReviews,
    'commission_rate': commissionRate,
    'store_active': storeActive,
    'accepts_returns': acceptsReturns,
    'return_window_days': returnWindowDays,
    'created_at': createdAt.toIso8601String(),
    'updated_at': updatedAt.toIso8601String(),
  };
}
```

### 2.3 BusinessVendorProfile

```dart
class BusinessVendorProfile {
  final int id;
  final String userEmail;
  final bool isVerified;
  final bool isFullyVetted;
  final String businessName;
  final String? businessTradingName;
  final String businessType;
  final String businessDescription;
  final String? businessLogo;
  final String? businessWebsite;
  final List<CategorySummary> categories;
  final String? qrCode;
  final String qrCodeIdentifier;
  final String cipcRegistrationNumber;
  final String cipcDocument;
  final String? taxNumber;
  final String? taxClearanceCertificate;
  final String? vatNumber;
  final String? beeCertificate;
  final String ownerFullName;
  final String ownerIdNumber;
  final String ownerIdDocument;
  final String ownerProofOfAddress;
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
  final DateTime? verifiedAt;
  final double totalSales;
  final int totalOrders;
  final double averageRating;
  final int totalReviews;
  final double commissionRate;
  final bool storeActive;
  final bool acceptsReturns;
  final int returnWindowDays;
  final DateTime createdAt;
  final DateTime updatedAt;

  BusinessVendorProfile({
    required this.id,
    required this.userEmail,
    required this.isVerified,
    required this.isFullyVetted,
    required this.businessName,
    this.businessTradingName,
    required this.businessType,
    required this.businessDescription,
    this.businessLogo,
    this.businessWebsite,
    required this.categories,
    this.qrCode,
    required this.qrCodeIdentifier,
    required this.cipcRegistrationNumber,
    required this.cipcDocument,
    this.taxNumber,
    this.taxClearanceCertificate,
    this.vatNumber,
    this.beeCertificate,
    required this.ownerFullName,
    required this.ownerIdNumber,
    required this.ownerIdDocument,
    required this.ownerProofOfAddress,
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
      id: json['id'] as int,
      userEmail: json['user_email'] as String,
      isVerified: json['is_verified'] as bool,
      isFullyVetted: json['is_fully_vetted'] as bool,
      businessName: json['business_name'] as String,
      businessTradingName: json['business_trading_name'] as String?,
      businessType: json['business_type'] as String,
      businessDescription: json['business_description'] as String,
      businessLogo: json['business_logo'] as String?,
      businessWebsite: json['business_website'] as String?,
      categories: (json['categories'] as List<dynamic>?)
          ?.map((e) => CategorySummary.fromJson(e as Map<String, dynamic>))
          .toList() ?? [],
      qrCode: json['qr_code'] as String?,
      qrCodeIdentifier: json['qr_code_identifier'] as String,
      cipcRegistrationNumber: json['cipc_registration_number'] as String,
      cipcDocument: json['cipc_document'] as String,
      taxNumber: json['tax_number'] as String?,
      taxClearanceCertificate: json['tax_clearance_certificate'] as String?,
      vatNumber: json['vat_number'] as String?,
      beeCertificate: json['bee_certificate'] as String?,
      ownerFullName: json['owner_full_name'] as String,
      ownerIdNumber: json['owner_id_number'] as String,
      ownerIdDocument: json['owner_id_document'] as String,
      ownerProofOfAddress: json['owner_proof_of_address'] as String,
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
      verifiedAt: json['verified_at'] != null ? DateTime.parse(json['verified_at'] as String) : null,
      totalSales: (json['total_sales'] as num).toDouble(),
      totalOrders: json['total_orders'] as int,
      averageRating: (json['average_rating'] as num).toDouble(),
      totalReviews: json['total_reviews'] as int,
      commissionRate: (json['commission_rate'] as num).toDouble(),
      storeActive: json['store_active'] as bool,
      acceptsReturns: json['accepts_returns'] as bool,
      returnWindowDays: json['return_window_days'] as int,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'user_email': userEmail,
    'is_verified': isVerified,
    'is_fully_vetted': isFullyVetted,
    'business_name': businessName,
    'business_trading_name': businessTradingName,
    'business_type': businessType,
    'business_description': businessDescription,
    'business_logo': businessLogo,
    'business_website': businessWebsite,
    'categories': categories.map((e) => e.toJson()).toList(),
    'qr_code': qrCode,
    'qr_code_identifier': qrCodeIdentifier,
    'cipc_registration_number': cipcRegistrationNumber,
    'cipc_document': cipcDocument,
    'tax_number': taxNumber,
    'tax_clearance_certificate': taxClearanceCertificate,
    'vat_number': vatNumber,
    'bee_certificate': beeCertificate,
    'owner_full_name': ownerFullName,
    'owner_id_number': ownerIdNumber,
    'owner_id_document': ownerIdDocument,
    'owner_proof_of_address': ownerProofOfAddress,
    'business_street_address': businessStreetAddress,
    'business_city': businessCity,
    'business_province': businessProvince,
    'business_postal_code': businessPostalCode,
    'business_country': businessCountry,
    'bank_name': bankName,
    'bank_account_number': bankAccountNumber,
    'bank_branch_code': bankBranchCode,
    'bank_account_holder': bankAccountHolder,
    'verification_status': verificationStatus,
    'owner_vetting_passed': ownerVettingPassed,
    'business_vetting_passed': businessVettingPassed,
    'rejection_reason': rejectionReason,
    'verified_at': verifiedAt?.toIso8601String(),
    'total_sales': totalSales,
    'total_orders': totalOrders,
    'average_rating': averageRating,
    'total_reviews': totalReviews,
    'commission_rate': commissionRate,
    'store_active': storeActive,
    'accepts_returns': acceptsReturns,
    'return_window_days': returnWindowDays,
    'created_at': createdAt.toIso8601String(),
    'updated_at': updatedAt.toIso8601String(),
  };
}
```

### 2.4 VettingApplication

```dart
class VettingApplication {
  final int id;
  final String vettingType;
  final String status;
  final bool idVerified;
  final bool addressVerified;
  final bool selfieVerified;
  final bool cipcVerified;
  final bool taxVerified;
  final bool bankVerified;
  final String? rejectionReason;
  final DateTime submittedAt;
  final DateTime? reviewedAt;
  final DateTime? completedAt;

  VettingApplication({
    required this.id,
    required this.vettingType,
    required this.status,
    required this.idVerified,
    required this.addressVerified,
    required this.selfieVerified,
    required this.cipcVerified,
    required this.taxVerified,
    required this.bankVerified,
    this.rejectionReason,
    required this.submittedAt,
    this.reviewedAt,
    this.completedAt,
  });

  factory VettingApplication.fromJson(Map<String, dynamic> json) {
    return VettingApplication(
      id: json['id'] as int,
      vettingType: json['vetting_type'] as String,
      status: json['status'] as String,
      idVerified: json['id_verified'] as bool,
      addressVerified: json['address_verified'] as bool,
      selfieVerified: json['selfie_verified'] as bool,
      cipcVerified: json['cipc_verified'] as bool,
      taxVerified: json['tax_verified'] as bool,
      bankVerified: json['bank_verified'] as bool,
      rejectionReason: json['rejection_reason'] as String?,
      submittedAt: DateTime.parse(json['submitted_at'] as String),
      reviewedAt: json['reviewed_at'] != null ? DateTime.parse(json['reviewed_at'] as String) : null,
      completedAt: json['completed_at'] != null ? DateTime.parse(json['completed_at'] as String) : null,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'vetting_type': vettingType,
    'status': status,
    'id_verified': idVerified,
    'address_verified': addressVerified,
    'selfie_verified': selfieVerified,
    'cipc_verified': cipcVerified,
    'tax_verified': taxVerified,
    'bank_verified': bankVerified,
    'rejection_reason': rejectionReason,
    'submitted_at': submittedAt.toIso8601String(),
    'reviewed_at': reviewedAt?.toIso8601String(),
    'completed_at': completedAt?.toIso8601String(),
  };
}
```

### 2.5 VendorDocument

```dart
class VendorDocument {
  final int id;
  final String documentType;
  final String documentFile;
  final String documentName;
  final String status;
  final String? reviewNotes;
  final DateTime uploadedAt;

  VendorDocument({
    required this.id,
    required this.documentType,
    required this.documentFile,
    required this.documentName,
    required this.status,
    this.reviewNotes,
    required this.uploadedAt,
  });

  factory VendorDocument.fromJson(Map<String, dynamic> json) {
    return VendorDocument(
      id: json['id'] as int,
      documentType: json['document_type'] as String,
      documentFile: json['document_file'] as String,
      documentName: json['document_name'] as String,
      status: json['status'] as String,
      reviewNotes: json['review_notes'] as String?,
      uploadedAt: DateTime.parse(json['uploaded_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'document_type': documentType,
    'document_file': documentFile,
    'document_name': documentName,
    'status': status,
    'review_notes': reviewNotes,
    'uploaded_at': uploadedAt.toIso8601String(),
  };
}
```

### 2.6 Address

```dart
class Address {
  final int id;
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
  final DateTime createdAt;
  final DateTime updatedAt;

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
      id: json['id'] as int,
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
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
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
    'created_at': createdAt.toIso8601String(),
    'updated_at': updatedAt.toIso8601String(),
  };
}
```

### 2.7 BusinessFollower

```dart
class BusinessFollower {
  final int id;
  final int user;
  final String userEmail;
  final int vendor;
  final String vendorEmail;
  final String vendorName;
  final DateTime createdAt;

  BusinessFollower({
    required this.id,
    required this.user,
    required this.userEmail,
    required this.vendor,
    required this.vendorEmail,
    required this.vendorName,
    required this.createdAt,
  });

  factory BusinessFollower.fromJson(Map<String, dynamic> json) {
    return BusinessFollower(
      id: json['id'] as int,
      user: json['user'] as int,
      userEmail: json['user_email'] as String,
      vendor: json['vendor'] as int,
      vendorEmail: json['vendor_email'] as String,
      vendorName: json['vendor_name'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'user': user,
    'user_email': userEmail,
    'vendor': vendor,
    'vendor_email': vendorEmail,
    'vendor_name': vendorName,
    'created_at': createdAt.toIso8601String(),
  };
}
```

### 2.8 StoreDiscoveryResult

```dart
class StoreDiscoveryResult {
  final String type; // 'nearby' or 'recommended'
  final List<StoreDiscoveryItem> stores;

  StoreDiscoveryResult({
    required this.type,
    required this.stores,
  });

  factory StoreDiscoveryResult.fromJson(Map<String, dynamic> json) {
    return StoreDiscoveryResult(
      type: json['type'] as String,
      stores: (json['stores'] as List<dynamic>)
          .map((e) => StoreDiscoveryItem.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() => {
    'type': type,
    'stores': stores.map((e) => e.toJson()).toList(),
  };
}

class StoreDiscoveryItem {
  final int vendorId;
  final String vendorType; // 'individual' or 'business'
  final String storeName;
  final String? storeDescription;
  final String? storeLogo;
  final double? distanceKm;
  final double? relevanceScore;
  final List<String> categories;
  final double averageRating;
  final int totalReviews;
  final bool isFollowing;

  StoreDiscoveryItem({
    required this.vendorId,
    required this.vendorType,
    required this.storeName,
    this.storeDescription,
    this.storeLogo,
    this.distanceKm,
    this.relevanceScore,
    required this.categories,
    required this.averageRating,
    required this.totalReviews,
    required this.isFollowing,
  });

  factory StoreDiscoveryItem.fromJson(Map<String, dynamic> json) {
    return StoreDiscoveryItem(
      vendorId: json['vendor_id'] as int,
      vendorType: json['vendor_type'] as String,
      storeName: json['store_name'] as String,
      storeDescription: json['store_description'] as String?,
      storeLogo: json['store_logo'] as String?,
      distanceKm: json['distance_km'] != null ? (json['distance_km'] as num).toDouble() : null,
      relevanceScore: json['relevance_score'] != null ? (json['relevance_score'] as num).toDouble() : null,
      categories: List<String>.from(json['categories'] as List),
      averageRating: (json['average_rating'] as num).toDouble(),
      totalReviews: json['total_reviews'] as int,
      isFollowing: json['is_following'] as bool,
    );
  }

  Map<String, dynamic> toJson() => {
    'vendor_id': vendorId,
    'vendor_type': vendorType,
    'store_name': storeName,
    'store_description': storeDescription,
    'store_logo': storeLogo,
    'distance_km': distanceKm,
    'relevance_score': relevanceScore,
    'categories': categories,
    'average_rating': averageRating,
    'total_reviews': totalReviews,
    'is_following': isFollowing,
  };
}
```

---

## 3. Dart / Flutter Setup

### 3.1 Dependencies

Add to `pubspec.yaml`:

```yaml
dependencies:
  http: ^1.1.0
  shared_preferences: ^2.2.2
  image_picker: ^1.0.4
```

### 3.2 Base API Client

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiClient {
  static const String baseUrl = 'https://your-domain.com'; // Replace with your server
  static const String tokenKey = 'access_token';

  static Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(tokenKey);
  }

  static Future<void> setToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(tokenKey, token);
  }

  static Future<Map<String, String>> getHeaders({bool auth = true}) async {
    final headers = {'Content-Type': 'application/json'};
    if (auth) {
      final token = await getToken();
      if (token != null) {
        headers['Authorization'] = 'Bearer $token';
      }
    }
    return headers;
  }

  static Future<Map<String, String>> getMultipartHeaders({bool auth = true}) async {
    final headers = <String, String>{};
    if (auth) {
      final token = await getToken();
      if (token != null) {
        headers['Authorization'] = 'Bearer $token';
      }
    }
    return headers;
  }

  static Future<http.Response> get(String endpoint, {bool auth = true}) async {
    final url = Uri.parse('$baseUrl$endpoint');
    final headers = await getHeaders(auth: auth);
    return await http.get(url, headers: headers);
  }

  static Future<http.Response> post(String endpoint, {Map<String, dynamic>? body, bool auth = true}) async {
    final url = Uri.parse('$baseUrl$endpoint');
    final headers = await getHeaders(auth: auth);
    return await http.post(url, headers: headers, body: jsonEncode(body));
  }

  static Future<http.Response> put(String endpoint, {Map<String, dynamic>? body, bool auth = true}) async {
    final url = Uri.parse('$baseUrl$endpoint');
    final headers = await getHeaders(auth: auth);
    return await http.put(url, headers: headers, body: jsonEncode(body));
  }

  static Future<http.Response> patch(String endpoint, {Map<String, dynamic>? body, bool auth = true}) async {
    final url = Uri.parse('$baseUrl$endpoint');
    final headers = await getHeaders(auth: auth);
    return await http.patch(url, headers: headers, body: jsonEncode(body));
  }

  static Future<http.Response> delete(String endpoint, {bool auth = true}) async {
    final url = Uri.parse('$baseUrl$endpoint');
    final headers = await getHeaders(auth: auth);
    return await http.delete(url, headers: headers);
  }

  static Future<http.StreamedResponse> multipartPost(
    String endpoint, {
    required Map<String, String> fields,
    List<http.MultipartFile>? files,
    bool auth = true,
  }) async {
    final url = Uri.parse('$baseUrl$endpoint');
    final headers = await getMultipartHeaders(auth: auth);
    final request = http.MultipartRequest('POST', url)..headers.addAll(headers);

    fields.forEach((key, value) {
      request.fields[key] = value;
    });

    if (files != null) {
      request.files.addAll(files);
    }

    return await request.send();
  }
}
```

---

## 4. Individual Vendor Profiles

**GET** `/api/business/profiles/vendor/individual/`

List individual vendor profiles (vendors only see their own, admins see all).

### Request

```http
GET /api/business/profiles/vendor/individual/ HTTP/1.1
Host: your-domain.com
Authorization: Bearer <access_token>
```

### Response

```json
[
  {
    "id": 1,
    "user_email": "vendor@example.com",
    "owner_name": "John Doe",
    "is_verified": false,
    "vendor_type": "street_vendor",
    "store_name": "John's Street Eats",
    "store_description": "Fresh street food",
    "store_logo": null,
    "categories": [
      {
        "id": 1,
        "name": "Food",
        "slug": "food",
        "description": "Food and beverages",
        "image": null
      }
    ],
    "qr_code": "/media/qrcodes/vendors/individual/vendor_abc123.png",
    "qr_code_identifier": "abc123",
    "id_number": "1234567890123",
    "id_document": "/media/documents/vendors/individual/id/id_doc.pdf",
    "proof_of_address": "/media/documents/vendors/individual/address/address.pdf",
    "selfie_with_id": null,
    "trading_address": "123 Main Street",
    "trading_city": "Johannesburg",
    "trading_province": "Gauteng",
    "trading_postal_code": "2000",
    "bank_name": "Standard Bank",
    "bank_account_number": "123456789",
    "bank_branch_code": "051001",
    "bank_account_holder": "John Doe",
    "verification_status": "pending",
    "rejection_reason": null,
    "verified_at": null,
    "total_sales": 0.0,
    "total_orders": 0,
    "average_rating": 0.0,
    "total_reviews": 0,
    "commission_rate": 8.0,
    "store_active": false,
    "accepts_returns": true,
    "return_window_days": 14,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Dart Code

```dart
Future<List<IndividualVendorProfile>> getIndividualVendorProfiles() async {
  final response = await ApiClient.get('/api/business/profiles/vendor/individual/');
  
  if (response.statusCode == 200) {
    final List<dynamic> data = jsonDecode(response.body);
    return data.map((json) => IndividualVendorProfile.fromJson(json)).toList();
  } else {
    throw Exception('Failed to load individual vendor profiles');
  }
}
```

---

## 5. Business Vendor Profiles

**GET** `/api/business/profiles/vendor/business/`

List business vendor profiles (vendors only see their own, admins see all).

### Request

```http
GET /api/business/profiles/vendor/business/ HTTP/1.1
Host: your-domain.com
Authorization: Bearer <access_token>
```

### Response

```json
[
  {
    "id": 1,
    "user_email": "business@example.com",
    "is_verified": false,
    "is_fully_vetted": false,
    "business_name": "ABC Trading Pty Ltd",
    "business_trading_name": "ABC Traders",
    "business_type": "pty_ltd",
    "business_description": "Wholesale and retail trading",
    "business_logo": null,
    "business_website": "https://abctraders.co.za",
    "categories": [
      {
        "id": 2,
        "name": "Electronics",
        "slug": "electronics",
        "description": "Electronic goods",
        "image": null
      }
    ],
    "qr_code": "/media/qrcodes/vendors/business/vendor_def456.png",
    "qr_code_identifier": "def456",
    "cipc_registration_number": "2024/123456/07",
    "cipc_document": "/media/documents/vendors/business/cipc/cipc.pdf",
    "tax_number": "1234567890",
    "tax_clearance_certificate": null,
    "vat_number": "4123456789",
    "bee_certificate": null,
    "owner_full_name": "Jane Smith",
    "owner_id_number": "9876543210987",
    "owner_id_document": "/media/documents/vendors/business/owner_id/id.pdf",
    "owner_proof_of_address": "/media/documents/vendors/business/owner_address/address.pdf",
    "business_street_address": "456 Business Ave",
    "business_city": "Cape Town",
    "business_province": "Western Cape",
    "business_postal_code": "8000",
    "business_country": "South Africa",
    "bank_name": "First National Bank",
    "bank_account_number": "987654321",
    "bank_branch_code": "250655",
    "bank_account_holder": "ABC Trading Pty Ltd",
    "verification_status": "pending",
    "owner_vetting_passed": false,
    "business_vetting_passed": false,
    "rejection_reason": null,
    "verified_at": null,
    "total_sales": 0.0,
    "total_orders": 0,
    "average_rating": 0.0,
    "total_reviews": 0,
    "commission_rate": 5.0,
    "store_active": false,
    "accepts_returns": true,
    "return_window_days": 30,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Dart Code

```dart
Future<List<BusinessVendorProfile>> getBusinessVendorProfiles() async {
  final response = await ApiClient.get('/api/business/profiles/vendor/business/');
  
  if (response.statusCode == 200) {
    final List<dynamic> data = jsonDecode(response.body);
    return data.map((json) => BusinessVendorProfile.fromJson(json)).toList();
  } else {
    throw Exception('Failed to load business vendor profiles');
  }
}
```

---

## 6. Vetting Applications

**GET** `/api/business/vetting/`

List vetting applications (vendors see their own, admins see all).

### Request

```http
GET /api/business/vetting/ HTTP/1.1
Host: your-domain.com
Authorization: Bearer <access_token>
```

### Response

```json
[
  {
    "id": 1,
    "vetting_type": "individual_owner",
    "status": "pending",
    "id_verified": false,
    "address_verified": false,
    "selfie_verified": false,
    "cipc_verified": false,
    "tax_verified": false,
    "bank_verified": false,
    "rejection_reason": null,
    "submitted_at": "2024-01-01T00:00:00Z",
    "reviewed_at": null,
    "completed_at": null
  }
]
```

### Dart Code

```dart
Future<List<VettingApplication>> getVettingApplications() async {
  final response = await ApiClient.get('/api/business/vetting/');
  
  if (response.statusCode == 200) {
    final List<dynamic> data = jsonDecode(response.body);
    return data.map((json) => VettingApplication.fromJson(json)).toList();
  } else {
    throw Exception('Failed to load vetting applications');
  }
}
```

---

## 7. Vendor Documents

**GET** `/api/business/vendor-documents/`

List vendor documents (admin only).

### Request

```http
GET /api/business/vendor-documents/ HTTP/1.1
Host: your-domain.com
Authorization: Bearer <admin_access_token>
```

### Response

```json
[
  {
    "id": 1,
    "document_type": "id_document",
    "document_file": "/media/documents/vendors/individual/id/id_doc.pdf",
    "document_name": "ID Document",
    "status": "pending",
    "review_notes": null,
    "uploaded_at": "2024-01-01T00:00:00Z"
  }
]
```

### Dart Code

```dart
Future<List<VendorDocument>> getVendorDocuments() async {
  final response = await ApiClient.get('/api/business/vendor-documents/');
  
  if (response.statusCode == 200) {
    final List<dynamic> data = jsonDecode(response.body);
    return data.map((json) => VendorDocument.fromJson(json)).toList();
  } else {
    throw Exception('Failed to load vendor documents');
  }
}
```

---

## 8. Addresses

**GET** `/api/business/addresses/`

List user addresses.

### Request

```http
GET /api/business/addresses/ HTTP/1.1
Host: your-domain.com
Authorization: Bearer <access_token>
```

### Response

```json
[
  {
    "id": 1,
    "address_type": "billing",
    "full_name": "John Doe",
    "phone_number": "+27123456789",
    "street_address": "123 Main Street",
    "apartment_number": "Apt 4B",
    "city": "Johannesburg",
    "state_province": "Gauteng",
    "postal_code": "2000",
    "country": "South Africa",
    "is_default": true,
    "delivery_instructions": "Ring doorbell twice",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

### Dart Code

```dart
Future<List<Address>> getAddresses() async {
  final response = await ApiClient.get('/api/business/addresses/');
  
  if (response.statusCode == 200) {
    final List<dynamic> data = jsonDecode(response.body);
    return data.map((json) => Address.fromJson(json)).toList();
  } else {
    throw Exception('Failed to load addresses');
  }
}
```

---

## 9. Business Followers

**GET** `/api/business/followers/my-following/`

List businesses the current user follows.

### Request

```http
GET /api/business/followers/my-following/ HTTP/1.1
Host: your-domain.com
Authorization: Bearer <access_token>
```

### Response

```json
[
  {
    "id": 1,
    "user": 1,
    "user_email": "customer@example.com",
    "vendor": 2,
    "vendor_email": "vendor@example.com",
    "vendor_name": "John's Street Eats",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### Dart Code

```dart
Future<List<BusinessFollower>> getMyFollowing() async {
  final response = await ApiClient.get('/api/business/followers/my-following/');
  
  if (response.statusCode == 200) {
    final List<dynamic> data = jsonDecode(response.body);
    return data.map((json) => BusinessFollower.fromJson(json)).toList();
  } else {
    throw Exception('Failed to load following list');
  }
}
```

---

## 10. Store Discovery

**GET** `/api/business/discover-stores/`

Discover stores based on location and user interests.

### Query Parameters

- `latitude`: Override user's stored latitude
- `longitude`: Override user's stored longitude

### Request

```http
GET /api/business/discover-stores/?latitude=-26.2041&longitude=28.0473 HTTP/1.1
Host: your-domain.com
Authorization: Bearer <access_token>
```

### Response

```json
{
  "nearby": {
    "type": "nearby",
    "stores": [
      {
        "vendor_id": 1,
        "vendor_type": "individual",
        "store_name": "John's Street Eats",
        "store_description": "Fresh street food",
        "store_logo": null,
        "distance_km": 2.5,
        "relevance_score": null,
        "categories": ["Food"],
        "average_rating": 4.2,
        "total_reviews": 15,
        "is_following": true
      }
    ]
  },
  "recommended": {
    "type": "recommended",
    "stores": [
      {
        "vendor_id": 2,
        "vendor_type": "business",
        "store_name": "ABC Traders",
        "store_description": "Wholesale electronics",
        "store_logo": "/media/logos/vendors/business/logo.png",
        "distance_km": 15.3,
        "relevance_score": 0.85,
        "categories": ["Electronics"],
        "average_rating": 4.8,
        "total_reviews": 42,
        "is_following": false
      }
    ]
  }
}
```

### Dart Code

```dart
Future<Map<String, StoreDiscoveryResult>> discoverStores({
  double? latitude,
  double? longitude,
}) async {
  final queryParams = <String, String>{};
  if (latitude != null) queryParams['latitude'] = latitude.toString();
  if (longitude != null) queryParams['longitude'] = longitude.toString();
  
  final queryString = queryParams.isNotEmpty 
    ? '?${queryParams.entries.map((e) => '${e.key}=${e.value}').join('&')}' 
    : '';
    
  final response = await ApiClient.get('/api/business/discover-stores/$queryString');
  
  if (response.statusCode == 200) {
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return {
      'nearby': StoreDiscoveryResult.fromJson(data['nearby']),
      'recommended': StoreDiscoveryResult.fromJson(data['recommended']),
    };
  } else {
    throw Exception('Failed to discover stores');
  }
}
```

---

## 11. Complete BusinessService Class

```dart
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class BusinessService {
  static const String baseUrl = 'https://your-domain.com'; // Replace with your server

  // Get authorization headers
  static Future<Map<String, String>> _getHeaders() async {
    // Assuming you have a token storage mechanism
    final token = await _getToken();
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  // Placeholder - implement token retrieval
  static Future<String> _getToken() async {
    // Implement your token retrieval logic
    throw UnimplementedError('Implement token retrieval');
  }

  /// Individual Vendor Profiles

  static Future<List<IndividualVendorProfile>> getIndividualVendorProfiles() async {
    final url = Uri.parse('$baseUrl/api/business/profiles/vendor/individual/');
    final headers = await _getHeaders();
    final response = await http.get(url, headers: headers);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => IndividualVendorProfile.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load individual vendor profiles: ${response.statusCode}');
    }
  }

  static Future<IndividualVendorProfile> createIndividualVendorProfile(
    Map<String, dynamic> profileData,
  ) async {
    final url = Uri.parse('$baseUrl/api/business/profiles/vendor/individual/');
    final headers = await _getHeaders();
    final body = jsonEncode(profileData);
    final response = await http.post(url, headers: headers, body: body);

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body);
      return IndividualVendorProfile.fromJson(data);
    } else {
      final error = jsonDecode(response.body);
      throw Exception('Failed to create individual vendor profile: ${error['error'] ?? response.statusCode}');
    }
  }

  static Future<IndividualVendorProfile> getIndividualVendorProfile(int id) async {
    final url = Uri.parse('$baseUrl/api/business/profiles/vendor/individual/$id/');
    final headers = await _getHeaders();
    final response = await http.get(url, headers: headers);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return IndividualVendorProfile.fromJson(data);
    } else {
      throw Exception('Failed to load individual vendor profile: ${response.statusCode}');
    }
  }

  static Future<IndividualVendorProfile> updateIndividualVendorProfile(
    int id,
    Map<String, dynamic> profileData,
  ) async {
    final url = Uri.parse('$baseUrl/api/business/profiles/vendor/individual/$id/');
    final headers = await _getHeaders();
    final body = jsonEncode(profileData);
    final response = await http.put(url, headers: headers, body: body);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return IndividualVendorProfile.fromJson(data);
    } else {
      final error = jsonDecode(response.body);
      throw Exception('Failed to update individual vendor profile: ${error['error'] ?? response.statusCode}');
    }
  }

  static Future<List<VettingApplication>> getIndividualVendorVettingStatus(int vendorId) async {
    final url = Uri.parse('$baseUrl/api/business/profiles/vendor/individual/$vendorId/vetting-status/');
    final headers = await _getHeaders();
    final response = await http.get(url, headers: headers);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => VettingApplication.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load vetting status: ${response.statusCode}');
    }
  }

  static Future<List<VendorDocument>> getIndividualVendorDocuments(int vendorId) async {
    final url = Uri.parse('$baseUrl/api/business/profiles/vendor/individual/$vendorId/documents/');
    final headers = await _getHeaders();
    final response = await http.get(url, headers: headers);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => VendorDocument.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load vendor documents: ${response.statusCode}');
    }
  }

  /// Business Vendor Profiles

  static Future<List<BusinessVendorProfile>> getBusinessVendorProfiles() async {
    final url = Uri.parse('$baseUrl/api/business/profiles/vendor/business/');
    final headers = await _getHeaders();
    final response = await http.get(url, headers: headers);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => BusinessVendorProfile.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load business vendor profiles: ${response.statusCode}');
    }
  }

  static Future<BusinessVendorProfile> createBusinessVendorProfile(
    Map<String, dynamic> profileData,
  ) async {
    final url = Uri.parse('$baseUrl/api/business/profiles/vendor/business/');
    final headers = await _getHeaders();
    final body = jsonEncode(profileData);
    final response = await http.post(url, headers: headers, body: body);

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body);
      return BusinessVendorProfile.fromJson(data);
    } else {
      final error = jsonDecode(response.body);
      throw Exception('Failed to create business vendor profile: ${error['error'] ?? response.statusCode}');
    }
  }

  /// Addresses

  static Future<List<Address>> getAddresses() async {
    final url = Uri.parse('$baseUrl/api/business/addresses/');
    final headers = await _getHeaders();
    final response = await http.get(url, headers: headers);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => Address.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load addresses: ${response.statusCode}');
    }
  }

  static Future<Address> createAddress(Map<String, dynamic> addressData) async {
    final url = Uri.parse('$baseUrl/api/business/addresses/');
    final headers = await _getHeaders();
    final body = jsonEncode(addressData);
    final response = await http.post(url, headers: headers, body: body);

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body);
      return Address.fromJson(data);
    } else {
      final error = jsonDecode(response.body);
      throw Exception('Failed to create address: ${error['error'] ?? response.statusCode}');
    }
  }

  static Future<Address> updateAddress(int id, Map<String, dynamic> addressData) async {
    final url = Uri.parse('$baseUrl/api/business/addresses/$id/');
    final headers = await _getHeaders();
    final body = jsonEncode(addressData);
    final response = await http.put(url, headers: headers, body: body);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return Address.fromJson(data);
    } else {
      final error = jsonDecode(response.body);
      throw Exception('Failed to update address: ${error['error'] ?? response.statusCode}');
    }
  }

  static Future<void> deleteAddress(int id) async {
    final url = Uri.parse('$baseUrl/api/business/addresses/$id/');
    final headers = await _getHeaders();
    final response = await http.delete(url, headers: headers);

    if (response.statusCode != 204) {
      throw Exception('Failed to delete address: ${response.statusCode}');
    }
  }

  static Future<Address> setDefaultAddress(int id) async {
    final url = Uri.parse('$baseUrl/api/business/addresses/$id/set-default/');
    final headers = await _getHeaders();
    final response = await http.post(url, headers: headers);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return Address.fromJson(data);
    } else {
      throw Exception('Failed to set default address: ${response.statusCode}');
    }
  }

  /// Business Followers

  static Future<List<BusinessFollower>> getMyFollowing() async {
    final url = Uri.parse('$baseUrl/api/business/followers/my-following/');
    final headers = await _getHeaders();
    final response = await http.get(url, headers: headers);

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => BusinessFollower.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load following list: ${response.statusCode}');
    }
  }

  static Future<BusinessFollower> followBusiness(int vendorId) async {
    final url = Uri.parse('$baseUrl/api/business/followers/follow/');
    final headers = await _getHeaders();
    final body = jsonEncode({'vendor_id': vendorId});
    final response = await http.post(url, headers: headers, body: body);

    if (response.statusCode == 201) {
      final data = jsonDecode(response.body);
      return BusinessFollower.fromJson(data);
    } else {
      final error = jsonDecode(response.body);
      throw Exception('Failed to follow business: ${error['error'] ?? response.statusCode}');
    }
  }

  static Future<void> unfollowBusiness(int vendorId) async {
    final url = Uri.parse('$baseUrl/api/business/followers/unfollow/');
    final headers = await _getHeaders();
    final body = jsonEncode({'vendor_id': vendorId});
    final response = await http.post(url, headers: headers, body: body);

    if (response.statusCode != 200) {
      final error = jsonDecode(response.body);
      throw Exception('Failed to unfollow business: ${error['error'] ?? response.statusCode}');
    }
  }

  static Future<Map<String, int>> getVendorFollowers(int vendorId) async {
    final url = Uri.parse('$baseUrl/api/business/followers/followers/$vendorId/');
    final response = await http.get(url);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return {
        'follower_count': data['follower_count'] as int,
        'is_following': data['is_following'] as bool ? 1 : 0,
      };
    } else {
      throw Exception('Failed to get vendor followers: ${response.statusCode}');
    }
  }

  /// Store Discovery

  static Future<Map<String, StoreDiscoveryResult>> discoverStores({
    double? latitude,
    double? longitude,
  }) async {
    final queryParams = <String>[];
    if (latitude != null) queryParams.add('latitude=$latitude');
    if (longitude != null) queryParams.add('longitude=$longitude');
    
    final queryString = queryParams.isNotEmpty ? '?${queryParams.join('&')}' : '';
    final url = Uri.parse('$baseUrl/api/business/discover-stores/$queryString');
    final headers = await _getHeaders();
    final response = await http.get(url, headers: headers);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return {
        'nearby': StoreDiscoveryResult.fromJson(data['nearby']),
        'recommended': StoreDiscoveryResult.fromJson(data['recommended']),
      };
    } else {
      throw Exception('Failed to discover stores: ${response.statusCode}');
    }
  }
}
```

---

## 12. Error Handling

### Common Error Responses

#### Authentication Errors

```json
{
  "detail": "Authentication credentials were not provided."
}
```

#### Permission Errors

```json
{
  "detail": "You do not have permission to perform this action."
}
```

#### Validation Errors

```json
{
  "vendor_type": ["This field is required."],
  "store_name": ["This field may not be blank."]
}
```

```json
{
  "error": "Only users with vendor account type can create a vendor profile."
}
```

```json
{
  "error": "You already have an individual vendor profile. A user can only have one vendor profile."
}
```

#### File Upload Errors

```json
{
  "id_document": ["The submitted file is empty."]
}
```

#### Follow Errors

```json
{
  "error": "Vendor not found."
}
```

```json
{
  "error": "You are already following this business."
}
```

```json
{
  "error": "You cannot follow yourself."
}
```

### Dart Error Handling

```dart
try {
  final profile = await BusinessService.createIndividualVendorProfile(profileData);
  // Handle success
} catch (e) {
  if (e.toString().contains('already have an individual vendor profile')) {
    // Handle existing profile
  } else if (e.toString().contains('Only users with vendor account type')) {
    // Handle wrong user type
  } else {
    // Handle other errors
  }
}
```

---

## 13. Best Practices

### 1. File Upload Handling

- Validate file types and sizes before upload
- Show upload progress for large files
- Handle network interruptions gracefully
- Compress images before upload

### 2. Form Validation

- Validate required fields on the client side
- Provide clear error messages
- Use appropriate input types (email, phone, etc.)
- Validate file formats for documents

### 3. State Management

- Cache vendor profiles locally
- Update UI immediately after successful operations
- Handle offline scenarios
- Sync data when connection is restored

### 4. User Experience

- Show loading states during API calls
- Provide feedback for long operations (vetting, uploads)
- Display verification status prominently
- Guide users through the vetting process

### 5. Security

- Never store sensitive documents locally
- Use HTTPS for all API calls
- Validate file uploads on the server
- Handle authentication errors gracefully

### 6. Performance

- Paginate large lists
- Lazy load images
- Cache frequently accessed data
- Minimize API calls

### Example Usage

```dart
class VendorProfileManager {
  IndividualVendorProfile? _individualProfile;
  BusinessVendorProfile? _businessProfile;
  List<Address> _addresses = [];
  List<BusinessFollower> _following = [];

  Future<void> loadData() async {
    try {
      // Load vendor profiles
      final individualProfiles = await BusinessService.getIndividualVendorProfiles();
      if (individualProfiles.isNotEmpty) {
        _individualProfile = individualProfiles.first;
      }

      final businessProfiles = await BusinessService.getBusinessVendorProfiles();
      if (businessProfiles.isNotEmpty) {
        _businessProfile = businessProfiles.first;
      }

      // Load addresses
      _addresses = await BusinessService.getAddresses();

      // Load following
      _following = await BusinessService.getMyFollowing();
    } catch (e) {
      // Handle error
    }
  }

  Future<void> createIndividualProfile(Map<String, dynamic> data) async {
    try {
      _individualProfile = await BusinessService.createIndividualVendorProfile(data);
      // Update UI
    } catch (e) {
      // Handle error
    }
  }

  Future<void> followBusiness(int vendorId) async {
    try {
      final follower = await BusinessService.followBusiness(vendorId);
      _following.add(follower);
      // Update UI
    } catch (e) {
      // Handle error
    }
  }

  bool get hasVendorProfile => _individualProfile != null || _businessProfile != null;
  bool get isVerified => _individualProfile?.isVerified == true || _businessProfile?.isVerified == true;
}
```</content>
<parameter name="filePath">c:\Users\linda\Documents\sanoa\backend\docs\SANOA_BUSINESS_API.md