# Platform Admin Service

## Overview

The Platform Admin module manages admin users, role-based permissions, and the employee invitation flow.

**Base URL:** `/api/platform-admin/`

**Authentication:** All endpoints require a valid Bearer JWT token, except where noted.

---

## Roles & Permissions

| Role | Key | Description |
|------|-----|-------------|
| Super Admin | `super_admin` | Full platform control, manages other admins |
| Operations Admin | `ops_admin` | Drivers, orders, inventory, delivery |
| Support Admin | `support_admin` | Customers, orders, refunds, disputes |
| Finance Admin | `finance_admin` | Payments, refunds, payouts, analytics |

### Permission Keys

| Key | Super | Ops | Support | Finance |
|-----|:-----:|:---:|:-------:|:-------:|
| `manage_admins` | ✓ | | | |
| `manage_drivers` | ✓ | ✓ | | |
| `manage_vendors` | ✓ | | | |
| `manage_customers` | ✓ | | ✓ | |
| `manage_orders` | ✓ | ✓ | ✓ | |
| `manage_payments` | ✓ | | | ✓ |
| `manage_refunds` | ✓ | | ✓ | ✓ |
| `manage_disputes` | ✓ | | ✓ | ✓ |
| `manage_subscriptions` | ✓ | | | ✓ |
| `manage_inventory` | ✓ | ✓ | | |
| `manage_delivery` | ✓ | ✓ | | |
| `manage_notifications` | ✓ | ✓ | ✓ | |
| `view_analytics` | ✓ | ✓ | | ✓ |
| `system_configuration` | ✓ | | | |
| `manage_support` | ✓ | | ✓ | |
| `view_audit_logs` | ✓ | ✓ | ✓ | ✓ |
| `financial_access` | ✓ | | | ✓ |
| `security_management` | ✓ | | | |

---

## Registration Flow (Self-register)

```
1. POST /api/accounts/register/         { user_type: "admin" }
2. POST /api/otp/verify/                { email, code, purpose: "verification" }
3. POST /api/auth/token/                { email, password }
4. POST /api/platform-admin/profile/   { role, department, work_email, ... }
```

## Invitation Flow (Super Admin invites employee)

```
1. Super Admin: POST /api/platform-admin/invitations/send/      { email, role, department }
2. Invitee:     POST /api/accounts/register/                    { user_type: "admin" }
3. Invitee:     POST /api/otp/verify/                           { email, code }
4. Invitee:     POST /api/auth/token/                           { email, password }
5. Invitee:     POST /api/platform-admin/invitations/<token>/accept/  { work_email, role_title }
```

---

## Endpoints

### My Profile

#### GET `/api/platform-admin/profile/`
Returns the authenticated admin's profile.

#### POST `/api/platform-admin/profile/`
Creates an admin profile after account registration + OTP verification.

**Request body:**
```json
{
  "role": "ops_admin",
  "department": "operations",
  "role_title": "Head of Logistics",
  "work_email": "ops@company.com",
  "profile_photo": "<file>"
}
```

#### PUT/PATCH `/api/platform-admin/profile/`
Updates own non-sensitive fields (`role_title`, `work_email`, `profile_photo`, `department`).

---

### Team Management (Super Admin only)

#### GET `/api/platform-admin/team/`
Lists all admin profiles.

#### GET `/api/platform-admin/team/<id>/`
Retrieves a specific admin profile by UUID.

#### PATCH `/api/platform-admin/team/<id>/`
Updates a team member's basic fields.

#### DELETE `/api/platform-admin/team/<id>/`
Deletes a team member (cannot delete own profile).

#### POST `/api/platform-admin/team/<id>/suspend/`
Suspends a team member (sets status to `suspended`).

#### POST `/api/platform-admin/team/<id>/activate/`
Reactivates a suspended team member.

#### PATCH `/api/platform-admin/team/<id>/permissions/`
Overrides individual permission keys on a team member's profile.

**Request body:**
```json
{
  "permissions": {
    "manage_payments": true,
    "financial_access": true
  }
}
```

#### POST `/api/platform-admin/team/<id>/permissions/`
Resets a team member's permissions to their role defaults.

---

### Invitations

#### POST `/api/platform-admin/invitations/send/`
Super Admin sends an invitation (expires after 7 days).

**Request body:**
```json
{
  "email": "newadmin@company.com",
  "role": "support_admin",
  "department": "support"
}
```

#### GET `/api/platform-admin/invitations/`
Lists all invitations (Super Admin only).

#### GET `/api/platform-admin/invitations/<token>/`
Retrieves an invitation by token (public — used by invitee to preview).

#### POST `/api/platform-admin/invitations/<token>/accept/`
Invitee accepts the invitation and creates their admin profile.

**Request body:**
```json
{
  "work_email": "mywork@company.com",
  "role_title": "Support Lead",
  "profile_photo": "<file>"
}
```

#### POST `/api/platform-admin/invitations/<id>/revoke/`
Super Admin revokes a pending invitation by UUID.

---

