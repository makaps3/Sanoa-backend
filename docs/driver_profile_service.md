# Driver Profile Service — Flutter

Base URL: `/api/delivery/driver/`

All endpoints require `Authorization: Bearer <token>` and `user_type = 'driver'`.
File/image uploads use `multipart/form-data`.

---

## Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/delivery/driver/profile/` | Create driver profile |
| `GET` | `/api/delivery/driver/profile/` | Get own driver profile |
| `PUT` | `/api/delivery/driver/profile/` | Full update |
| `PATCH` | `/api/delivery/driver/profile/` | Partial update (only send changed fields) |

---

## Field Reference

### Create / Update fields

#### Personal Info
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `profile_photo` | File (image) | No | Clear face photo |
| `date_of_birth` | Date `YYYY-MM-DD` | No | For eligibility verification |
| `gender` | String | No | `male` \| `female` \| `other` \| `prefer_not_to_say` |
| `national_id_document` | File | No | National ID or passport scan |
| `residential_address` | String | No | Driver home address |
| `emergency_contact_name` | String | No | |
| `emergency_contact_phone` | String | No | |

#### Vehicle Info
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `vehicle_type` | String | No | `bicycle` \| `motorbike` \| `car` \| `van` \| `truck` |
| `vehicle_brand` | String | No | e.g. Toyota |
| `vehicle_model` | String | No | e.g. Hilux |
| `vehicle_registration` | String | No | License plate |
| `vehicle_color` | String | No | |
| `vehicle_photo_front` | File (image) | No | |
| `vehicle_photo_side` | File (image) | No | |
| `vehicle_photo_rear` | File (image) | No | |
| `insurance_document` | File | No | |
| `vehicle_license_expiry` | Date `YYYY-MM-DD` | No | |

#### Verification Docs
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `driver_license_document` | File | No | |
| `license_number` | String | No | |
| `license_expiry_date` | Date `YYYY-MM-DD` | No | |
| `terms_accepted` | Boolean | **Yes (create only)** | Must be `true` |

### Read-only fields (returned in GET, never sent by client)

| Field | Type | Notes |
|-------|------|-------|
| `id` | Integer | |
| `user` | Integer | User ID |
| `user_email` | String | |
| `full_name` | String | From `first_name + last_name` on User |
| `background_check_status` | String | `pending` \| `approved` \| `rejected` — set by admin |
| `identity_verification_status` | String | `pending` \| `approved` \| `rejected` — set by admin |
| `training_completed` | Boolean | Set by admin |
| `terms_accepted_at` | DateTime | Auto-set on create |
| `is_available` | Boolean | Controlled by shift system |
| `current_latitude` | Decimal | Updated by GPS system |
| `current_longitude` | Decimal | Updated by GPS system |
| `total_deliveries` | Integer | System-computed |
| `average_rating` | Decimal | System-computed |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

---

## Example Response — GET

```json
{
  "id": 1,
  "user": 42,
  "user_email": "driver@example.com",
  "full_name": "Sipho Nkosi",
  "profile_photo": "https://cdn.sanoa.co.za/media/drivers/photos/sipho.jpg",
  "date_of_birth": "1995-06-15",
  "gender": "male",
  "national_id_document": "https://cdn.sanoa.co.za/media/drivers/id_docs/id.pdf",
  "residential_address": "45 Bree Street, Johannesburg, 2001",
  "emergency_contact_name": "Thandi Nkosi",
  "emergency_contact_phone": "+27821234567",
  "vehicle_type": "motorbike",
  "vehicle_brand": "Honda",
  "vehicle_model": "CB125F",
  "vehicle_registration": "GP 123-456",
  "vehicle_color": "Red",
  "vehicle_photo_front": "https://cdn.sanoa.co.za/media/drivers/vehicles/front.jpg",
  "vehicle_photo_side": "https://cdn.sanoa.co.za/media/drivers/vehicles/side.jpg",
  "vehicle_photo_rear": "https://cdn.sanoa.co.za/media/drivers/vehicles/rear.jpg",
  "insurance_document": "https://cdn.sanoa.co.za/media/drivers/insurance/policy.pdf",
  "vehicle_license_expiry": "2027-03-31",
  "driver_license_document": "https://cdn.sanoa.co.za/media/drivers/licenses/license.pdf",
  "license_number": "DL-9876543",
  "license_expiry_date": "2028-01-15",
  "background_check_status": "approved",
  "identity_verification_status": "approved",
  "training_completed": true,
  "terms_accepted": true,
  "terms_accepted_at": "2026-05-17T10:00:00Z",
  "is_available": false,
  "current_latitude": null,
  "current_longitude": null,
  "total_deliveries": 127,
  "average_rating": "4.85",
  "created_at": "2026-05-17T10:00:00Z",
  "updated_at": "2026-05-17T12:00:00Z"
}
```

