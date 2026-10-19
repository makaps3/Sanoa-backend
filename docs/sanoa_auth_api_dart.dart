// ignore_for_file: avoid_print
/// Sanoa Authentication API - Complete Documentation
///
/// Covers all three user types: Customer, Individual Vendor, Business Vendor
/// Includes Dart models, complete request/response bodies, and HTTP examples.
///
/// Prerequisites:
///   dart pub add pdf http
///
/// Run:
///   dart run docs/sanoa_auth_api_dart.dart

import 'dart:io';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

// ═══════════════════════════════════════════════════════════════════════
// Table helper functions
// ═══════════════════════════════════════════════════════════════════════

pw.TableRow _tableRow(String method, String endpoint, String description) {
  return pw.TableRow(children: [
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(method, style: const pw.TextStyle(fontSize: 9))),
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(endpoint, style: pw.TextStyle(fontSize: 8, font: pw.Font.courier()))),
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(description, style: const pw.TextStyle(fontSize: 9))),
  ]);
}

pw.TableRow _fieldHeader() {
  return pw.TableRow(
    decoration: const pw.BoxDecoration(color: PdfColors.blueGrey50),
    children: [
      pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Field', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
      pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Type', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
      pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Required', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
      pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Description', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
    ],
  );
}

pw.TableRow _fieldRow(String field, String type, String required, String desc) {
  return pw.TableRow(children: [
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(field, style: pw.TextStyle(fontSize: 8, font: pw.Font.courier()))),
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(type, style: const pw.TextStyle(fontSize: 8))),
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(required, style: const pw.TextStyle(fontSize: 8))),
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(desc, style: const pw.TextStyle(fontSize: 8))),
  ]);
}

pw.TableRow _errorRow(String code, String meaning, String when) {
  return pw.TableRow(children: [
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(code, style: pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold))),
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(meaning, style: const pw.TextStyle(fontSize: 9))),
    pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text(when, style: const pw.TextStyle(fontSize: 9))),
  ]);
}

// ═══════════════════════════════════════════════════════════════════════
// Styles
// ═══════════════════════════════════════════════════════════════════════

final _titleStyle = pw.TextStyle(fontSize: 26, fontWeight: pw.FontWeight.bold, color: PdfColors.blueGrey900);
final _h1Style = pw.TextStyle(fontSize: 18, fontWeight: pw.FontWeight.bold, color: PdfColors.blueGrey800);
final _h2Style = pw.TextStyle(fontSize: 14, fontWeight: pw.FontWeight.bold, color: PdfColors.blueGrey700);
const _bodyStyle = pw.TextStyle(fontSize: 10);
final _codeStyle = pw.TextStyle(fontSize: 8, font: pw.Font.courier(), color: PdfColors.grey800);
final _labelStyle = pw.TextStyle(fontSize: 10, fontWeight: pw.FontWeight.bold, color: PdfColors.blue800);
final _noteStyle = pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold, color: PdfColors.orange900);

pw.Widget _section(String text) => pw.Padding(
      padding: const pw.EdgeInsets.only(top: 14, bottom: 5),
      child: pw.Text(text, style: _h1Style),
    );

pw.Widget _sub(String text) => pw.Padding(
      padding: const pw.EdgeInsets.only(top: 8, bottom: 3),
      child: pw.Text(text, style: _h2Style),
    );

pw.Widget _label(String text) => pw.Padding(
      padding: const pw.EdgeInsets.only(top: 5, bottom: 2),
      child: pw.Text(text, style: _labelStyle),
    );

pw.Widget _body(String text) => pw.Padding(
      padding: const pw.EdgeInsets.only(bottom: 3),
      child: pw.Text(text, style: _bodyStyle),
    );

pw.Widget _note(String text) => pw.Container(
      padding: const pw.EdgeInsets.all(7),
      margin: const pw.EdgeInsets.only(top: 3, bottom: 7),
      decoration: pw.BoxDecoration(
        color: PdfColors.amber50,
        border: pw.Border.all(color: PdfColors.orange300),
        borderRadius: pw.BorderRadius.circular(3),
      ),
      child: pw.Text(text, style: _noteStyle),
    );

pw.Widget _code(String code) => pw.Container(
      width: double.infinity,
      padding: const pw.EdgeInsets.all(8),
      margin: const pw.EdgeInsets.only(top: 3, bottom: 6),
      decoration: pw.BoxDecoration(
        color: PdfColors.grey100,
        border: pw.Border.all(color: PdfColors.grey400),
        borderRadius: pw.BorderRadius.circular(3),
      ),
      child: pw.Text(code, style: _codeStyle),
    );

pw.Widget _divider() => pw.Divider(color: PdfColors.grey300, thickness: 0.5);

pw.Widget _fieldTable(List<pw.TableRow> rows) => pw.Table(
      border: pw.TableBorder.all(color: PdfColors.grey400, width: 0.5),
      columnWidths: {
        0: const pw.FlexColumnWidth(1.8),
        1: const pw.FlexColumnWidth(1),
        2: const pw.FlexColumnWidth(0.8),
        3: const pw.FlexColumnWidth(2.4),
      },
      children: [_fieldHeader(), ...rows],
    );

// ═══════════════════════════════════════════════════════════════════════
// PDF Builder
// ═══════════════════════════════════════════════════════════════════════