## Data Models (Dart)

```dart
class AdminProfile {
  final String id;
  final String userId;
  final String userEmail;
  final String fullName;
  final String role;
  final String department;
  final String roleTitle;
  final String workEmail;
  final String? profilePhoto;
  final String status;
  final String? invitedBy;
  final String? invitedByEmail;
  final Map<String, bool> permissions;
  final DateTime? lastLoginAt;
  final DateTime createdAt;
  final DateTime updatedAt;

  AdminProfile({
    required this.id,
    required this.userId,
    required this.userEmail,
    required this.fullName,
    required this.role,
    required this.department,
    required this.roleTitle,
    required this.workEmail,
    this.profilePhoto,
    required this.status,
    this.invitedBy,
    this.invitedByEmail,
    required this.permissions,
    this.lastLoginAt,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AdminProfile.fromJson(Map<String, dynamic> json) {
    return AdminProfile(
      id: json['id'],
      userId: json['user'].toString(),
      userEmail: json['user_email'],
      fullName: json['full_name'] ?? '',
      role: json['role'],
      department: json['department'],
      roleTitle: json['role_title'] ?? '',
      workEmail: json['work_email'],
      profilePhoto: json['profile_photo'],
      status: json['status'],
      invitedBy: json['invited_by']?.toString(),
      invitedByEmail: json['invited_by_email'],
      permissions: Map<String, bool>.from(json['permissions'] ?? {}),
      lastLoginAt: json['last_login_at'] != null
          ? DateTime.parse(json['last_login_at'])
          : null,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }

  bool hasPermission(String key) => permissions[key] ?? false;
  bool get isSuperAdmin => role == 'super_admin';
  bool get isActive => status == 'active';
}


class AdminInvitation {
  final String id;
  final String invitedBy;
  final String invitedByEmail;
  final String email;
  final String role;
  final String department;
  final String token;
  final String status;
  final DateTime expiresAt;
  final String? acceptedBy;
  final String? acceptedByEmail;
  final DateTime createdAt;

  AdminInvitation({
    required this.id,
    required this.invitedBy,
    required this.invitedByEmail,
    required this.email,
    required this.role,
    required this.department,
    required this.token,
    required this.status,
    required this.expiresAt,
    this.acceptedBy,
    this.acceptedByEmail,
    required this.createdAt,
  });

  factory AdminInvitation.fromJson(Map<String, dynamic> json) {
    return AdminInvitation(
      id: json['id'],
      invitedBy: json['invited_by'].toString(),
      invitedByEmail: json['invited_by_email'],
      email: json['email'],
      role: json['role'],
      department: json['department'],
      token: json['token'],
      status: json['status'],
      expiresAt: DateTime.parse(json['expires_at']),
      acceptedBy: json['accepted_by']?.toString(),
      acceptedByEmail: json['accepted_by_email'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }

  bool get isPending => status == 'pending';
  bool get isExpired => DateTime.now().isAfter(expiresAt);
  bool get isValid => isPending && !isExpired;
}
```

---