---

## Error Responses

| HTTP Status | Body | Meaning |
|-------------|------|---------|
| `401 Unauthorized` | `{"detail": "Authentication credentials were not provided."}` | Missing or invalid JWT |
| `403 Forbidden` | `{"error": "Only drivers can access this endpoint."}` | `user_type` is not `driver` |
| `404 Not Found` | `{"detail": "Driver profile not found. Create one first."}` | GET/PUT/PATCH before profile exists |
| `400 Bad Request` | `{"terms_accepted": ["You must accept the terms and conditions."]}` | Create without accepting terms |
| `400 Bad Request` | `{"non_field_errors": ["You already have a driver profile."]}` | POST when profile already exists |

---

## Flutter Models

```dart
class DriverProfile {
  final int id;
  final int user;
  final String userEmail;
  final String fullName;

  // Personal info
  final String? profilePhoto;
  final String? dateOfBirth;
  final String? gender;
  final String? nationalIdDocument;
  final String residentialAddress;
  final String emergencyContactName;
  final String emergencyContactPhone;

  // Vehicle
  final String vehicleType;
  final String vehicleBrand;
  final String vehicleModel;
  final String vehicleRegistration;
  final String vehicleColor;
  final String? vehiclePhotoFront;
  final String? vehiclePhotoSide;
  final String? vehiclePhotoRear;
  final String? insuranceDocument;
  final String? vehicleLicenseExpiry;

  // Verification
  final String? driverLicenseDocument;
  final String licenseNumber;
  final String? licenseExpiryDate;
  final String backgroundCheckStatus;
  final String identityVerificationStatus;
  final bool trainingCompleted;
  final bool termsAccepted;
  final String? termsAcceptedAt;

  // Operational (read-only)
  final bool isAvailable;
  final double? currentLatitude;
  final double? currentLongitude;
  final int totalDeliveries;
  final double averageRating;
  final String createdAt;
  final String updatedAt;

  DriverProfile({
    required this.id,
    required this.user,
    required this.userEmail,
    required this.fullName,
    this.profilePhoto,
    this.dateOfBirth,
    this.gender,
    this.nationalIdDocument,
    this.residentialAddress = '',
    this.emergencyContactName = '',
    this.emergencyContactPhone = '',
    this.vehicleType = 'motorbike',
    this.vehicleBrand = '',
    this.vehicleModel = '',
    this.vehicleRegistration = '',
    this.vehicleColor = '',
    this.vehiclePhotoFront,
    this.vehiclePhotoSide,
    this.vehiclePhotoRear,
    this.insuranceDocument,
    this.vehicleLicenseExpiry,
    this.driverLicenseDocument,
    this.licenseNumber = '',
    this.licenseExpiryDate,
    this.backgroundCheckStatus = 'pending',
    this.identityVerificationStatus = 'pending',
    this.trainingCompleted = false,
    this.termsAccepted = false,
    this.termsAcceptedAt,
    this.isAvailable = false,
    this.currentLatitude,
    this.currentLongitude,
    this.totalDeliveries = 0,
    this.averageRating = 0.0,
    required this.createdAt,
    required this.updatedAt,
  });

  factory DriverProfile.fromJson(Map<String, dynamic> json) {
    return DriverProfile(
      id: json['id'] as int,
      user: json['user'] as int,
      userEmail: json['user_email'] as String,
      fullName: json['full_name'] as String? ?? '',
      profilePhoto: json['profile_photo'] as String?,
      dateOfBirth: json['date_of_birth'] as String?,
      gender: json['gender'] as String?,
      nationalIdDocument: json['national_id_document'] as String?,
      residentialAddress: json['residential_address'] as String? ?? '',
      emergencyContactName: json['emergency_contact_name'] as String? ?? '',
      emergencyContactPhone: json['emergency_contact_phone'] as String? ?? '',
      vehicleType: json['vehicle_type'] as String? ?? 'motorbike',
      vehicleBrand: json['vehicle_brand'] as String? ?? '',
      vehicleModel: json['vehicle_model'] as String? ?? '',
      vehicleRegistration: json['vehicle_registration'] as String? ?? '',
      vehicleColor: json['vehicle_color'] as String? ?? '',
      vehiclePhotoFront: json['vehicle_photo_front'] as String?,
      vehiclePhotoSide: json['vehicle_photo_side'] as String?,
      vehiclePhotoRear: json['vehicle_photo_rear'] as String?,
      insuranceDocument: json['insurance_document'] as String?,
      vehicleLicenseExpiry: json['vehicle_license_expiry'] as String?,
      driverLicenseDocument: json['driver_license_document'] as String?,
      licenseNumber: json['license_number'] as String? ?? '',
      licenseExpiryDate: json['license_expiry_date'] as String?,
      backgroundCheckStatus: json['background_check_status'] as String? ?? 'pending',
      identityVerificationStatus: json['identity_verification_status'] as String? ?? 'pending',
      trainingCompleted: json['training_completed'] as bool? ?? false,
      termsAccepted: json['terms_accepted'] as bool? ?? false,
      termsAcceptedAt: json['terms_accepted_at'] as String?,
      isAvailable: json['is_available'] as bool? ?? false,
      currentLatitude: json['current_latitude'] != null
          ? double.tryParse(json['current_latitude'].toString())
          : null,
      currentLongitude: json['current_longitude'] != null
          ? double.tryParse(json['current_longitude'].toString())
          : null,
      totalDeliveries: json['total_deliveries'] as int? ?? 0,
      averageRating: double.tryParse(json['average_rating'].toString()) ?? 0.0,
      createdAt: json['created_at'] as String,
      updatedAt: json['updated_at'] as String,
    );
  }
}
```