pw.Document buildAuthApiDoc() {
  final pdf = pw.Document(
    title: 'Sanoa Authentication API - Complete Documentation',
    author: 'Sanoa Platform',
  );

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 1: COVER / OVERVIEW
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      pw.SizedBox(height: 50),
      pw.Center(child: pw.Text('Sanoa Platform', style: _titleStyle)),
      pw.SizedBox(height: 6),
      pw.Center(child: pw.Text('Authentication API Documentation', style: pw.TextStyle(fontSize: 16, color: PdfColors.blueGrey600))),
      pw.SizedBox(height: 4),
      pw.Center(child: pw.Text('Dart / Flutter - Complete Reference', style: pw.TextStyle(fontSize: 12, color: PdfColors.blueGrey400))),
      pw.SizedBox(height: 30),
      _divider(),
      pw.SizedBox(height: 16),

      _section('1. Overview'),
      _body('Sanoa uses JWT (JSON Web Token) authentication via SimpleJWT. '
          'All authenticated requests must include the access token in the Authorization header as: Bearer <token>.'),
      _body('Base URL: https://your-domain.com (replace with your server)'),
      _body('All monetary values are in ZAR (South African Rand).'),

      _sub('User Types'),
      _body('- customer: App buyers/users. Auto-creates CustomerProfile on registration.'),
      _body('- vendor (individual): Informal traders (tuck shops, street vendors, freelancers). Create IndividualVendorProfile after registration.'),
      _body('- vendor (business): Registered businesses with CIPC. Create BusinessVendorProfile after registration.'),
      _body('- admin: Platform administrators.'),

      _sub('Authentication Flow'),
      _body('1. Register account (customer or vendor) -> receive JWT tokens immediately'),
      _body('2. For vendors: create vendor profile (individual OR business) -> triggers vetting'),
      _body('3. Use access token for authenticated requests (valid 60 minutes)'),
      _body('4. Refresh token when expired (valid 7 days, rotates on use)'),

      _sub('All Authentication Endpoints'),
      pw.Table(
        border: pw.TableBorder.all(color: PdfColors.grey400, width: 0.5),
        columnWidths: {0: const pw.FlexColumnWidth(1), 1: const pw.FlexColumnWidth(2.5), 2: const pw.FlexColumnWidth(2.5)},
        children: [
          pw.TableRow(
            decoration: const pw.BoxDecoration(color: PdfColors.blueGrey50),
            children: [
              pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Method', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
              pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Endpoint', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
              pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Description', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
            ],
          ),
          _tableRow('POST', '/api/accounts/register/', 'Register (customer or vendor)'),
          _tableRow('POST', '/api/auth/token/', 'Login - obtain JWT tokens'),
          _tableRow('POST', '/api/auth/token/refresh/', 'Refresh access token'),
          _tableRow('POST', '/api/auth/token/verify/', 'Verify token validity'),
          _tableRow('GET', '/api/accounts/me/', 'Get current user profile'),
          _tableRow('PATCH', '/api/accounts/me/', 'Update user profile'),
          _tableRow('POST', '/api/accounts/profiles/vendor/individual/', 'Create individual vendor profile'),
          _tableRow('POST', '/api/accounts/profiles/vendor/business/', 'Create business vendor profile'),
          _tableRow('GET', '/api/accounts/profiles/vendor/individual/{id}/', 'Get individual vendor profile'),
          _tableRow('GET', '/api/accounts/profiles/vendor/business/{id}/', 'Get business vendor profile'),
          _tableRow('PATCH', '/api/accounts/profiles/vendor/individual/{id}/', 'Update individual vendor profile'),
          _tableRow('PATCH', '/api/accounts/profiles/vendor/business/{id}/', 'Update business vendor profile'),
        ],
      ),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 2: DART MODELS
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('2. Dart Models'),
      _body('These Dart model classes map to the API response structures. Use them to deserialize JSON responses.'),

      _sub('2.1 AuthTokens'),
      _code('''class AuthTokens {
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
}'''),

      _sub('2.2 User'),
      _code('''class User {
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
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as String,
      email: json['email'] as String,
      username: json['username'] as String?,
      firstName: json['first_name'] as String,
      lastName: json['last_name'] as String,
      phoneNumber: json['phone_number'] as String?,
      userType: json['user_type'] as String,
      isVerified: json['is_verified'] as bool? ?? false,
      dateOfBirth: json['date_of_birth'] as String?,
      isActive: json['is_active'] as bool? ?? true,
      dateJoined: json['date_joined'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
      updatedAt: json['updated_at'] as String? ?? '',
      customerProfile: json['customer_profile'] != null
          ? CustomerProfile.fromJson(json['customer_profile'])
          : null,
      individualVendorProfile: json['individual_vendor_profile'] != null
          ? IndividualVendorProfile.fromJson(
              json['individual_vendor_profile'])
          : null,
      businessVendorProfile: json['business_vendor_profile'] != null
          ? BusinessVendorProfile.fromJson(
              json['business_vendor_profile'])
          : null,
    );
  }
}'''),

      _sub('2.3 RegisterResponse'),
      _code('''class RegisterResponse {
  final User user;
  final AuthTokens tokens;

  RegisterResponse({required this.user, required this.tokens});

  factory RegisterResponse.fromJson(Map<String, dynamic> json) {
    return RegisterResponse(
      user: User.fromJson(json['user'] as Map<String, dynamic>),
      tokens: AuthTokens.fromJson(json['tokens'] as Map<String, dynamic>),
    );
  }
}'''),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 2 continued: CustomerProfile + VendorProfile models
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _sub('2.4 CustomerProfile'),
      _code('''class CustomerProfile {
  final String id;
  final String? avatar;
  final String? gender;
  final String? bio;
  final List<int> interestCategories;
  final double? latitude;
  final double? longitude;
  final String preferredLanguage;
  final bool newsletterSubscription;
  final bool smsNotifications;
  final bool emailNotifications;
  final int loyaltyPoints;
  final String memberSince;
  final String createdAt;
  final String updatedAt;

  CustomerProfile({
    required this.id,
    this.avatar,
    this.gender,
    this.bio,
    this.interestCategories = const [],
    this.latitude,
    this.longitude,
    this.preferredLanguage = 'en',
    this.newsletterSubscription = true,
    this.smsNotifications = true,
    this.emailNotifications = true,
    this.loyaltyPoints = 0,
    required this.memberSince,
    required this.createdAt,
    required this.updatedAt,
  });

  factory CustomerProfile.fromJson(Map<String, dynamic> json) {
    return CustomerProfile(
      id: json['id'] as String,
      avatar: json['avatar'] as String?,
      gender: json['gender'] as String?,
      bio: json['bio'] as String?,
      interestCategories: (json['interest_categories'] as List?)
              ?.map((e) => e as int)
              .toList() ??
          [],
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      preferredLanguage:
          json['preferred_language'] as String? ?? 'en',
      newsletterSubscription:
          json['newsletter_subscription'] as bool? ?? true,
      smsNotifications:
          json['sms_notifications'] as bool? ?? true,
      emailNotifications:
          json['email_notifications'] as bool? ?? true,
      loyaltyPoints: json['loyalty_points'] as int? ?? 0,
      memberSince: json['member_since'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
      updatedAt: json['updated_at'] as String? ?? '',
    );
  }
}'''),

      _sub('2.5 IndividualVendorProfile'),
      _code('''class IndividualVendorProfile {
  final String id;
  final String? userEmail;
  final String? ownerName;
  final String storeName;
  final String vendorCategory;
  final String? storeDescription;
  final String? storeLogo;
  final String? qrCode;
  final String? qrCodeIdentifier;
  final String? idNumber;
  final String? tradingAddress;
  final String? tradingCity;
  final String? tradingProvince;
  final String? tradingPostalCode;
  final String verificationStatus;
  final String? rejectionReason;
  final String? verifiedAt;
  final bool isVerified;
  final double totalSales;
  final int totalOrders;
  final double averageRating;
  final int totalReviews;
  final double commissionRate;
  final bool storeActive;
  final bool acceptsReturns;
  final int returnWindowDays;
  final String createdAt;
  final String updatedAt;

  IndividualVendorProfile({
    required this.id, this.userEmail, this.ownerName,
    required this.storeName, required this.vendorCategory,
    this.storeDescription, this.storeLogo, this.qrCode,
    this.qrCodeIdentifier, this.idNumber,
    this.tradingAddress, this.tradingCity,
    this.tradingProvince, this.tradingPostalCode,
    this.verificationStatus = 'pending',
    this.rejectionReason, this.verifiedAt,
    this.isVerified = false,
    this.totalSales = 0, this.totalOrders = 0,
    this.averageRating = 0, this.totalReviews = 0,
    this.commissionRate = 8.0,
    this.storeActive = false, this.acceptsReturns = true,
    this.returnWindowDays = 14,
    required this.createdAt, required this.updatedAt,
  });

  factory IndividualVendorProfile.fromJson(Map<String, dynamic> j) {
    return IndividualVendorProfile(
      id: j['id'] as String,
      userEmail: j['user_email'] as String?,
      ownerName: j['owner_name'] as String?,
      storeName: j['store_name'] as String,
      vendorCategory: j['vendor_category'] as String,
      storeDescription: j['store_description'] as String?,
      storeLogo: j['store_logo'] as String?,
      qrCode: j['qr_code'] as String?,
      qrCodeIdentifier: j['qr_code_identifier'] as String?,
      idNumber: j['id_number'] as String?,
      tradingAddress: j['trading_address'] as String?,
      tradingCity: j['trading_city'] as String?,
      tradingProvince: j['trading_province'] as String?,
      tradingPostalCode: j['trading_postal_code'] as String?,
      verificationStatus:
          j['verification_status'] as String? ?? 'pending',
      rejectionReason: j['rejection_reason'] as String?,
      verifiedAt: j['verified_at'] as String?,
      isVerified: j['is_verified'] as bool? ?? false,
      totalSales: (j['total_sales'] as num?)?.toDouble() ?? 0,
      totalOrders: j['total_orders'] as int? ?? 0,
      averageRating:
          (j['average_rating'] as num?)?.toDouble() ?? 0,
      totalReviews: j['total_reviews'] as int? ?? 0,
      commissionRate:
          (j['commission_rate'] as num?)?.toDouble() ?? 8.0,
      storeActive: j['store_active'] as bool? ?? false,
      acceptsReturns: j['accepts_returns'] as bool? ?? true,
      returnWindowDays: j['return_window_days'] as int? ?? 14,
      createdAt: j['created_at'] as String? ?? '',
      updatedAt: j['updated_at'] as String? ?? '',
    );
  }
}'''),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 2 continued: BusinessVendorProfile model
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _sub('2.6 BusinessVendorProfile'),
      _code('''class BusinessVendorProfile {
  final String id;
  final String? userEmail;
  final String businessName;
  final String? businessTradingName;
  final String businessType;
  final String? businessDescription;
  final String? businessLogo;
  final String? businessWebsite;
  final String? qrCode;
  final String? qrCodeIdentifier;
  final String cipcRegistrationNumber;
  final String? taxNumber;
  final String? vatNumber;
  final String? ownerFullName;
  final String? ownerIdNumber;
  final String businessStreetAddress;
  final String businessCity;
  final String businessProvince;
  final String businessPostalCode;
  final String businessCountry;
  final String verificationStatus;
  final bool ownerVettingPassed;
  final bool businessVettingPassed;
  final String? rejectionReason;
  final String? verifiedAt;
  final bool isVerified;
  final bool isFullyVetted;
  final double totalSales;
  final int totalOrders;
  final double averageRating;
  final int totalReviews;
  final double commissionRate;
  final bool storeActive;
  final bool acceptsReturns;
  final int returnWindowDays;
  final String createdAt;
  final String updatedAt;

  BusinessVendorProfile({
    required this.id, this.userEmail,
    required this.businessName, this.businessTradingName,
    required this.businessType, this.businessDescription,
    this.businessLogo, this.businessWebsite,
    this.qrCode, this.qrCodeIdentifier,
    required this.cipcRegistrationNumber,
    this.taxNumber, this.vatNumber,
    this.ownerFullName, this.ownerIdNumber,
    required this.businessStreetAddress,
    required this.businessCity, required this.businessProvince,
    required this.businessPostalCode,
    this.businessCountry = 'South Africa',
    this.verificationStatus = 'pending',
    this.ownerVettingPassed = false,
    this.businessVettingPassed = false,
    this.rejectionReason, this.verifiedAt,
    this.isVerified = false, this.isFullyVetted = false,
    this.totalSales = 0, this.totalOrders = 0,
    this.averageRating = 0, this.totalReviews = 0,
    this.commissionRate = 5.0,
    this.storeActive = false, this.acceptsReturns = true,
    this.returnWindowDays = 30,
    required this.createdAt, required this.updatedAt,
  });

  factory BusinessVendorProfile.fromJson(Map<String, dynamic> j) {
    return BusinessVendorProfile(
      id: j['id'] as String,
      userEmail: j['user_email'] as String?,
      businessName: j['business_name'] as String,
      businessTradingName: j['business_trading_name'] as String?,
      businessType: j['business_type'] as String,
      businessDescription: j['business_description'] as String?,
      businessLogo: j['business_logo'] as String?,
      businessWebsite: j['business_website'] as String?,
      qrCode: j['qr_code'] as String?,
      qrCodeIdentifier: j['qr_code_identifier'] as String?,
      cipcRegistrationNumber:
          j['cipc_registration_number'] as String,
      taxNumber: j['tax_number'] as String?,
      vatNumber: j['vat_number'] as String?,
      ownerFullName: j['owner_full_name'] as String?,
      ownerIdNumber: j['owner_id_number'] as String?,
      businessStreetAddress:
          j['business_street_address'] as String,
      businessCity: j['business_city'] as String,
      businessProvince: j['business_province'] as String,
      businessPostalCode: j['business_postal_code'] as String,
      businessCountry:
          j['business_country'] as String? ?? 'South Africa',
      verificationStatus:
          j['verification_status'] as String? ?? 'pending',
      ownerVettingPassed:
          j['owner_vetting_passed'] as bool? ?? false,
      businessVettingPassed:
          j['business_vetting_passed'] as bool? ?? false,
      rejectionReason: j['rejection_reason'] as String?,
      verifiedAt: j['verified_at'] as String?,
      isVerified: j['is_verified'] as bool? ?? false,
      isFullyVetted: j['is_fully_vetted'] as bool? ?? false,
      totalSales: (j['total_sales'] as num?)?.toDouble() ?? 0,
      totalOrders: j['total_orders'] as int? ?? 0,
      averageRating:
          (j['average_rating'] as num?)?.toDouble() ?? 0,
      totalReviews: j['total_reviews'] as int? ?? 0,
      commissionRate:
          (j['commission_rate'] as num?)?.toDouble() ?? 5.0,
      storeActive: j['store_active'] as bool? ?? false,
      acceptsReturns: j['accepts_returns'] as bool? ?? true,
      returnWindowDays: j['return_window_days'] as int? ?? 30,
      createdAt: j['created_at'] as String? ?? '',
      updatedAt: j['updated_at'] as String? ?? '',
    );
  }
}'''),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 3: DART SETUP
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('3. Dart / Flutter Setup'),
      _body('Add dependencies to pubspec.yaml:'),
      _code('''dependencies:
  http: ^1.2.0
  flutter_secure_storage: ^9.0.0  # for secure token storage'''),

      _body('Base configuration and helpers:'),
      _code('''import 'dart:convert';
import 'package:http/http.dart' as http;

const String baseUrl = 'https://your-domain.com';

Map<String, String> jsonHeaders({String? token}) {
  final h = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
  if (token != null) {
    h['Authorization'] = 'Bearer \$token';
  }
  return h;
}

/// For multipart requests (file uploads)
Future<http.MultipartRequest> multipartRequest(
  String method,
  String path, {
  String? token,
}) async {
  final request = http.MultipartRequest(
    method,
    Uri.parse('\$baseUrl\$path'),
  );
  request.headers['Accept'] = 'application/json';
  if (token != null) {
    request.headers['Authorization'] = 'Bearer \$token';
  }
  return request;
}'''),
      _note('Replace baseUrl with your server. '
          'Android emulator: http://10.0.2.2:8000 | '
          'iOS simulator: http://localhost:8000'),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 4: CUSTOMER REGISTRATION
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('4. Customer Registration'),
      _body('Register a new app user (buyer). Returns user data with CustomerProfile and JWT tokens.'),
      _label('POST /api/accounts/register/'),
      _body('Authentication: None (public)'),
      _label('Request Body Fields'),
      _fieldTable([
        _fieldRow('email', 'String', 'Yes', 'Unique email address'),
        _fieldRow('password', 'String', 'Yes', 'Min 8 characters'),
        _fieldRow('password_confirm', 'String', 'Yes', 'Must match password'),
        _fieldRow('first_name', 'String', 'Yes', 'First name'),
        _fieldRow('last_name', 'String', 'Yes', 'Last name'),
        _fieldRow('username', 'String', 'No', 'Optional username'),
        _fieldRow('user_type', 'String', 'Yes', '"customer"'),
        _fieldRow('phone_number', 'String', 'No', 'E.g. +27821234567'),
        _fieldRow('interest_categories', 'List<int>', 'No', 'Category IDs user is interested in'),
        _fieldRow('latitude', 'double', 'No', 'User GPS latitude'),
        _fieldRow('longitude', 'double', 'No', 'User GPS longitude'),
      ]),

      _label('Dart HTTP Request'),
      _code('''Future<RegisterResponse> registerCustomer({
  required String email,
  required String password,
  required String firstName,
  required String lastName,
  String? username,
  String? phoneNumber,
  List<int>? interestCategories,
  double? latitude,
  double? longitude,
}) async {
  final response = await http.post(
    Uri.parse('\$baseUrl/api/accounts/register/'),
    headers: jsonHeaders(),
    body: jsonEncode({
      'email': email,
      'password': password,
      'password_confirm': password,
      'first_name': firstName,
      'last_name': lastName,
      'user_type': 'customer',
      if (username != null) 'username': username,
      if (phoneNumber != null) 'phone_number': phoneNumber,
      if (interestCategories != null)
        'interest_categories': interestCategories,
      if (latitude != null) 'latitude': latitude,
      if (longitude != null) 'longitude': longitude,
    }),
  );

  if (response.statusCode == 201) {
    return RegisterResponse.fromJson(jsonDecode(response.body));
  }
  throw Exception('Registration failed: \${response.body}');
}'''),

      _label('Success Response (201 Created)'),
      _code('''{
  "user": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "john@example.com",
    "username": "john@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "phone_number": "+27821234567",
    "user_type": "customer",
    "is_verified": false,
    "date_of_birth": null,
    "is_active": true,
    "date_joined": "2026-03-08T10:30:00Z",
    "created_at": "2026-03-08T10:30:00Z",
    "updated_at": "2026-03-08T10:30:00Z"
  },
  "tokens": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }
}'''),
      _note('CustomerProfile is auto-created via Django signal. '
          'interest_categories and lat/long are set on the profile if provided.'),

      _label('Error Response (400 Bad Request)'),
      _code('''{
  "email": ["user with this email address already exists."],
  "non_field_errors": ["Passwords do not match."]
}'''),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 5: VENDOR REGISTRATION (account only)
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('5. Vendor Registration (Account Only)'),
      _body('Register a vendor account. This creates the user only. '
          'You must then create either an Individual or Business vendor profile in a separate call.'),
      _label('POST /api/accounts/register/'),
      _body('Authentication: None (public)'),
      _label('Request Body Fields'),
      _fieldTable([
        _fieldRow('email', 'String', 'Yes', 'Unique email address'),
        _fieldRow('password', 'String', 'Yes', 'Min 8 characters'),
        _fieldRow('password_confirm', 'String', 'Yes', 'Must match password'),
        _fieldRow('first_name', 'String', 'Yes', 'Owner first name'),
        _fieldRow('last_name', 'String', 'Yes', 'Owner last name'),
        _fieldRow('username', 'String', 'No', 'Optional username'),
        _fieldRow('user_type', 'String', 'Yes', '"vendor"'),
        _fieldRow('phone_number', 'String', 'No', 'E.g. +27831234567'),
      ]),

      _label('Dart HTTP Request'),
      _code('''Future<RegisterResponse> registerVendor({
  required String email,
  required String password,
  required String firstName,
  required String lastName,
  String? username,
  String? phoneNumber,
}) async {
  final response = await http.post(
    Uri.parse('\$baseUrl/api/accounts/register/'),
    headers: jsonHeaders(),
    body: jsonEncode({
      'email': email,
      'password': password,
      'password_confirm': password,
      'first_name': firstName,
      'last_name': lastName,
      'user_type': 'vendor',
      if (username != null) 'username': username,
      if (phoneNumber != null) 'phone_number': phoneNumber,
    }),
  );

  if (response.statusCode == 201) {
    return RegisterResponse.fromJson(jsonDecode(response.body));
  }
  throw Exception('Registration failed: \${response.body}');
}'''),

      _label('Success Response (201 Created)'),
      _code('''{
  "user": {
    "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
    "email": "vendor@example.com",
    "username": "vendor@example.com",
    "first_name": "Jane",
    "last_name": "Smith",
    "phone_number": "+27831234567",
    "user_type": "vendor",
    "is_verified": false,
    "date_of_birth": null,
    "is_active": true,
    "date_joined": "2026-03-08T11:00:00Z",
    "created_at": "2026-03-08T11:00:00Z",
    "updated_at": "2026-03-08T11:00:00Z"
  },
  "tokens": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }
}'''),
      _note('NEXT STEP: Create vendor profile using the access token.\n'
          '- Individual vendor: POST /api/accounts/profiles/vendor/individual/\n'
          '- Business vendor: POST /api/accounts/profiles/vendor/business/\n'
          'A user can only have ONE vendor profile (individual OR business, not both).'),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 6: INDIVIDUAL VENDOR PROFILE CREATION
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('6. Create Individual Vendor Profile'),
      _body('For informal traders: tuck shops, street vendors, local brands, home businesses, '
          'freelancers, craftspersons. Requires owner ID documents for vetting.'),
      _label('POST /api/accounts/profiles/vendor/individual/'),
      _body('Authentication: Required (Bearer token, user_type must be "vendor")'),
      _body('Content-Type: multipart/form-data (for file uploads)'),

      _label('Request Body Fields'),
      _fieldTable([
        _fieldRow('store_name', 'String', 'Yes', 'Store/trading name'),
        _fieldRow('vendor_category', 'String', 'Yes', 'tuck_shop | street_vendor | local_brand | home_business | freelancer | craftsperson | other'),
        _fieldRow('store_description', 'String', 'No', 'Store description (max 1000 chars)'),
        _fieldRow('store_logo', 'File', 'No', 'Store logo image'),
        _fieldRow('id_number', 'String', 'Yes', 'SA ID number'),
        _fieldRow('id_document', 'File', 'Yes', 'Copy of ID document'),
        _fieldRow('proof_of_address', 'File', 'Yes', 'Proof of address document'),
        _fieldRow('selfie_with_id', 'File', 'No', 'Selfie holding ID'),
        _fieldRow('trading_address', 'String', 'No', 'Trading/store address'),
        _fieldRow('trading_city', 'String', 'No', 'City'),
        _fieldRow('trading_province', 'String', 'No', 'Province'),
        _fieldRow('trading_postal_code', 'String', 'No', 'Postal code'),
        _fieldRow('bank_name', 'String', 'No', 'Bank name'),
        _fieldRow('bank_account_number', 'String', 'No', 'Account number'),
        _fieldRow('bank_branch_code', 'String', 'No', 'Branch code'),
        _fieldRow('bank_account_holder', 'String', 'No', 'Account holder name'),
      ]),

      _label('Dart HTTP Request (multipart/form-data)'),
      _code('''Future<IndividualVendorProfile> createIndividualProfile({
  required String accessToken,
  required String storeName,
  required String vendorCategory,
  required String idNumber,
  required File idDocument,
  required File proofOfAddress,
  String? storeDescription,
  File? storeLogo,
  File? selfieWithId,
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
    Uri.parse(
      '\$baseUrl/api/accounts/profiles/vendor/individual/',
    ),
  );
  request.headers['Authorization'] = 'Bearer \$accessToken';

  // Required fields
  request.fields['store_name'] = storeName;
  request.fields['vendor_category'] = vendorCategory;
  request.fields['id_number'] = idNumber;
  request.files.add(
    await http.MultipartFile.fromPath(
      'id_document', idDocument.path,
    ),
  );
  request.files.add(
    await http.MultipartFile.fromPath(
      'proof_of_address', proofOfAddress.path,
    ),
  );

  // Optional fields
  if (storeDescription != null)
    request.fields['store_description'] = storeDescription;
  if (storeLogo != null)
    request.files.add(
      await http.MultipartFile.fromPath(
        'store_logo', storeLogo.path,
      ),
    );
  if (selfieWithId != null)
    request.files.add(
      await http.MultipartFile.fromPath(
        'selfie_with_id', selfieWithId.path,
      ),
    );
  if (tradingAddress != null)
    request.fields['trading_address'] = tradingAddress;
  if (tradingCity != null)
    request.fields['trading_city'] = tradingCity;
  if (tradingProvince != null)
    request.fields['trading_province'] = tradingProvince;
  if (tradingPostalCode != null)
    request.fields['trading_postal_code'] = tradingPostalCode;
  if (bankName != null)
    request.fields['bank_name'] = bankName;
  if (bankAccountNumber != null)
    request.fields['bank_account_number'] = bankAccountNumber;
  if (bankBranchCode != null)
    request.fields['bank_branch_code'] = bankBranchCode;
  if (bankAccountHolder != null)
    request.fields['bank_account_holder'] = bankAccountHolder;

  final streamed = await request.send();
  final body = await streamed.stream.bytesToString();

  if (streamed.statusCode == 201) {
    return IndividualVendorProfile.fromJson(
      jsonDecode(body),
    );
  }
  throw Exception('Profile creation failed: \$body');
}'''),
    ],
  ));

  // Individual vendor profile response
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _sub('6.1 Individual Vendor Profile - Response'),
      _label('Success Response (201 Created)'),
      _code('''{
  "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "user_email": "vendor@example.com",
  "owner_name": "Jane Smith",
  "store_name": "Jane's Tuck Shop",
  "vendor_category": "tuck_shop",
  "store_description": "Fresh snacks and drinks",
  "store_logo": "https://your-domain.com/media/logos/vendors/individual/logo.jpg",
  "qr_code": "https://your-domain.com/media/qrcodes/vendors/individual/qr.png",
  "qr_code_identifier": "d4e5f6a7-b8c9-0123-def0-234567890123",
  "id_number": "9001015800087",
  "id_document": "https://your-domain.com/media/documents/vendors/individual/id/id.pdf",
  "proof_of_address": "https://your-domain.com/media/documents/vendors/individual/address/poa.pdf",
  "selfie_with_id": null,
  "trading_address": "123 Main Rd",
  "trading_city": "Johannesburg",
  "trading_province": "Gauteng",
  "trading_postal_code": "2000",
  "bank_name": "FNB",
  "bank_account_number": "62012345678",
  "bank_branch_code": "250655",
  "bank_account_holder": "Jane Smith",
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
  "created_at": "2026-03-08T11:05:00Z",
  "updated_at": "2026-03-08T11:05:00Z"
}'''),
      _note('On profile creation:\n'
          '1. A QR code is auto-generated for the store\n'
          '2. A VettingApplication (type: individual_owner) is auto-created\n'
          '3. verification_status starts as "pending" -> admin reviews -> "verified"\n'
          '4. store_active becomes true only after vetting approval'),

      _label('Error Responses'),
      _code('''// 400 - Already has a profile
{
  "non_field_errors": [
    "You already have an individual vendor profile."
  ]
}

// 400 - Wrong user type
{
  "non_field_errors": [
    "Only users with vendor account type can create a vendor profile."
  ]
}

// 400 - Already has business profile
{
  "non_field_errors": [
    "You already have a business vendor profile. "
    "A user can only have one vendor profile."
  ]
}'''),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 7: BUSINESS VENDOR PROFILE CREATION
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('7. Create Business Vendor Profile'),
      _body('For CIPC-registered businesses: sole proprietors, partnerships, Pty Ltd, CC, NPC, cooperatives. '
          'Requires CIPC documents AND owner ID for two-stage vetting.'),
      _label('POST /api/accounts/profiles/vendor/business/'),
      _body('Authentication: Required (Bearer token, user_type must be "vendor")'),
      _body('Content-Type: multipart/form-data (for file uploads)'),

      _label('Request Body Fields'),
      _fieldTable([
        _fieldRow('business_name', 'String', 'Yes', 'Registered business name'),
        _fieldRow('business_trading_name', 'String', 'No', 'Trading-as name'),
        _fieldRow('business_type', 'String', 'Yes', 'sole_proprietor | partnership | pty_ltd | cc | npc | cooperative | other'),
        _fieldRow('business_description', 'String', 'No', 'Description (max 2000 chars)'),
        _fieldRow('business_logo', 'File', 'No', 'Business logo image'),
        _fieldRow('business_website', 'String', 'No', 'Website URL'),
        _fieldRow('cipc_registration_number', 'String', 'Yes', 'CIPC reg number (unique)'),
        _fieldRow('cipc_document', 'File', 'Yes', 'CIPC registration document'),
        _fieldRow('tax_number', 'String', 'No', 'Tax reference number'),
        _fieldRow('tax_clearance_certificate', 'File', 'No', 'Tax clearance cert'),
        _fieldRow('vat_number', 'String', 'No', 'VAT number'),
        _fieldRow('bee_certificate', 'File', 'No', 'BEE certificate'),
        _fieldRow('owner_full_name', 'String', 'Yes', 'Owner/director full name'),
        _fieldRow('owner_id_number', 'String', 'Yes', 'Owner SA ID number'),
        _fieldRow('owner_id_document', 'File', 'Yes', 'Owner ID document'),
        _fieldRow('owner_proof_of_address', 'File', 'Yes', 'Owner proof of address'),
        _fieldRow('business_street_address', 'String', 'Yes', 'Business street address'),
        _fieldRow('business_city', 'String', 'Yes', 'City'),
        _fieldRow('business_province', 'String', 'Yes', 'Province'),
        _fieldRow('business_postal_code', 'String', 'Yes', 'Postal code'),
        _fieldRow('business_country', 'String', 'No', 'Default: South Africa'),
        _fieldRow('bank_name', 'String', 'Yes', 'Bank name'),
        _fieldRow('bank_account_number', 'String', 'Yes', 'Account number'),
        _fieldRow('bank_branch_code', 'String', 'Yes', 'Branch code'),
        _fieldRow('bank_account_holder', 'String', 'Yes', 'Account holder name'),
      ]),
    ],
  ));

  // Business vendor Dart request
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _sub('7.1 Business Vendor - Dart HTTP Request'),
      _code('''Future<BusinessVendorProfile> createBusinessProfile({
  required String accessToken,
  required String businessName,
  required String businessType,
  required String cipcRegistrationNumber,
  required File cipcDocument,
  required String ownerFullName,
  required String ownerIdNumber,
  required File ownerIdDocument,
  required File ownerProofOfAddress,
  required String businessStreetAddress,
  required String businessCity,
  required String businessProvince,
  required String businessPostalCode,
  required String bankName,
  required String bankAccountNumber,
  required String bankBranchCode,
  required String bankAccountHolder,
  String? businessTradingName,
  String? businessDescription,
  File? businessLogo,
  String? businessWebsite,
  String? taxNumber,
  File? taxClearanceCertificate,
  String? vatNumber,
  File? beeCertificate,
  String businessCountry = 'South Africa',
}) async {
  final request = http.MultipartRequest(
    'POST',
    Uri.parse(
      '\$baseUrl/api/accounts/profiles/vendor/business/',
    ),
  );
  request.headers['Authorization'] = 'Bearer \$accessToken';

  // Required text fields
  request.fields['business_name'] = businessName;
  request.fields['business_type'] = businessType;
  request.fields['cipc_registration_number'] =
      cipcRegistrationNumber;
  request.fields['owner_full_name'] = ownerFullName;
  request.fields['owner_id_number'] = ownerIdNumber;
  request.fields['business_street_address'] =
      businessStreetAddress;
  request.fields['business_city'] = businessCity;
  request.fields['business_province'] = businessProvince;
  request.fields['business_postal_code'] = businessPostalCode;
  request.fields['business_country'] = businessCountry;
  request.fields['bank_name'] = bankName;
  request.fields['bank_account_number'] = bankAccountNumber;
  request.fields['bank_branch_code'] = bankBranchCode;
  request.fields['bank_account_holder'] = bankAccountHolder;

  // Required file fields
  request.files.add(await http.MultipartFile.fromPath(
    'cipc_document', cipcDocument.path));
  request.files.add(await http.MultipartFile.fromPath(
    'owner_id_document', ownerIdDocument.path));
  request.files.add(await http.MultipartFile.fromPath(
    'owner_proof_of_address', ownerProofOfAddress.path));

  // Optional fields
  if (businessTradingName != null)
    request.fields['business_trading_name'] =
        businessTradingName;
  if (businessDescription != null)
    request.fields['business_description'] =
        businessDescription;
  if (businessWebsite != null)
    request.fields['business_website'] = businessWebsite;
  if (taxNumber != null)
    request.fields['tax_number'] = taxNumber;
  if (vatNumber != null)
    request.fields['vat_number'] = vatNumber;
  if (businessLogo != null)
    request.files.add(await http.MultipartFile.fromPath(
      'business_logo', businessLogo.path));
  if (taxClearanceCertificate != null)
    request.files.add(await http.MultipartFile.fromPath(
      'tax_clearance_certificate',
      taxClearanceCertificate.path));
  if (beeCertificate != null)
    request.files.add(await http.MultipartFile.fromPath(
      'bee_certificate', beeCertificate.path));

  final streamed = await request.send();
  final body = await streamed.stream.bytesToString();

  if (streamed.statusCode == 201) {
    return BusinessVendorProfile.fromJson(jsonDecode(body));
  }
  throw Exception('Profile creation failed: \$body');
}'''),
    ],
  ));

  // Business vendor response
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _sub('7.2 Business Vendor Profile - Response'),
      _label('Success Response (201 Created)'),
      _code('''{
  "id": "d4e5f6a7-b8c9-0123-def0-234567890abc",
  "user_email": "business@example.com",
  "business_name": "Mzansi Fresh Produce Pty Ltd",
  "business_trading_name": "Mzansi Fresh",
  "business_type": "pty_ltd",
  "business_description": "Fresh organic produce supplier",
  "business_logo": ".../media/logos/vendors/business/logo.jpg",
  "business_website": "https://mzansifresh.co.za",
  "qr_code": ".../media/qrcodes/vendors/business/qr.png",
  "qr_code_identifier": "e5f6a7b8-c9d0-1234-ef01-345678901234",
  "cipc_registration_number": "2024/123456/07",
  "cipc_document": ".../media/documents/.../cipc.pdf",
  "tax_number": "9876543210",
  "tax_clearance_certificate": ".../media/documents/.../tax.pdf",
  "vat_number": "4567890123",
  "bee_certificate": null,
  "owner_full_name": "Jane Smith",
  "owner_id_number": "9001015800087",
  "owner_id_document": ".../media/documents/.../owner_id.pdf",
  "owner_proof_of_address": ".../media/documents/.../poa.pdf",
  "business_street_address": "456 Business Park",
  "business_city": "Cape Town",
  "business_province": "Western Cape",
  "business_postal_code": "8000",
  "business_country": "South Africa",
  "bank_name": "Standard Bank",
  "bank_account_number": "012345678",
  "bank_branch_code": "051001",
  "bank_account_holder": "Mzansi Fresh Produce Pty Ltd",
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
  "created_at": "2026-03-08T11:15:00Z",
  "updated_at": "2026-03-08T11:15:00Z"
}'''),
      _note('On profile creation:\n'
          '1. QR code auto-generated\n'
          '2. TWO VettingApplications created: business_owner + business_entity\n'
          '3. Two-stage vetting: owner must pass first, then business entity\n'
          '4. verification_status: pending -> owner_verified -> verified\n'
          '5. store_active=true only after BOTH vettings pass'),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 8: LOGIN
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('8. Login (Obtain JWT Tokens)'),
      _body('Authenticate with email and password. Works for all user types.'),
      _label('POST /api/auth/token/'),
      _body('Authentication: None (public)'),

      _label('Request Body'),
      _fieldTable([
        _fieldRow('email', 'String', 'Yes', 'User email address'),
        _fieldRow('password', 'String', 'Yes', 'User password'),
      ]),

      _label('Dart HTTP Request'),
      _code('''Future<AuthTokens> login({
  required String email,
  required String password,
}) async {
  final response = await http.post(
    Uri.parse('\$baseUrl/api/auth/token/'),
    headers: jsonHeaders(),
    body: jsonEncode({
      'email': email,
      'password': password,
    }),
  );

  if (response.statusCode == 200) {
    return AuthTokens.fromJson(jsonDecode(response.body));
  }
  throw Exception('Login failed: \${response.body}');
}'''),

      _label('Success Response (200 OK)'),
      _code('''{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoi...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoi..."
}'''),

      _label('Error Response (401 Unauthorized)'),
      _code('''{
  "detail": "No active account found with the given credentials"
}'''),
      _note('The USERNAME_FIELD is "email" - login uses email, not username.'),

      _divider(),

      // ── TOKEN REFRESH ──
      _section('9. Token Refresh'),
      _body('Refresh an expired access token. Refresh tokens rotate (old one invalidated).'),
      _label('POST /api/auth/token/refresh/'),

      _label('Request Body'),
      _fieldTable([
        _fieldRow('refresh', 'String', 'Yes', 'Current refresh token'),
      ]),

      _label('Dart HTTP Request'),
      _code('''Future<AuthTokens> refreshTokens({
  required String refreshToken,
}) async {
  final response = await http.post(
    Uri.parse('\$baseUrl/api/auth/token/refresh/'),
    headers: jsonHeaders(),
    body: jsonEncode({'refresh': refreshToken}),
  );

  if (response.statusCode == 200) {
    return AuthTokens.fromJson(jsonDecode(response.body));
  }
  throw Exception('Refresh failed: \${response.body}');
}'''),

      _label('Success Response (200 OK)'),
      _code('''{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}'''),
      _note('CRITICAL: Save the NEW refresh token. The old one is now invalid.'),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 10: TOKEN VERIFY
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('10. Token Verify'),
      _body('Check if a token is still valid. Returns 200 if valid, 401 if expired/invalid.'),
      _label('POST /api/auth/token/verify/'),

      _label('Request Body'),
      _fieldTable([
        _fieldRow('token', 'String', 'Yes', 'Access or refresh token to verify'),
      ]),

      _label('Dart HTTP Request'),
      _code('''Future<bool> verifyToken({required String token}) async {
  final response = await http.post(
    Uri.parse('\$baseUrl/api/auth/token/verify/'),
    headers: jsonHeaders(),
    body: jsonEncode({'token': token}),
  );
  return response.statusCode == 200;
}'''),

      _label('Success Response (200 OK)'),
      _code('{}'),

      _label('Error Response (401 Unauthorized)'),
      _code('''{
  "detail": "Token is invalid or expired",
  "code": "token_not_valid"
}'''),

      _divider(),

      // ── GET PROFILE ──
      _section('11. Get Current User Profile'),
      _body('Returns full user data with nested profile. The response includes '
          'customer_profile, individual_vendor_profile, or business_vendor_profile depending on user type.'),
      _label('GET /api/accounts/me/'),
      _body('Authentication: Required (Bearer token)'),

      _label('Dart HTTP Request'),
      _code('''Future<User> getProfile({
  required String accessToken,
}) async {
  final response = await http.get(
    Uri.parse('\$baseUrl/api/accounts/me/'),
    headers: jsonHeaders(token: accessToken),
  );

  if (response.statusCode == 200) {
    return User.fromJson(jsonDecode(response.body));
  }
  if (response.statusCode == 401) {
    throw Exception('Token expired - call refreshTokens()');
  }
  throw Exception('Failed: \${response.body}');
}'''),
    ],
  ));

  // GET profile responses for each user type
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _sub('11.1 Profile Response - Customer'),
      _code('''{
  "id": "a1b2c3d4-...",
  "email": "customer@example.com",
  "username": "customer@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+27821234567",
  "user_type": "customer",
  "is_verified": false,
  "date_of_birth": null,
  "is_active": true,
  "customer_profile": {
    "id": "e5f6g7h8-...",
    "user_email": "customer@example.com",
    "avatar": null,
    "gender": null,
    "bio": "",
    "interest_categories": [1, 3, 5],
    "latitude": "-26.195246",
    "longitude": "28.034088",
    "preferred_language": "en",
    "newsletter_subscription": true,
    "sms_notifications": true,
    "email_notifications": true,
    "loyalty_points": 0,
    "member_since": "2026-03-08T10:30:00Z",
    "created_at": "2026-03-08T10:30:00Z",
    "updated_at": "2026-03-08T10:30:00Z"
  },
  "individual_vendor_profile": null,
  "business_vendor_profile": null,
  "addresses": [],
  "date_joined": "2026-03-08T10:30:00Z",
  "created_at": "2026-03-08T10:30:00Z",
  "updated_at": "2026-03-08T10:30:00Z"
}'''),

      _sub('11.2 Profile Response - Individual Vendor'),
      _code('''{
  "id": "b2c3d4e5-...",
  "email": "vendor@example.com",
  "username": "vendor@example.com",
  "first_name": "Jane",
  "last_name": "Smith",
  "phone_number": "+27831234567",
  "user_type": "vendor",
  "is_verified": false,
  "customer_profile": null,
  "individual_vendor_profile": {
    "id": "c3d4e5f6-...",
    "user_email": "vendor@example.com",
    "owner_name": "Jane Smith",
    "store_name": "Jane's Tuck Shop",
    "vendor_category": "tuck_shop",
    "store_description": "Fresh snacks and drinks",
    "store_logo": ".../logo.jpg",
    "qr_code": ".../qr.png",
    "qr_code_identifier": "d4e5f6a7-...",
    "verification_status": "pending",
    "is_verified": false,
    "total_sales": "0.00",
    "total_orders": 0,
    "average_rating": "0.00",
    "total_reviews": 0,
    "store_active": false,
    "commission_rate": "8.00",
    "...": "..."
  },
  "business_vendor_profile": null,
  "addresses": []
}'''),

      _sub('11.3 Profile Response - Business Vendor'),
      _code('''{
  "id": "f6a7b8c9-...",
  "email": "business@example.com",
  "user_type": "vendor",
  "customer_profile": null,
  "individual_vendor_profile": null,
  "business_vendor_profile": {
    "id": "d4e5f6a7-...",
    "business_name": "Mzansi Fresh Produce Pty Ltd",
    "business_type": "pty_ltd",
    "cipc_registration_number": "2024/123456/07",
    "verification_status": "pending",
    "owner_vetting_passed": false,
    "business_vetting_passed": false,
    "is_verified": false,
    "is_fully_vetted": false,
    "store_active": false,
    "commission_rate": "5.00",
    "...": "..."
  },
  "addresses": []
}'''),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 12: UPDATE PROFILE
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('12. Update User Profile'),
      _body('Partial update of the user account. Only send fields you want to change.'),
      _label('PATCH /api/accounts/me/'),
      _body('Authentication: Required (Bearer token)'),

      _label('Updatable Fields'),
      _fieldTable([
        _fieldRow('first_name', 'String', 'No', 'First name'),
        _fieldRow('last_name', 'String', 'No', 'Last name'),
        _fieldRow('phone_number', 'String', 'No', 'Phone number'),
        _fieldRow('date_of_birth', 'String', 'No', 'YYYY-MM-DD format'),
      ]),

      _label('Dart HTTP Request'),
      _code('''Future<User> updateProfile({
  required String accessToken,
  String? firstName,
  String? lastName,
  String? phoneNumber,
  String? dateOfBirth,
}) async {
  final body = <String, dynamic>{};
  if (firstName != null) body['first_name'] = firstName;
  if (lastName != null) body['last_name'] = lastName;
  if (phoneNumber != null) body['phone_number'] = phoneNumber;
  if (dateOfBirth != null) body['date_of_birth'] = dateOfBirth;

  final response = await http.patch(
    Uri.parse('\$baseUrl/api/accounts/me/'),
    headers: jsonHeaders(token: accessToken),
    body: jsonEncode(body),
  );

  if (response.statusCode == 200) {
    return User.fromJson(jsonDecode(response.body));
  }
  throw Exception('Update failed: \${response.body}');
}'''),

      _label('Success Response (200 OK)'),
      _body('Returns the full updated User object (same as GET /api/accounts/me/).'),

      _divider(),

      // ── UPDATE VENDOR PROFILES ──
      _section('13. Update Vendor Profiles'),
      _body('Update individual or business vendor profile fields.'),

      _sub('13.1 Update Individual Vendor Profile'),
      _label('PATCH /api/accounts/profiles/vendor/individual/{id}/'),
      _body('Authentication: Required (Bearer token, must be profile owner)'),

      _label('Dart HTTP Request'),
      _code('''Future<IndividualVendorProfile> updateIndividualProfile({
  required String accessToken,
  required String profileId,
  String? storeName,
  String? storeDescription,
  String? tradingAddress,
  String? tradingCity,
  String? tradingProvince,
  bool? acceptsReturns,
  int? returnWindowDays,
}) async {
  final body = <String, dynamic>{};
  if (storeName != null) body['store_name'] = storeName;
  if (storeDescription != null)
    body['store_description'] = storeDescription;
  if (tradingAddress != null)
    body['trading_address'] = tradingAddress;
  if (tradingCity != null) body['trading_city'] = tradingCity;
  if (tradingProvince != null)
    body['trading_province'] = tradingProvince;
  if (acceptsReturns != null)
    body['accepts_returns'] = acceptsReturns;
  if (returnWindowDays != null)
    body['return_window_days'] = returnWindowDays;

  final response = await http.patch(
    Uri.parse(
      '\$baseUrl/api/accounts/profiles/vendor/individual/'
      '\$profileId/',
    ),
    headers: jsonHeaders(token: accessToken),
    body: jsonEncode(body),
  );

  if (response.statusCode == 200) {
    return IndividualVendorProfile.fromJson(
      jsonDecode(response.body),
    );
  }
  throw Exception('Update failed: \${response.body}');
}'''),

      _sub('13.2 Update Business Vendor Profile'),
      _label('PATCH /api/accounts/profiles/vendor/business/{id}/'),

      _label('Dart HTTP Request'),
      _code('''Future<BusinessVendorProfile> updateBusinessProfile({
  required String accessToken,
  required String profileId,
  String? businessDescription,
  String? businessWebsite,
  String? businessStreetAddress,
  String? businessCity,
  bool? acceptsReturns,
  int? returnWindowDays,
}) async {
  final body = <String, dynamic>{};
  if (businessDescription != null)
    body['business_description'] = businessDescription;
  if (businessWebsite != null)
    body['business_website'] = businessWebsite;
  if (businessStreetAddress != null)
    body['business_street_address'] = businessStreetAddress;
  if (businessCity != null)
    body['business_city'] = businessCity;
  if (acceptsReturns != null)
    body['accepts_returns'] = acceptsReturns;
  if (returnWindowDays != null)
    body['return_window_days'] = returnWindowDays;

  final response = await http.patch(
    Uri.parse(
      '\$baseUrl/api/accounts/profiles/vendor/business/'
      '\$profileId/',
    ),
    headers: jsonHeaders(token: accessToken),
    body: jsonEncode(body),
  );

  if (response.statusCode == 200) {
    return BusinessVendorProfile.fromJson(
      jsonDecode(response.body),
    );
  }
  throw Exception('Update failed: \${response.body}');
}'''),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 14: COMPLETE AUTH SERVICE
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('14. Complete AuthService Class'),
      _body('A production-ready service class combining all auth operations with automatic token refresh.'),
      _code('''import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthService {
  static const _baseUrl = 'https://your-domain.com';
  final _storage = const FlutterSecureStorage();

  String? _accessToken;
  String? _refreshToken;
  User? _currentUser;

  User? get currentUser => _currentUser;
  bool get isAuthenticated => _accessToken != null;

  Map<String, String> _headers({bool auth = true}) {
    final h = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (auth && _accessToken != null) {
      h['Authorization'] = 'Bearer \$_accessToken';
    }
    return h;
  }

  Future<void> _saveTokens(AuthTokens tokens) async {
    _accessToken = tokens.access;
    _refreshToken = tokens.refresh;
    await _storage.write(
      key: 'access_token', value: tokens.access);
    await _storage.write(
      key: 'refresh_token', value: tokens.refresh);
  }

  /// Load tokens from secure storage on app start
  Future<bool> loadSavedTokens() async {
    _accessToken = await _storage.read(key: 'access_token');
    _refreshToken = await _storage.read(key: 'refresh_token');
    if (_accessToken == null) return false;
    // Verify token is still valid
    try {
      final valid = await verifyToken(_accessToken!);
      if (!valid) await refreshTokens();
      return true;
    } catch (_) {
      await logout();
      return false;
    }
  }

  /// Register customer
  Future<User> registerCustomer({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    String? phoneNumber,
    List<int>? interestCategories,
    double? latitude,
    double? longitude,
  }) async {
    final res = await http.post(
      Uri.parse('\$_baseUrl/api/accounts/register/'),
      headers: _headers(auth: false),
      body: jsonEncode({
        'email': email,
        'password': password,
        'password_confirm': password,
        'first_name': firstName,
        'last_name': lastName,
        'user_type': 'customer',
        if (phoneNumber != null) 'phone_number': phoneNumber,
        if (interestCategories != null)
          'interest_categories': interestCategories,
        if (latitude != null) 'latitude': latitude,
        if (longitude != null) 'longitude': longitude,
      }),
    );
    if (res.statusCode != 201) throw Exception(res.body);
    final data = jsonDecode(res.body);
    await _saveTokens(
      AuthTokens.fromJson(data['tokens']));
    _currentUser = User.fromJson(data['user']);
    return _currentUser!;
  }

  /// Register vendor
  Future<User> registerVendor({
    required String email,
    required String password,
    required String firstName,
    required String lastName,
    String? phoneNumber,
  }) async {
    final res = await http.post(
      Uri.parse('\$_baseUrl/api/accounts/register/'),
      headers: _headers(auth: false),
      body: jsonEncode({
        'email': email,
        'password': password,
        'password_confirm': password,
        'first_name': firstName,
        'last_name': lastName,
        'user_type': 'vendor',
        if (phoneNumber != null) 'phone_number': phoneNumber,
      }),
    );
    if (res.statusCode != 201) throw Exception(res.body);
    final data = jsonDecode(res.body);
    await _saveTokens(
      AuthTokens.fromJson(data['tokens']));
    _currentUser = User.fromJson(data['user']);
    return _currentUser!;
  }

  /// Login
  Future<User> login({
    required String email,
    required String password,
  }) async {
    final res = await http.post(
      Uri.parse('\$_baseUrl/api/auth/token/'),
      headers: _headers(auth: false),
      body: jsonEncode({
        'email': email, 'password': password,
      }),
    );
    if (res.statusCode != 200) throw Exception(res.body);
    await _saveTokens(
      AuthTokens.fromJson(jsonDecode(res.body)));
    return await getProfile();
  }

  /// Refresh tokens
  Future<void> refreshTokens() async {
    if (_refreshToken == null) throw Exception('No token');
    final res = await http.post(
      Uri.parse('\$_baseUrl/api/auth/token/refresh/'),
      headers: _headers(auth: false),
      body: jsonEncode({'refresh': _refreshToken}),
    );
    if (res.statusCode != 200) {
      await logout();
      throw Exception('Session expired');
    }
    await _saveTokens(
      AuthTokens.fromJson(jsonDecode(res.body)));
  }

  /// Verify token
  Future<bool> verifyToken(String token) async {
    final res = await http.post(
      Uri.parse('\$_baseUrl/api/auth/token/verify/'),
      headers: _headers(auth: false),
      body: jsonEncode({'token': token}),
    );
    return res.statusCode == 200;
  }

  /// Get profile (auto-refreshes on 401)
  Future<User> getProfile() async {
    var res = await http.get(
      Uri.parse('\$_baseUrl/api/accounts/me/'),
      headers: _headers(),
    );
    if (res.statusCode == 401) {
      await refreshTokens();
      res = await http.get(
        Uri.parse('\$_baseUrl/api/accounts/me/'),
        headers: _headers(),
      );
    }
    if (res.statusCode != 200) throw Exception(res.body);
    _currentUser = User.fromJson(jsonDecode(res.body));
    return _currentUser!;
  }

  /// Logout
  Future<void> logout() async {
    _accessToken = null;
    _refreshToken = null;
    _currentUser = null;
    await _storage.deleteAll();
  }
}'''),
    ],
  ));

  // ═════════════════════════════════════════════════════════════════════
  // SECTION 15: ERROR HANDLING & BEST PRACTICES
  // ═════════════════════════════════════════════════════════════════════
  pdf.addPage(pw.MultiPage(
    pageFormat: PdfPageFormat.a4,
    margin: const pw.EdgeInsets.all(36),
    build: (ctx) => [
      _section('15. Error Handling'),
      pw.Table(
        border: pw.TableBorder.all(color: PdfColors.grey400, width: 0.5),
        columnWidths: {0: const pw.FlexColumnWidth(0.8), 1: const pw.FlexColumnWidth(1.2), 2: const pw.FlexColumnWidth(3)},
        children: [
          pw.TableRow(
            decoration: const pw.BoxDecoration(color: PdfColors.blueGrey50),
            children: [
              pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Code', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
              pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('Meaning', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
              pw.Padding(padding: const pw.EdgeInsets.all(5), child: pw.Text('When', style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 9))),
            ],
          ),
          _errorRow('200', 'OK', 'Request succeeded (login, profile, token ops)'),
          _errorRow('201', 'Created', 'Resource created (registration, profile creation)'),
          _errorRow('400', 'Bad Request', 'Validation errors (missing fields, password mismatch, duplicate email)'),
          _errorRow('401', 'Unauthorized', 'Invalid/expired token, wrong credentials'),
          _errorRow('403', 'Forbidden', 'Authenticated but wrong user type or not owner'),
          _errorRow('404', 'Not Found', 'Endpoint or profile not found'),
          _errorRow('500', 'Server Error', 'Internal server error'),
        ],
      ),

      _label('Dart API Error Model'),
      _code('''class ApiError {
  final int statusCode;
  final Map<String, List<String>> fieldErrors;
  final String? detail;

  ApiError({
    required this.statusCode,
    this.fieldErrors = const {},
    this.detail,
  });

  factory ApiError.fromResponse(http.Response response) {
    final data = jsonDecode(response.body);
    if (data is Map<String, dynamic>) {
      // Check for "detail" key (auth errors)
      if (data.containsKey('detail')) {
        return ApiError(
          statusCode: response.statusCode,
          detail: data['detail'] as String,
        );
      }
      // Field-level validation errors
      final fields = <String, List<String>>{};
      data.forEach((key, value) {
        if (value is List) {
          fields[key] = value.cast<String>();
        } else if (value is String) {
          fields[key] = [value];
        }
      });
      return ApiError(
        statusCode: response.statusCode,
        fieldErrors: fields,
      );
    }
    return ApiError(
      statusCode: response.statusCode,
      detail: response.body,
    );
  }

  String get message {
    if (detail != null) return detail!;
    return fieldErrors.entries
        .map((e) => '\${e.key}: \${e.value.join(", ")}')
        .join('\\n');
  }
}'''),

      _divider(),

      _section('16. Best Practices'),
      _body('1. Use flutter_secure_storage for tokens, never SharedPreferences.'),
      _body('2. Implement auto-refresh: intercept 401, refresh token, retry request.'),
      _body('3. Always save the NEW refresh token (tokens rotate on use).'),
      _body('4. Clear all tokens on logout and when refresh fails.'),
      _body('5. Use HTTPS in production. HTTP only for local development.'),
      _body('6. Email is the username - there is no separate username field for login.'),
      _body('7. All monetary values use ZAR (South African Rand).'),
      _body('8. After vendor registration, create vendor profile before listing products.'),
      _body('9. A vendor can only have ONE profile type (individual OR business, not both).'),
      _body('10. Vendor profiles require multipart/form-data for document uploads.'),
      _body('11. Individual vendors: owner vetting only (ID, address, selfie).'),
      _body('12. Business vendors: two-stage vetting (owner + CIPC/business entity).'),
      _body('13. store_active becomes true only after vetting is approved by admin.'),
      _body('14. Vendor categories - Individual: tuck_shop, street_vendor, local_brand, home_business, freelancer, craftsperson, other.'),
      _body('15. Business types: sole_proprietor, partnership, pty_ltd, cc, npc, cooperative, other.'),
    ],
  ));

  return pdf;
}

// ═══════════════════════════════════════════════════════════════════════
// Entry point
// ═══════════════════════════════════════════════════════════════════════

Future<void> main() async {
  final pdf = buildAuthApiDoc();
  final file = File('docs/sanoa_auth_api.pdf');
  await file.parent.create(recursive: true);
  await file.writeAsBytes(await pdf.save());
  print('PDF generated successfully: ${file.path}');
}