## Service Class (Dart)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class PlatformAdminService {
  final String token;
  final String baseUrl;

  PlatformAdminService({required this.token, this.baseUrl = 'http://your-api.com'});

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  Future<Map<String, dynamic>> _get(String path) async {
    final res = await http.get(_uri(path), headers: _headers);
    return jsonDecode(res.body);
  }

  Future<Map<String, dynamic>> _post(String path, Map<String, dynamic> body) async {
    final res = await http.post(_uri(path), headers: _headers, body: jsonEncode(body));
    return jsonDecode(res.body);
  }

  Future<Map<String, dynamic>> _patch(String path, Map<String, dynamic> body) async {
    final res = await http.patch(_uri(path), headers: _headers, body: jsonEncode(body));
    return jsonDecode(res.body);
  }

  Future<bool> _delete(String path) async {
    final res = await http.delete(_uri(path), headers: _headers);
    return res.statusCode == 204;
  }

  // ── My Profile ──────────────────────────────────────────────

  Future<AdminProfile> getProfile() async {
    final data = await _get('/api/platform-admin/profile/');
    return AdminProfile.fromJson(data);
  }

  Future<AdminProfile> createProfile({
    required String role,
    required String department,
    required String workEmail,
    String roleTitle = '',
  }) async {
    final data = await _post('/api/platform-admin/profile/', {
      'role': role,
      'department': department,
      'work_email': workEmail,
      if (roleTitle.isNotEmpty) 'role_title': roleTitle,
    });
    return AdminProfile.fromJson(data);
  }

  Future<AdminProfile> updateProfile({
    String? roleTitle,
    String? workEmail,
    String? department,
  }) async {
    final body = <String, dynamic>{};
    if (roleTitle != null) body['role_title'] = roleTitle;
    if (workEmail != null) body['work_email'] = workEmail;
    if (department != null) body['department'] = department;
    final data = await _patch('/api/platform-admin/profile/', body);
    return AdminProfile.fromJson(data);
  }

  // ── Team Management (Super Admin) ────────────────────────────

  Future<List<AdminProfile>> getTeam() async {
    final data = await _get('/api/platform-admin/team/');
    return (data as List).map((e) => AdminProfile.fromJson(e)).toList();
  }

  Future<AdminProfile> getTeamMember(String id) async {
    final data = await _get('/api/platform-admin/team/$id/');
    return AdminProfile.fromJson(data);
  }

  Future<AdminProfile> updateTeamMember(String id, Map<String, dynamic> body) async {
    final data = await _patch('/api/platform-admin/team/$id/', body);
    return AdminProfile.fromJson(data);
  }

  Future<bool> deleteTeamMember(String id) =>
      _delete('/api/platform-admin/team/$id/');

  Future<AdminProfile> suspendMember(String id) async {
    final data = await _post('/api/platform-admin/team/$id/suspend/', {});
    return AdminProfile.fromJson(data);
  }

  Future<AdminProfile> activateMember(String id) async {
    final data = await _post('/api/platform-admin/team/$id/activate/', {});
    return AdminProfile.fromJson(data);
  }

  Future<AdminProfile> overridePermissions(
    String id,
    Map<String, bool> permissions,
  ) async {
    final data = await _patch(
      '/api/platform-admin/team/$id/permissions/',
      {'permissions': permissions},
    );
    return AdminProfile.fromJson(data);
  }

  Future<AdminProfile> resetPermissions(String id) async {
    final data = await _post('/api/platform-admin/team/$id/permissions/', {});
    return AdminProfile.fromJson(data);
  }

  // ── Invitations ──────────────────────────────────────────────

  Future<AdminInvitation> sendInvitation({
    required String email,
    required String role,
    required String department,
  }) async {
    final data = await _post('/api/platform-admin/invitations/send/', {
      'email': email,
      'role': role,
      'department': department,
    });
    return AdminInvitation.fromJson(data);
  }

  Future<List<AdminInvitation>> getInvitations() async {
    final data = await _get('/api/platform-admin/invitations/');
    return (data as List).map((e) => AdminInvitation.fromJson(e)).toList();
  }

  Future<AdminInvitation> getInvitationByToken(String token) async {
    final data = await _get('/api/platform-admin/invitations/$token/');
    return AdminInvitation.fromJson(data);
  }

  Future<AdminProfile> acceptInvitation({
    required String token,
    required String workEmail,
    String roleTitle = '',
  }) async {
    final data = await _post('/api/platform-admin/invitations/$token/accept/', {
      'work_email': workEmail,
      if (roleTitle.isNotEmpty) 'role_title': roleTitle,
    });
    return AdminProfile.fromJson(data);
  }

  Future<AdminInvitation> revokeInvitation(String id) async {
    final data = await _post('/api/platform-admin/invitations/$id/revoke/', {});
    return AdminInvitation.fromJson(data);
  }
}
```

---

## Sample Response — `AdminProfile`

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "user": "8fd2b3c1-0001-0001-0001-000000000001",
  "user_email": "ops@company.com",
  "full_name": "Jane Doe",
  "role": "ops_admin",
  "department": "operations",
  "role_title": "Head of Logistics",
  "work_email": "jane.doe@company.com",
  "profile_photo": "/media/admin/photos/jane.jpg",
  "status": "active",
  "invited_by": "1a2b3c4d-0001-0001-0001-000000000001",
  "invited_by_email": "super@company.com",
  "permissions": {
    "manage_admins": false,
    "manage_drivers": true,
    "manage_vendors": false,
    "manage_customers": false,
    "manage_orders": true,
    "manage_payments": false,
    "manage_refunds": false,
    "manage_disputes": false,
    "manage_subscriptions": false,
    "manage_inventory": true,
    "manage_delivery": true,
    "manage_notifications": true,
    "view_analytics": true,
    "system_configuration": false,
    "manage_support": false,
    "view_audit_logs": true,
    "financial_access": false,
    "security_management": false
  },
  "last_login_at": "2026-05-18T08:30:00Z",
  "created_at": "2026-05-01T10:00:00Z",
  "updated_at": "2026-05-18T08:30:00Z"
}
```

## Sample Response — `AdminInvitation`

```json
{
  "id": "9ab12cd3-0001-0001-0001-000000000002",
  "invited_by": "1a2b3c4d-0001-0001-0001-000000000001",
  "invited_by_email": "super@company.com",
  "email": "newadmin@company.com",
  "role": "support_admin",
  "department": "support",
  "token": "abc123xyz_secure_token_here",
  "status": "pending",
  "expires_at": "2026-05-25T10:00:00Z",
  "accepted_by": null,
  "accepted_by_email": null,
  "created_at": "2026-05-18T10:00:00Z"
}
```

---

## Error Responses

| Status | Scenario |
|--------|----------|
| 400 | Profile already exists, invalid invitation, non-boolean permission value |
| 403 | Wrong user type, email mismatch on invitation, not Super Admin |
| 404 | Profile, team member, or invitation not found |