---

## Flutter Service

```dart
import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;

class DriverProfileService {
  static const String _base = 'https://api.sanoa.co.za';

  final String token;

  DriverProfileService({required this.token});

  Map<String, String> get _headers => {
        'Authorization': 'Bearer $token',
      };

  // ── Helpers ───────────────────────────────────────────────────

  /// Builds a multipart request and attaches text fields + optional files.
  Future<http.StreamedResponse> _multipart(
    String method,
    String path,
    Map<String, String> fields, {
    Map<String, File?> files = const {},
  }) async {
    final uri = Uri.parse('$_base$path');
    final request = http.MultipartRequest(method, uri)
      ..headers.addAll(_headers)
      ..fields.addAll(fields);

    for (final entry in files.entries) {
      if (entry.value != null) {
        request.files.add(await http.MultipartFile.fromPath(
          entry.key,
          entry.value!.path,
        ));
      }
    }
    return request.send();
  }

  Future<Map<String, dynamic>> _parseResponse(http.StreamedResponse streamed) async {
    final body = await streamed.stream.bytesToString();
    return jsonDecode(body) as Map<String, dynamic>;
  }

  // ── Profile ───────────────────────────────────────────────────

  /// GET /api/delivery/driver/profile/
  Future<DriverProfile> getProfile() async {
    final uri = Uri.parse('$_base/api/delivery/driver/profile/');
    final response = await http.get(uri, headers: _headers);
    if (response.statusCode == 200) {
      return DriverProfile.fromJson(jsonDecode(response.body));
    }
    throw Exception(jsonDecode(response.body)['detail'] ?? 'Failed to fetch profile');
  }

  /// POST /api/delivery/driver/profile/
  /// [termsAccepted] must be true or the request will fail.
  Future<DriverProfile> createProfile({
    File? profilePhoto,
    String? dateOfBirth,
    String? gender,
    File? nationalIdDocument,
    String residentialAddress = '',
    String emergencyContactName = '',
    String emergencyContactPhone = '',
    String vehicleType = 'motorbike',
    String vehicleBrand = '',
    String vehicleModel = '',
    String vehicleRegistration = '',
    String vehicleColor = '',
    File? vehiclePhotoFront,
    File? vehiclePhotoSide,
    File? vehiclePhotoRear,
    File? insuranceDocument,
    String? vehicleLicenseExpiry,
    File? driverLicenseDocument,
    String licenseNumber = '',
    String? licenseExpiryDate,
    required bool termsAccepted,
  }) async {
    final fields = <String, String>{
      'terms_accepted': termsAccepted.toString(),
      if (dateOfBirth != null) 'date_of_birth': dateOfBirth,
      if (gender != null) 'gender': gender,
      if (residentialAddress.isNotEmpty) 'residential_address': residentialAddress,
      if (emergencyContactName.isNotEmpty) 'emergency_contact_name': emergencyContactName,
      if (emergencyContactPhone.isNotEmpty) 'emergency_contact_phone': emergencyContactPhone,
      if (vehicleType.isNotEmpty) 'vehicle_type': vehicleType,
      if (vehicleBrand.isNotEmpty) 'vehicle_brand': vehicleBrand,
      if (vehicleModel.isNotEmpty) 'vehicle_model': vehicleModel,
      if (vehicleRegistration.isNotEmpty) 'vehicle_registration': vehicleRegistration,
      if (vehicleColor.isNotEmpty) 'vehicle_color': vehicleColor,
      if (vehicleLicenseExpiry != null) 'vehicle_license_expiry': vehicleLicenseExpiry,
      if (licenseNumber.isNotEmpty) 'license_number': licenseNumber,
      if (licenseExpiryDate != null) 'license_expiry_date': licenseExpiryDate,
    };

    final files = <String, File?>{
      'profile_photo': profilePhoto,
      'national_id_document': nationalIdDocument,
      'vehicle_photo_front': vehiclePhotoFront,
      'vehicle_photo_side': vehiclePhotoSide,
      'vehicle_photo_rear': vehiclePhotoRear,
      'insurance_document': insuranceDocument,
      'driver_license_document': driverLicenseDocument,
    };

    final streamed = await _multipart('POST', '/api/delivery/driver/profile/', fields, files: files);
    final data = await _parseResponse(streamed);

    if (streamed.statusCode == 201) {
      return DriverProfile.fromJson(data);
    }
    throw Exception(data['detail'] ?? data['non_field_errors']?.first ?? 'Failed to create profile');
  }

  /// PATCH /api/delivery/driver/profile/
  /// Only include fields you want to change — omitted fields are unchanged.
  Future<DriverProfile> updateProfile({
    File? profilePhoto,
    String? dateOfBirth,
    String? gender,
    File? nationalIdDocument,
    String? residentialAddress,
    String? emergencyContactName,
    String? emergencyContactPhone,
    String? vehicleType,
    String? vehicleBrand,
    String? vehicleModel,
    String? vehicleRegistration,
    String? vehicleColor,
    File? vehiclePhotoFront,
    File? vehiclePhotoSide,
    File? vehiclePhotoRear,
    File? insuranceDocument,
    String? vehicleLicenseExpiry,
    File? driverLicenseDocument,
    String? licenseNumber,
    String? licenseExpiryDate,
  }) async {
    final fields = <String, String>{
      if (dateOfBirth != null) 'date_of_birth': dateOfBirth,
      if (gender != null) 'gender': gender,
      if (residentialAddress != null) 'residential_address': residentialAddress,
      if (emergencyContactName != null) 'emergency_contact_name': emergencyContactName,
      if (emergencyContactPhone != null) 'emergency_contact_phone': emergencyContactPhone,
      if (vehicleType != null) 'vehicle_type': vehicleType,
      if (vehicleBrand != null) 'vehicle_brand': vehicleBrand,
      if (vehicleModel != null) 'vehicle_model': vehicleModel,
      if (vehicleRegistration != null) 'vehicle_registration': vehicleRegistration,
      if (vehicleColor != null) 'vehicle_color': vehicleColor,
      if (vehicleLicenseExpiry != null) 'vehicle_license_expiry': vehicleLicenseExpiry,
      if (licenseNumber != null) 'license_number': licenseNumber,
      if (licenseExpiryDate != null) 'license_expiry_date': licenseExpiryDate,
    };

    final files = <String, File?>{
      'profile_photo': profilePhoto,
      'national_id_document': nationalIdDocument,
      'vehicle_photo_front': vehiclePhotoFront,
      'vehicle_photo_side': vehiclePhotoSide,
      'vehicle_photo_rear': vehiclePhotoRear,
      'insurance_document': insuranceDocument,
      'driver_license_document': driverLicenseDocument,
    };

    final streamed = await _multipart('PATCH', '/api/delivery/driver/profile/', fields, files: files);
    final data = await _parseResponse(streamed);

    if (streamed.statusCode == 200) {
      return DriverProfile.fromJson(data);
    }
    throw Exception(data['detail'] ?? 'Failed to update profile');
  }
}
```

