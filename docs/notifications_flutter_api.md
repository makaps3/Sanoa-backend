# Sanoa Notification System — Flutter / Dart Integration Guide

> **Backend base URL** `https://api.sanoa.app` (replace with your actual domain)  
> **WebSocket base URL** `wss://api.sanoa.app`  
> **Auth** JWT Bearer token — include in every REST request header and as a query param on the WebSocket connection.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Dart Models](#2-dart-models)
3. [NotificationService](#3-notificationservice)
4. [WebSocket — Real-Time Push](#4-websocket--real-time-push)
5. [REST API Endpoints](#5-rest-api-endpoints)
6. [NotificationRepository](#6-notificationrepository)
7. [State Management (Provider)](#7-state-management-provider)
8. [UI — Notification Bell + Badge](#8-ui--notification-bell--badge)
9. [UI — Full Notification Screen](#9-ui--full-notification-screen)
10. [UI — Notification Tile](#10-ui--notification-tile)
11. [Preferences Screen](#11-preferences-screen)
12. [Deep-Linking from Notifications](#12-deep-linking-from-notifications)
13. [Notification Type Reference](#13-notification-type-reference)
14. [Category Reference](#14-category-reference)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   Flutter App                        │
│                                                      │
│  NotificationProvider (ChangeNotifier)               │
│     ├── List<NotificationModel>  notifications       │
│     └── int                      unreadCount         │
│                                                      │
│  NotificationService                                 │
│     ├── WebSocketChannel    ←──── ws/notifications/  │
│     └── NotificationRepository   ←─── REST API      │
└─────────────────────────────────────────────────────┘
          │  WebSocket push              │  HTTP
          ▼                             ▼
  Backend sends JSON         REST endpoints for
  on every new event         list / mark-read / prefs
```

### Flow

1. App authenticates → stores JWT token.
2. `NotificationService.connect()` opens a WebSocket to `wss://.../ws/notifications/`.
3. Backend pushes `{type: "notification", notification: {...}}` whenever a new notification is created for the user.
4. `NotificationProvider` receives the push, inserts it at the top of the list, and increments `unreadCount`.
5. On app launch, REST `GET /api/notifications/` hydrates the full list so nothing is missed while the app was closed.

---

## 2. Dart Models

### `notification_model.dart`

```dart
// lib/models/notification_model.dart

enum NotificationCategory {
  order,
  payment,
  subscription,
  credit,
  negotiation,
  delivery,
  social,
  fraud,
  account,
  admin,
  unknown;

  static NotificationCategory fromString(String v) {
    return NotificationCategory.values.firstWhere(
      (e) => e.name == v,
      orElse: () => NotificationCategory.unknown,
    );
  }
}

// Every backend notification_type string mapped to a Dart constant.
// Use these when deciding which icon/color/route to show.
class NotificationType {
  // ── Customer ───────────────────────────────────────
  static const welcome                 = 'welcome';
  static const orderCreated            = 'order_created';
  static const orderProcessing         = 'order_processing';
  static const orderShipped            = 'order_shipped';
  static const orderDelivered          = 'order_delivered';
  static const orderCancelled          = 'order_cancelled';
  static const orderRefunded           = 'order_refunded';
  static const paymentSuccess          = 'payment_success';
  static const paymentFailed           = 'payment_failed';
  static const subscriptionCreated     = 'subscription_created';
  static const subscriptionExpiring    = 'subscription_expiring';
  static const subscriptionExpired     = 'subscription_expired';
  static const subscriptionPastDue     = 'subscription_past_due';
  static const creditAccountCreated    = 'credit_account_created';
  static const creditPurchaseCreated   = 'credit_purchase_created';
  static const creditRepayment         = 'credit_repayment_received';
  static const creditLowBalance        = 'credit_low_balance';
  static const creditOverdue           = 'credit_overdue';
  static const creditSuspended         = 'credit_suspended';
  static const creditUnsuspended       = 'credit_unsuspended';
  static const negotiationOffer        = 'negotiation_offer';
  static const negotiationCounter      = 'negotiation_counter';
  static const negotiationAccepted     = 'negotiation_accepted';
  static const negotiationRejected     = 'negotiation_rejected';
  static const negotiationReminder     = 'negotiation_reminder';
  static const negotiationExpired      = 'negotiation_expired';
  static const negotiationAgreed       = 'negotiation_agreed';
  static const deliveryAssigned        = 'delivery_assigned';
  static const deliveryPickedUp        = 'delivery_picked_up';
  static const deliveryInTransit       = 'delivery_in_transit';
  static const deliveryCompleted       = 'delivery_completed';
  static const vendorFollowed          = 'vendor_followed';
  static const vendorUnfollowed        = 'vendor_unfollowed';
  static const refundRequested         = 'refund_requested';
  static const refundProcessed         = 'refund_processed';
  static const disputeCreated          = 'dispute_created';
  static const disputeResolved         = 'dispute_resolved';
  // ── Vendor ─────────────────────────────────────────
  static const newOrder                = 'new_order';
  static const newFollower             = 'new_follower';
  static const unfollowedBy            = 'unfollowed_by';
  static const vendorNegotiationOffer  = 'vendor_negotiation_offer';
  static const vendorNegotiationReminder = 'vendor_negotiation_reminder';
  static const vendorPaymentReceived   = 'vendor_payment_received';
  static const verificationApproved    = 'verification_approved';
  static const verificationRejected    = 'verification_rejected';
  static const vendorOrderCancelled    = 'vendor_order_cancelled';
  static const vendorRefundRequested   = 'vendor_refund_requested';
  static const vendorDispute           = 'vendor_dispute';
  static const vendorFraudFlagged      = 'vendor_fraud_flagged';
  static const vendorFraudCleared      = 'vendor_fraud_cleared';
  // ── Admin ──────────────────────────────────────────
  static const adminNewUser            = 'admin_new_user';
  static const adminRefundPending      = 'admin_refund_pending';
  static const adminDispute            = 'admin_dispute';
  static const adminFraudHigh          = 'admin_fraud_high';
  static const adminFraudCritical      = 'admin_fraud_critical';
  static const adminCreditDefaulted    = 'admin_credit_defaulted';
  static const adminVendorPending      = 'admin_vendor_pending';
}

class NotificationModel {
  final String id;                   // UUID
  final String notificationType;     // one of NotificationType.*
  final NotificationCategory category;
  final String title;
  final String body;
  final Map<String, dynamic> data;   // e.g. {order_id, amount, room_id}
  final String? actorName;           // human who triggered it, or null
  final bool isRead;
  final DateTime? readAt;
  final DateTime createdAt;

  const NotificationModel({
    required this.id,
    required this.notificationType,
    required this.category,
    required this.title,
    required this.body,
    required this.data,
    this.actorName,
    required this.isRead,
    this.readAt,
    required this.createdAt,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) {
    return NotificationModel(
      id: json['id'] as String,
      notificationType: json['notification_type'] as String,
      category: NotificationCategory.fromString(json['category'] as String),
      title: json['title'] as String,
      body: json['body'] as String,
      data: Map<String, dynamic>.from(json['data'] as Map? ?? {}),
      actorName: json['actor_name'] as String?,
      isRead: json['is_read'] as bool,
      readAt: json['read_at'] != null
          ? DateTime.parse(json['read_at'] as String)
          : null,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  NotificationModel copyWith({bool? isRead, DateTime? readAt}) {
    return NotificationModel(
      id: id,
      notificationType: notificationType,
      category: category,
      title: title,
      body: body,
      data: data,
      actorName: actorName,
      isRead: isRead ?? this.isRead,
      readAt: readAt ?? this.readAt,
      createdAt: createdAt,
    );
  }
}
```

---

### `notification_preference_model.dart`

```dart
// lib/models/notification_preference_model.dart

class NotificationPreferenceModel {
  final bool orderNotifications;
  final bool paymentNotifications;
  final bool subscriptionNotifications;
  final bool creditNotifications;
  final bool negotiationNotifications;
  final bool deliveryNotifications;
  final bool socialNotifications;
  final bool fraudNotifications;
  final bool accountNotifications;
  final bool adminNotifications;
  final bool inAppEnabled;
  final bool pushEnabled;

  const NotificationPreferenceModel({
    this.orderNotifications        = true,
    this.paymentNotifications      = true,
    this.subscriptionNotifications = true,
    this.creditNotifications       = true,
    this.negotiationNotifications  = true,
    this.deliveryNotifications     = true,
    this.socialNotifications       = true,
    this.fraudNotifications        = true,
    this.accountNotifications      = true,
    this.adminNotifications        = true,
    this.inAppEnabled              = true,
    this.pushEnabled               = true,
  });

  factory NotificationPreferenceModel.fromJson(Map<String, dynamic> json) {
    return NotificationPreferenceModel(
      orderNotifications:        json['order_notifications']        as bool? ?? true,
      paymentNotifications:      json['payment_notifications']      as bool? ?? true,
      subscriptionNotifications: json['subscription_notifications'] as bool? ?? true,
      creditNotifications:       json['credit_notifications']       as bool? ?? true,
      negotiationNotifications:  json['negotiation_notifications']  as bool? ?? true,
      deliveryNotifications:     json['delivery_notifications']     as bool? ?? true,
      socialNotifications:       json['social_notifications']       as bool? ?? true,
      fraudNotifications:        json['fraud_notifications']        as bool? ?? true,
      accountNotifications:      json['account_notifications']      as bool? ?? true,
      adminNotifications:        json['admin_notifications']        as bool? ?? true,
      inAppEnabled:              json['in_app_enabled']             as bool? ?? true,
      pushEnabled:               json['push_enabled']               as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() => {
    'order_notifications':        orderNotifications,
    'payment_notifications':      paymentNotifications,
    'subscription_notifications': subscriptionNotifications,
    'credit_notifications':       creditNotifications,
    'negotiation_notifications':  negotiationNotifications,
    'delivery_notifications':     deliveryNotifications,
    'social_notifications':       socialNotifications,
    'fraud_notifications':        fraudNotifications,
    'account_notifications':      accountNotifications,
    'admin_notifications':        adminNotifications,
    'in_app_enabled':             inAppEnabled,
    'push_enabled':               pushEnabled,
  };

  NotificationPreferenceModel copyWith({
    bool? orderNotifications,
    bool? paymentNotifications,
    bool? subscriptionNotifications,
    bool? creditNotifications,
    bool? negotiationNotifications,
    bool? deliveryNotifications,
    bool? socialNotifications,
    bool? fraudNotifications,
    bool? accountNotifications,
    bool? adminNotifications,
    bool? inAppEnabled,
    bool? pushEnabled,
  }) {
    return NotificationPreferenceModel(
      orderNotifications:        orderNotifications        ?? this.orderNotifications,
      paymentNotifications:      paymentNotifications      ?? this.paymentNotifications,
      subscriptionNotifications: subscriptionNotifications ?? this.subscriptionNotifications,
      creditNotifications:       creditNotifications       ?? this.creditNotifications,
      negotiationNotifications:  negotiationNotifications  ?? this.negotiationNotifications,
      deliveryNotifications:     deliveryNotifications     ?? this.deliveryNotifications,
      socialNotifications:       socialNotifications       ?? this.socialNotifications,
      fraudNotifications:        fraudNotifications        ?? this.fraudNotifications,
      accountNotifications:      accountNotifications      ?? this.accountNotifications,
      adminNotifications:        adminNotifications        ?? this.adminNotifications,
      inAppEnabled:              inAppEnabled              ?? this.inAppEnabled,
      pushEnabled:               pushEnabled               ?? this.pushEnabled,
    );
  }
}
```

---

## 3. NotificationService

This is the single class that:
- Maintains the WebSocket connection
- Reconnects automatically on disconnection
- Exposes a `Stream<NotificationModel>` for real-time push
- Handles mark-read messages sent over the socket

```dart
// lib/services/notification_service.dart

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/io.dart';

import '../models/notification_model.dart';

class NotificationService {
  static const String _wsBaseUrl = 'wss://api.sanoa.app';
  static const Duration _reconnectDelay = Duration(seconds: 5);
  static const Duration _pingInterval   = Duration(seconds: 30);

  final String Function() _getToken; // callback that returns the current JWT

  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  Timer? _pingTimer;
  bool _disposed = false;

  final _controller = StreamController<NotificationModel>.broadcast();

  /// Listen to this stream to receive real-time notifications as they arrive.
  Stream<NotificationModel> get stream => _controller.stream;

  /// True while the socket is open.
  bool get isConnected => _channel != null;

  NotificationService({required String Function() getToken})
      : _getToken = getToken;

  // ──────────────────────────────────────────────────────────────────
  // Connect / Disconnect
  // ──────────────────────────────────────────────────────────────────

  /// Call this after the user logs in.
  void connect() {
    _disposed = false;
    _openSocket();
  }

  /// Call this when the user logs out or the app is destroyed.
  void disconnect() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _pingTimer?.cancel();
    _channel?.sink.close(WebSocketStatus.normalClosure);
    _channel = null;
  }

  void dispose() {
    disconnect();
    _controller.close();
  }

  // ──────────────────────────────────────────────────────────────────
  // Internal
  // ──────────────────────────────────────────────────────────────────

  void _openSocket() {
    if (_disposed) return;

    final token = _getToken();
    final uri = Uri.parse('$_wsBaseUrl/ws/notifications/?token=$token');

    try {
      _channel = IOWebSocketChannel.connect(
        uri,
        headers: {'Authorization': 'Bearer $token'},
      );

      _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
        cancelOnError: false,
      );

      // Keep-alive ping every 30 s
      _pingTimer?.cancel();
      _pingTimer = Timer.periodic(_pingInterval, (_) {
        _channel?.sink.add(jsonEncode({'action': 'ping'}));
      });
    } catch (e) {
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic raw) {
    if (raw is! String) return;
    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      if (json['type'] == 'notification') {
        final notif = NotificationModel.fromJson(
          json['notification'] as Map<String, dynamic>,
        );
        _controller.add(notif);
      }
    } catch (_) {
      // ignore malformed frames
    }
  }

  void _onError(Object error) {
    _channel = null;
    _scheduleReconnect();
  }

  void _onDone() {
    _channel = null;
    if (!_disposed) _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(_reconnectDelay, _openSocket);
  }

  // ──────────────────────────────────────────────────────────────────
  // Client → Server actions (over the same WebSocket)
  // ──────────────────────────────────────────────────────────────────

  /// Mark a single notification as read via the WebSocket
  /// (no extra HTTP call needed).
  void markReadWs(String notificationId) {
    _channel?.sink.add(jsonEncode({
      'action': 'mark_read',
      'id': notificationId,
    }));
  }

  /// Mark every notification as read via the WebSocket.
  void markAllReadWs() {
    _channel?.sink.add(jsonEncode({'action': 'mark_all_read'}));
  }
}
```

> **Dependencies** — add to `pubspec.yaml`:
> ```yaml
> dependencies:
>   web_socket_channel: ^2.4.0
> ```

---

## 4. WebSocket — Real-Time Push

### Connection URL

```
wss://api.sanoa.app/ws/notifications/?token=<JWT>
```

The token is read by the backend's `AuthMiddlewareStack`. Unauthenticated connections are immediately closed with code `4001`.

### Incoming frame shape

Every real-time notification arrives as a JSON string:

```json
{
  "type": "notification",
  "notification": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "notification_type": "order_created",
    "category": "order",
    "title": "Order Placed Successfully",
    "body": "Your order #ORD-20260509-000042 has been placed.",
    "data": {
      "order_id": "a1b2c3d4-...",
      "order_number": "ORD-20260509-000042"
    },
    "actor_name": null,
    "is_read": false,
    "read_at": null,
    "created_at": "2026-05-09T10:30:00.000Z"
  }
}
```

### Outgoing frame shapes (client → server)

```json
// Mark one notification read (no REST call needed)
{ "action": "mark_read", "id": "3fa85f64-5717-..." }

// Mark all read
{ "action": "mark_all_read" }
```

---

## 5. REST API Endpoints

### 5.1 List Notifications

```
GET /api/notifications/
Authorization: Bearer <token>
```

**Query parameters**

| Param | Type | Description |
|---|---|---|
| `category` | string | Filter: `order` `payment` `subscription` `credit` `negotiation` `delivery` `social` `fraud` `account` `admin` |
| `unread` | `true` | Return only unread notifications |

**Response `200 OK`**

```json
[
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "notification_type": "order_created",
    "category": "order",
    "title": "Order Placed Successfully",
    "body": "Your order #ORD-20260509-000042 has been placed and is awaiting processing.",
    "data": {
      "order_id": "a1b2c3d4-...",
      "order_number": "ORD-20260509-000042",
      "amount": "1500.00"
    },
    "actor": null,
    "actor_name": null,
    "is_read": false,
    "read_at": null,
    "created_at": "2026-05-09T10:30:00Z"
  }
]
```

---

### 5.2 Unread Count

```
GET /api/notifications/unread-count/
Authorization: Bearer <token>
```

**Response `200 OK`**
```json
{ "count": 5 }
```

---

### 5.3 Mark One Read

```
POST /api/notifications/<uuid>/mark-read/
Authorization: Bearer <token>
```

**Response `200 OK`** — returns the updated notification object (same shape as list item).

---

### 5.4 Mark All Read

```
POST /api/notifications/mark-all-read/
Authorization: Bearer <token>
```

**Response `200 OK`**
```json
{ "marked_read": 12 }
```

---

### 5.5 Delete Notification

```
DELETE /api/notifications/<uuid>/
Authorization: Bearer <token>
```

**Response `204 No Content`**

---

### 5.6 Get Preferences

```
GET /api/notifications/preferences/
Authorization: Bearer <token>
```

**Response `200 OK`**
```json
{
  "order_notifications":        true,
  "payment_notifications":      true,
  "subscription_notifications": true,
  "credit_notifications":       true,
  "negotiation_notifications":  true,
  "delivery_notifications":     true,
  "social_notifications":       true,
  "fraud_notifications":        true,
  "account_notifications":      true,
  "admin_notifications":        true,
  "in_app_enabled":             true,
  "push_enabled":               true,
  "updated_at": "2026-05-09T10:00:00Z"
}
```

---

### 5.7 Update Preferences

```
PATCH /api/notifications/preferences/
Authorization: Bearer <token>
Content-Type: application/json
```

**Request body** — send only the fields you want to change:
```json
{
  "social_notifications": false,
  "push_enabled": false
}
```

**Response `200 OK`** — full updated preferences object.

---

## 6. NotificationRepository

All HTTP calls live here. Inject your Dio / http client of choice.

```dart
// lib/repositories/notification_repository.dart

import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/notification_model.dart';
import '../models/notification_preference_model.dart';

class NotificationRepository {
  static const String _base = 'https://api.sanoa.app/api/notifications';

  final String Function() _getToken;
  final http.Client _client;

  NotificationRepository({
    required String Function() getToken,
    http.Client? client,
  })  : _getToken = getToken,
        _client = client ?? http.Client();

  Map<String, String> get _headers => {
    'Authorization': 'Bearer ${_getToken()}',
    'Content-Type': 'application/json',
  };

  // ── List ────────────────────────────────────────────────────────

  Future<List<NotificationModel>> fetchAll({
    String? category,
    bool unreadOnly = false,
  }) async {
    final params = <String, String>{};
    if (category != null) params['category'] = category;
    if (unreadOnly) params['unread'] = 'true';

    final uri = Uri.parse('$_base/').replace(queryParameters: params);
    final res = await _client.get(uri, headers: _headers);
    _checkStatus(res);
    final list = jsonDecode(res.body) as List;
    return list
        .map((e) => NotificationModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── Unread count ─────────────────────────────────────────────────

  Future<int> fetchUnreadCount() async {
    final res = await _client.get(
      Uri.parse('$_base/unread-count/'),
      headers: _headers,
    );
    _checkStatus(res);
    return (jsonDecode(res.body) as Map)['count'] as int;
  }

  // ── Mark read ────────────────────────────────────────────────────

  Future<NotificationModel> markRead(String id) async {
    final res = await _client.post(
      Uri.parse('$_base/$id/mark-read/'),
      headers: _headers,
    );
    _checkStatus(res);
    return NotificationModel.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<int> markAllRead() async {
    final res = await _client.post(
      Uri.parse('$_base/mark-all-read/'),
      headers: _headers,
    );
    _checkStatus(res);
    return (jsonDecode(res.body) as Map)['marked_read'] as int;
  }

  // ── Delete ───────────────────────────────────────────────────────

  Future<void> delete(String id) async {
    final res = await _client.delete(
      Uri.parse('$_base/$id/'),
      headers: _headers,
    );
    if (res.statusCode != 204) _checkStatus(res);
  }

  // ── Preferences ──────────────────────────────────────────────────

  Future<NotificationPreferenceModel> fetchPreferences() async {
    final res = await _client.get(
      Uri.parse('$_base/preferences/'),
      headers: _headers,
    );
    _checkStatus(res);
    return NotificationPreferenceModel.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<NotificationPreferenceModel> updatePreferences(
      Map<String, dynamic> patch) async {
    final res = await _client.patch(
      Uri.parse('$_base/preferences/'),
      headers: _headers,
      body: jsonEncode(patch),
    );
    _checkStatus(res);
    return NotificationPreferenceModel.fromJson(
        jsonDecode(res.body) as Map<String, dynamic>);
  }

  // ── Helper ───────────────────────────────────────────────────────

  void _checkStatus(http.Response res) {
    if (res.statusCode >= 400) {
      throw Exception(
          'Notification API error ${res.statusCode}: ${res.body}');
    }
  }
}
```

---

## 7. State Management (Provider)

```dart
// lib/providers/notification_provider.dart

import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/notification_model.dart';
import '../models/notification_preference_model.dart';
import '../repositories/notification_repository.dart';
import '../services/notification_service.dart';

class NotificationProvider extends ChangeNotifier {
  final NotificationRepository _repo;
  final NotificationService _service;

  List<NotificationModel> _notifications = [];
  int _unreadCount = 0;
  bool _loading = false;
  NotificationPreferenceModel? _preferences;

  StreamSubscription<NotificationModel>? _wsSub;

  List<NotificationModel> get notifications => _notifications;
  int get unreadCount => _unreadCount;
  bool get loading => _loading;
  NotificationPreferenceModel? get preferences => _preferences;

  NotificationProvider({
    required NotificationRepository repo,
    required NotificationService service,
  })  : _repo = repo,
        _service = service;

  // ── Lifecycle ────────────────────────────────────────────────────

  /// Call after user logs in.  Loads history and opens the WebSocket.
  Future<void> init() async {
    _service.connect();

    // Subscribe to real-time pushes
    _wsSub = _service.stream.listen(_onPush);

    // Load existing notifications from REST
    await loadAll();
  }

  /// Call when user logs out.
  void teardown() {
    _wsSub?.cancel();
    _service.disconnect();
    _notifications = [];
    _unreadCount = 0;
    notifyListeners();
  }

  @override
  void dispose() {
    _wsSub?.cancel();
    _service.dispose();
    super.dispose();
  }

  // ── Data loading ─────────────────────────────────────────────────

  Future<void> loadAll({String? category, bool unreadOnly = false}) async {
    _loading = true;
    notifyListeners();
    try {
      _notifications = await _repo.fetchAll(
        category: category,
        unreadOnly: unreadOnly,
      );
      _unreadCount = _notifications.where((n) => !n.isRead).length;
    } finally {
      _loading = false;
      notifyListeners();
    }
  }

  Future<void> refreshUnreadCount() async {
    _unreadCount = await _repo.fetchUnreadCount();
    notifyListeners();
  }

  // ── Real-time push ───────────────────────────────────────────────

  void _onPush(NotificationModel notif) {
    // Insert at front (newest first)
    _notifications = [notif, ..._notifications];
    if (!notif.isRead) _unreadCount++;
    notifyListeners();
  }

  // ── Mark read ────────────────────────────────────────────────────

  Future<void> markRead(String id) async {
    // Optimistic UI update
    _updateLocally(id, isRead: true);

    // Use WebSocket — no extra HTTP round-trip
    _service.markReadWs(id);

    // Also call REST to persist if WS is not connected
    if (!_service.isConnected) await _repo.markRead(id);
  }

  Future<void> markAllRead() async {
    // Optimistic
    _notifications = _notifications
        .map((n) => n.copyWith(isRead: true))
        .toList();
    _unreadCount = 0;
    notifyListeners();

    _service.markAllReadWs();
    if (!_service.isConnected) await _repo.markAllRead();
  }

  // ── Delete ───────────────────────────────────────────────────────

  Future<void> delete(String id) async {
    _notifications.removeWhere((n) => n.id == id);
    _unreadCount = _notifications.where((n) => !n.isRead).length;
    notifyListeners();
    await _repo.delete(id);
  }

  // ── Preferences ──────────────────────────────────────────────────

  Future<void> loadPreferences() async {
    _preferences = await _repo.fetchPreferences();
    notifyListeners();
  }

  Future<void> updatePreference(String field, bool value) async {
    _preferences = await _repo.updatePreferences({field: value});
    notifyListeners();
  }

  // ── Helper ───────────────────────────────────────────────────────

  void _updateLocally(String id, {required bool isRead}) {
    final idx = _notifications.indexWhere((n) => n.id == id);
    if (idx == -1) return;
    final old = _notifications[idx];
    if (old.isRead == isRead) return;
    _notifications[idx] = old.copyWith(isRead: isRead);
    _unreadCount = _notifications.where((n) => !n.isRead).length;
    notifyListeners();
  }
}
```

### Register in `main.dart`

```dart
// lib/main.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/notification_provider.dart';
import 'repositories/notification_repository.dart';
import 'services/notification_service.dart';
import 'services/auth_service.dart'; // your existing auth service

void main() {
  runApp(
    MultiProvider(
      providers: [
        // ... your other providers
        ChangeNotifierProvider<NotificationProvider>(
          create: (ctx) {
            final auth = ctx.read<AuthService>();
            final repo = NotificationRepository(getToken: () => auth.token ?? '');
            final ws   = NotificationService(getToken: () => auth.token ?? '');
            return NotificationProvider(repo: repo, service: ws);
          },
        ),
      ],
      child: const SanoaApp(),
    ),
  );
}
```

### Connect after login

```dart
// Inside your login success handler (e.g. AuthProvider or LoginBloc)

final notifProvider = context.read<NotificationProvider>();
await notifProvider.init();   // opens WS + loads history
```

### Disconnect on logout

```dart
context.read<NotificationProvider>().teardown();
```

---

## 8. UI — Notification Bell + Badge

Place this in your `AppBar` actions.

```dart
// lib/widgets/notification_bell.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/notification_provider.dart';
import '../screens/notifications_screen.dart';

class NotificationBell extends StatelessWidget {
  const NotificationBell({super.key});

  @override
  Widget build(BuildContext context) {
    final count = context.watch<NotificationProvider>().unreadCount;

    return Stack(
      children: [
        IconButton(
          icon: const Icon(Icons.notifications_outlined),
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const NotificationsScreen()),
          ),
        ),
        if (count > 0)
          Positioned(
            right: 6,
            top: 6,
            child: Container(
              padding: const EdgeInsets.all(2),
              constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
              decoration: BoxDecoration(
                color: Colors.red,
                borderRadius: BorderRadius.circular(9),
              ),
              child: Text(
                count > 99 ? '99+' : '$count',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
                textAlign: TextAlign.center,
              ),
            ),
          ),
      ],
    );
  }
}
```

Usage in AppBar:

```dart
AppBar(
  title: const Text('Home'),
  actions: const [NotificationBell()],
)
```

---

## 9. UI — Full Notification Screen

```dart
// lib/screens/notifications_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/notification_provider.dart';
import '../widgets/notification_tile.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  String? _activeCategory;

  static const _categories = [
    (null,           'All'),
    ('order',        'Orders'),
    ('payment',      'Payments'),
    ('credit',       'Credit'),
    ('delivery',     'Delivery'),
    ('negotiation',  'Negotiate'),
    ('social',       'Social'),
    ('subscription', 'Plan'),
    ('fraud',        'Security'),
  ];

  @override
  void initState() {
    super.initState();
    // Reload on screen open
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationProvider>().loadAll(
            category: _activeCategory,
          );
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          if (provider.unreadCount > 0)
            TextButton(
              onPressed: () => provider.markAllRead(),
              child: const Text('Mark all read',
                  style: TextStyle(color: Colors.white)),
            ),
        ],
      ),
      body: Column(
        children: [
          // Category filter chips
          SizedBox(
            height: 48,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: _categories.length,
              itemBuilder: (ctx, i) {
                final (value, label) = _categories[i];
                final selected = _activeCategory == value;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(label),
                    selected: selected,
                    onSelected: (_) {
                      setState(() => _activeCategory = value);
                      provider.loadAll(category: value);
                    },
                  ),
                );
              },
            ),
          ),
          const Divider(height: 1),
          // List
          Expanded(
            child: provider.loading
                ? const Center(child: CircularProgressIndicator())
                : provider.notifications.isEmpty
                    ? const Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.notifications_none, size: 64,
                                color: Colors.grey),
                            SizedBox(height: 12),
                            Text('No notifications yet',
                                style: TextStyle(color: Colors.grey)),
                          ],
                        ),
                      )
                    : RefreshIndicator(
                        onRefresh: () => provider.loadAll(
                            category: _activeCategory),
                        child: ListView.separated(
                          itemCount: provider.notifications.length,
                          separatorBuilder: (_, __) =>
                              const Divider(height: 1),
                          itemBuilder: (ctx, i) {
                            final notif = provider.notifications[i];
                            return NotificationTile(
                              notification: notif,
                              onTap: () => _handleTap(notif),
                              onDismiss: () => provider.delete(notif.id),
                            );
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  void _handleTap(notification) {
    if (!notification.isRead) {
      context.read<NotificationProvider>().markRead(notification.id);
    }
    // Deep-link based on type — see Section 12
    NotificationRouter.navigate(context, notification);
  }
}
```

---

## 10. UI — Notification Tile

```dart
// lib/widgets/notification_tile.dart

import 'package:flutter/material.dart';
import 'package:timeago/timeago.dart' as timeago;
import '../models/notification_model.dart';

class NotificationTile extends StatelessWidget {
  final NotificationModel notification;
  final VoidCallback onTap;
  final VoidCallback onDismiss;

  const NotificationTile({
    super.key,
    required this.notification,
    required this.onTap,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final n = notification;
    return Dismissible(
      key: ValueKey(n.id),
      direction: DismissDirection.endToStart,
      background: Container(
        color: Colors.red,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 16),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      onDismissed: (_) => onDismiss(),
      child: InkWell(
        onTap: onTap,
        child: Container(
          color: n.isRead ? null : Theme.of(context).primaryColor.withOpacity(0.06),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Category icon
              CircleAvatar(
                radius: 22,
                backgroundColor: _categoryColor(n.category).withOpacity(0.15),
                child: Icon(
                  _categoryIcon(n.category),
                  color: _categoryColor(n.category),
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            n.title,
                            style: TextStyle(
                              fontWeight: n.isRead
                                  ? FontWeight.normal
                                  : FontWeight.bold,
                              fontSize: 14,
                            ),
                          ),
                        ),
                        if (!n.isRead)
                          Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: Theme.of(context).primaryColor,
                              shape: BoxShape.circle,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      n.body,
                      style: const TextStyle(
                          fontSize: 13, color: Colors.black54),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      timeago.format(n.createdAt),
                      style: const TextStyle(
                          fontSize: 11, color: Colors.black38),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  static IconData _categoryIcon(NotificationCategory cat) {
    switch (cat) {
      case NotificationCategory.order:        return Icons.shopping_bag_outlined;
      case NotificationCategory.payment:      return Icons.payment_outlined;
      case NotificationCategory.subscription: return Icons.star_border;
      case NotificationCategory.credit:       return Icons.credit_card_outlined;
      case NotificationCategory.negotiation:  return Icons.handshake_outlined;
      case NotificationCategory.delivery:     return Icons.local_shipping_outlined;
      case NotificationCategory.social:       return Icons.people_outline;
      case NotificationCategory.fraud:        return Icons.security;
      case NotificationCategory.account:      return Icons.person_outline;
      case NotificationCategory.admin:        return Icons.admin_panel_settings_outlined;
      default:                                return Icons.notifications_outlined;
    }
  }

  static Color _categoryColor(NotificationCategory cat) {
    switch (cat) {
      case NotificationCategory.order:        return const Color(0xFF1565C0);
      case NotificationCategory.payment:      return const Color(0xFF2E7D32);
      case NotificationCategory.subscription: return const Color(0xFF6A1B9A);
      case NotificationCategory.credit:       return const Color(0xFFE65100);
      case NotificationCategory.negotiation:  return const Color(0xFF00695C);
      case NotificationCategory.delivery:     return const Color(0xFF0277BD);
      case NotificationCategory.social:       return const Color(0xFFC62828);
      case NotificationCategory.fraud:        return const Color(0xFFB71C1C);
      case NotificationCategory.account:      return const Color(0xFF37474F);
      case NotificationCategory.admin:        return const Color(0xFF4A148C);
      default:                                return Colors.grey;
    }
  }
}
```

> Add `timeago` to `pubspec.yaml`:
> ```yaml
> dependencies:
>   timeago: ^3.6.1
> ```

---

## 11. Preferences Screen

```dart
// lib/screens/notification_preferences_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/notification_provider.dart';
import '../models/notification_preference_model.dart';

class NotificationPreferencesScreen extends StatefulWidget {
  const NotificationPreferencesScreen({super.key});

  @override
  State<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends State<NotificationPreferencesScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<NotificationProvider>().loadPreferences();
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationProvider>();
    final prefs = provider.preferences;

    if (prefs == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Notification Settings')),
      body: ListView(
        children: [
          _sectionHeader('Channels'),
          _prefSwitch(
            label: 'In-App Notifications',
            subtitle: 'Show notifications inside the app',
            value: prefs.inAppEnabled,
            field: 'in_app_enabled',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Push Notifications',
            subtitle: 'Send notifications when app is closed',
            value: prefs.pushEnabled,
            field: 'push_enabled',
            provider: provider,
          ),
          _sectionHeader('Categories'),
          _prefSwitch(
            label: 'Orders',
            subtitle: 'Order placed, shipped, delivered, cancelled',
            value: prefs.orderNotifications,
            field: 'order_notifications',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Payments',
            subtitle: 'Payment success, failures, refunds, disputes',
            value: prefs.paymentNotifications,
            field: 'payment_notifications',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Subscriptions',
            subtitle: 'Plan renewals and expiry warnings',
            value: prefs.subscriptionNotifications,
            field: 'subscription_notifications',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Credit / BNPL',
            subtitle: 'Credit account, purchases, repayments, overdue alerts',
            value: prefs.creditNotifications,
            field: 'credit_notifications',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Negotiations',
            subtitle: 'Offers, counter-offers, 24-hour reminders',
            value: prefs.negotiationNotifications,
            field: 'negotiation_notifications',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Delivery',
            subtitle: 'Driver assigned, picked up, in transit, delivered',
            value: prefs.deliveryNotifications,
            field: 'delivery_notifications',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Social',
            subtitle: 'Follow and unfollow activity',
            value: prefs.socialNotifications,
            field: 'social_notifications',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Security & Fraud',
            subtitle: 'Account review alerts',
            value: prefs.fraudNotifications,
            field: 'fraud_notifications',
            provider: provider,
          ),
          _prefSwitch(
            label: 'Account',
            subtitle: 'Verification status, welcome messages',
            value: prefs.accountNotifications,
            field: 'account_notifications',
            provider: provider,
          ),
        ],
      ),
    );
  }

  Widget _sectionHeader(String title) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
        child: Text(title.toUpperCase(),
            style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: Colors.grey,
                letterSpacing: 1.2)),
      );

  Widget _prefSwitch({
    required String label,
    required String subtitle,
    required bool value,
    required String field,
    required NotificationProvider provider,
  }) =>
      SwitchListTile(
        title: Text(label),
        subtitle: Text(subtitle,
            style: const TextStyle(fontSize: 12, color: Colors.black54)),
        value: value,
        onChanged: (v) => provider.updatePreference(field, v),
      );
}
```

---

## 12. Deep-Linking from Notifications

When a user taps a notification, navigate to the relevant screen based on `notification_type` and the `data` payload.

```dart
// lib/navigation/notification_router.dart

import 'package:flutter/material.dart';
import '../models/notification_model.dart';

class NotificationRouter {
  static void navigate(
      BuildContext context, NotificationModel notification) {
    final data = notification.data;

    switch (notification.notificationType) {

      // ── Orders ─────────────────────────────────────────────
      case NotificationType.orderCreated:
      case NotificationType.orderProcessing:
      case NotificationType.orderShipped:
      case NotificationType.orderDelivered:
      case NotificationType.orderCancelled:
      case NotificationType.orderRefunded:
      case NotificationType.newOrder:
      case NotificationType.vendorOrderCancelled:
        final orderId = data['order_id'] as String?;
        if (orderId != null) {
          Navigator.pushNamed(context, '/orders/detail',
              arguments: orderId);
        }
        break;

      // ── Payments ───────────────────────────────────────────
      case NotificationType.paymentSuccess:
      case NotificationType.paymentFailed:
      case NotificationType.vendorPaymentReceived:
        final txId = data['transaction_id'] as String?;
        if (txId != null) {
          Navigator.pushNamed(context, '/payments/detail',
              arguments: txId);
        }
        break;

      case NotificationType.refundRequested:
      case NotificationType.refundProcessed:
      case NotificationType.vendorRefundRequested:
      case NotificationType.adminRefundPending:
        final refundId = data['refund_id'] as String?;
        if (refundId != null) {
          Navigator.pushNamed(context, '/payments/refunds/detail',
              arguments: refundId);
        }
        break;

      case NotificationType.disputeCreated:
      case NotificationType.disputeResolved:
      case NotificationType.vendorDispute:
      case NotificationType.adminDispute:
        final disputeId = data['dispute_id'] as String?;
        if (disputeId != null) {
          Navigator.pushNamed(context, '/payments/disputes/detail',
              arguments: disputeId);
        }
        break;

      // ── Subscriptions ──────────────────────────────────────
      case NotificationType.subscriptionCreated:
      case NotificationType.subscriptionExpiring:
      case NotificationType.subscriptionExpired:
      case NotificationType.subscriptionPastDue:
        Navigator.pushNamed(context, '/subscriptions');
        break;

      // ── Credit ─────────────────────────────────────────────
      case NotificationType.creditAccountCreated:
      case NotificationType.creditLowBalance:
      case NotificationType.creditSuspended:
      case NotificationType.creditUnsuspended:
        Navigator.pushNamed(context, '/credit/account');
        break;

      case NotificationType.creditPurchaseCreated:
      case NotificationType.creditRepayment:
      case NotificationType.creditOverdue:
      case NotificationType.adminCreditDefaulted:
        final purchaseId = data['purchase_id'] as String?;
        if (purchaseId != null) {
          Navigator.pushNamed(context, '/credit/purchases/detail',
              arguments: purchaseId);
        } else {
          Navigator.pushNamed(context, '/credit/purchases');
        }
        break;

      // ── Negotiations ───────────────────────────────────────
      case NotificationType.negotiationOffer:
      case NotificationType.negotiationCounter:
      case NotificationType.negotiationAccepted:
      case NotificationType.negotiationRejected:
      case NotificationType.negotiationReminder:
      case NotificationType.negotiationExpired:
      case NotificationType.negotiationAgreed:
      case NotificationType.vendorNegotiationOffer:
      case NotificationType.vendorNegotiationReminder:
        final roomId = data['room_id'] as String?;
        if (roomId != null) {
          Navigator.pushNamed(context, '/negotiations/room',
              arguments: roomId);
        }
        break;

      // ── Delivery ───────────────────────────────────────────
      case NotificationType.deliveryAssigned:
      case NotificationType.deliveryPickedUp:
      case NotificationType.deliveryInTransit:
      case NotificationType.deliveryCompleted:
        final orderId = data['order_id'] as String?;
        if (orderId != null) {
          Navigator.pushNamed(context, '/orders/tracking',
              arguments: orderId);
        }
        break;

      // ── Social ─────────────────────────────────────────────
      case NotificationType.vendorFollowed:
      case NotificationType.vendorUnfollowed:
        final vendorId = data['vendor_id'] as String?;
        if (vendorId != null) {
          Navigator.pushNamed(context, '/vendor/profile',
              arguments: vendorId);
        }
        break;

      case NotificationType.newFollower:
      case NotificationType.unfollowedBy:
        Navigator.pushNamed(context, '/vendor/followers');
        break;

      // ── Account / Verification ─────────────────────────────
      case NotificationType.welcome:
        Navigator.pushNamed(context, '/home');
        break;

      case NotificationType.verificationApproved:
      case NotificationType.verificationRejected:
      case NotificationType.vendorFraudFlagged:
      case NotificationType.vendorFraudCleared:
        Navigator.pushNamed(context, '/vendor/profile/verification');
        break;

      // ── Fraud / Admin ──────────────────────────────────────
      case NotificationType.adminFraudHigh:
      case NotificationType.adminFraudCritical:
        final profileId = data['profile_id'] as String?;
        Navigator.pushNamed(context, '/admin/fraud',
            arguments: profileId);
        break;

      case NotificationType.adminVendorPending:
        Navigator.pushNamed(context, '/admin/vendors/pending');
        break;

      default:
        // Fallback — stay on notifications screen
        break;
    }
  }
}
```

---

## 13. Notification Type Reference

| `notification_type` | Who receives it | Triggered by |
|---|---|---|
| `welcome` | Customer / Vendor | Account signup |
| `order_created` | Customer | New order placed |
| `order_processing` | Customer | Order status → processing |
| `order_shipped` | Customer | Order status → shipped |
| `order_delivered` | Customer | Order status → delivered |
| `order_cancelled` | Customer | Order cancelled |
| `order_refunded` | Customer | Refund processed |
| `payment_success` | Customer | Transaction success |
| `payment_failed` | Customer | Transaction failed |
| `subscription_created` | Customer | New subscription |
| `subscription_expiring` | Customer | 3 days before renewal (Celery) |
| `subscription_expired` | Customer | Subscription cancelled/expired |
| `subscription_past_due` | Customer | Subscription payment overdue |
| `credit_account_created` | Customer | Credit account opened |
| `credit_purchase_created` | Customer | BNPL purchase created |
| `credit_repayment_received` | Customer | Repayment recorded |
| `credit_low_balance` | Customer | < 20% credit available (Celery) |
| `credit_overdue` | Customer | Credit purchase past due date (Celery) |
| `credit_suspended` | Customer | Account suspended due to overdue |
| `credit_unsuspended` | Customer | Suspension lifted |
| `negotiation_offer` | Customer | Vendor/AI counter-offer received |
| `negotiation_counter` | Customer | Counter-offer from vendor |
| `negotiation_accepted` | Customer | Offer accepted |
| `negotiation_rejected` | Customer | Offer rejected |
| `negotiation_reminder` | Customer | 24 hr before offer expiry (Celery) |
| `negotiation_expired` | Customer / Vendor | Agreed offer expired without checkout |
| `negotiation_agreed` | Customer | Negotiation reached agreement |
| `delivery_assigned` | Customer | Driver accepted job |
| `delivery_picked_up` | Customer | Driver picked up order |
| `delivery_in_transit` | Customer | Order in transit |
| `delivery_completed` | Customer | Order delivered |
| `vendor_followed` | Customer | Followed a vendor |
| `vendor_unfollowed` | Customer | Unfollowed a vendor |
| `refund_requested` | Customer | Refund request submitted |
| `refund_processed` | Customer | Refund approved and processed |
| `dispute_created` | Customer | Dispute filed |
| `dispute_resolved` | Customer | Dispute resolved |
| `new_order` | **Vendor** | Customer placed an order |
| `new_follower` | **Vendor** | Customer followed the store |
| `unfollowed_by` | **Vendor** | Customer unfollowed |
| `vendor_negotiation_offer` | **Vendor** | Buyer submitted an offer |
| `vendor_negotiation_reminder` | **Vendor** | 24 hr before offer expiry (Celery) |
| `vendor_payment_received` | **Vendor** | Payment received for order |
| `verification_approved` | **Vendor** | Verification approved by admin |
| `verification_rejected` | **Vendor** | Verification rejected |
| `vendor_order_cancelled` | **Vendor** | Customer cancelled an order |
| `vendor_refund_requested` | **Vendor** | Customer requested refund |
| `vendor_dispute` | **Vendor** | Dispute filed against their order |
| `vendor_fraud_flagged` | **Vendor** | Account flagged for fraud review |
| `vendor_fraud_cleared` | **Vendor** | Fraud review passed |
| `admin_new_user` | **Admin** | New user/vendor registered |
| `admin_refund_pending` | **Admin** | Refund request needs approval |
| `admin_dispute` | **Admin** | New dispute filed |
| `admin_fraud_high` | **Admin** | Risk score 50–74 detected |
| `admin_fraud_critical` | **Admin** | Risk score 75–100 detected |
| `admin_credit_defaulted` | **Admin** | Credit purchase defaulted |
| `admin_vendor_pending` | **Admin** | Vendor registered, needs review |

---

## 14. Category Reference

| `category` | Icon (Material) | Color | Covers |
|---|---|---|---|
| `order` | `shopping_bag_outlined` | Blue `#1565C0` | All order lifecycle events |
| `payment` | `payment_outlined` | Green `#2E7D32` | Transactions, refunds, disputes |
| `subscription` | `star_border` | Purple `#6A1B9A` | Plan events |
| `credit` | `credit_card_outlined` | Orange `#E65100` | BNPL events |
| `negotiation` | `handshake_outlined` | Teal `#00695C` | Offer events |
| `delivery` | `local_shipping_outlined` | Light Blue `#0277BD` | Delivery tracking |
| `social` | `people_outline` | Red `#C62828` | Follow/unfollow |
| `fraud` | `security` | Dark Red `#B71C1C` | Fraud alerts |
| `account` | `person_outline` | Grey `#37474F` | Welcome, verification |
| `admin` | `admin_panel_settings_outlined` | Deep Purple `#4A148C` | Admin-only alerts |

---

## Quick-Start Checklist

- [ ] Add `web_socket_channel: ^2.4.0` and `timeago: ^3.6.1` to `pubspec.yaml`
- [ ] Create `lib/models/notification_model.dart`
- [ ] Create `lib/models/notification_preference_model.dart`
- [ ] Create `lib/repositories/notification_repository.dart`
- [ ] Create `lib/services/notification_service.dart`
- [ ] Create `lib/providers/notification_provider.dart`
- [ ] Register `NotificationProvider` in `MultiProvider` inside `main.dart`
- [ ] Call `provider.init()` after successful login
- [ ] Call `provider.teardown()` after logout
- [ ] Add `NotificationBell` to `AppBar.actions`
- [ ] Create `NotificationsScreen` and route to it from the bell
- [ ] Create `NotificationPreferencesScreen` and add to settings
- [ ] Implement `NotificationRouter.navigate()` routes to match your app's named routes