---

## Usage Examples

```dart
final service = DriverProfileService(token: authToken);

// Check if profile exists
DriverProfile? profile;
try {
  profile = await service.getProfile();
} catch (_) {
  profile = null;
}

// Create profile on first login
if (profile == null) {
  profile = await service.createProfile(
    vehicleType: 'motorbike',
    vehicleBrand: 'Honda',
    vehicleModel: 'CB125F',
    vehicleRegistration: 'GP 123-456',
    residentialAddress: '45 Bree Street, Johannesburg',
    emergencyContactName: 'Thandi Nkosi',
    emergencyContactPhone: '+27821234567',
    licenseNumber: 'DL-9876543',
    licenseExpiryDate: '2028-01-15',
    driverLicenseDocument: File('/path/to/license.pdf'),
    profilePhoto: File('/path/to/photo.jpg'),
    termsAccepted: true,
  );
}

// Update vehicle details later
profile = await service.updateProfile(
  vehicleColor: 'Blue',
  vehicleLicenseExpiry: '2027-03-31',
  insuranceDocument: File('/path/to/insurance.pdf'),
);
```

---

## Verification Status Values

These fields are **read-only** — set by admin after document review:

| Field | Values |
|-------|--------|
| `background_check_status` | `pending` → `approved` \| `rejected` |
| `identity_verification_status` | `pending` → `approved` \| `rejected` |
| `training_completed` | `false` → `true` (after safety onboarding) |
