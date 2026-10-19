# Vendor & Admin Notifications — Dart Service Reference

> This document covers the **vendor-facing** and **admin-facing** notification types
> added to the Sanoa platform, including tier subscriptions, inventory alerts, vetting
> results, business performance alerts, and all admin monitoring events.  
>
> For the **base notification infrastructure** (WebSocket connection, REST endpoints,
> `NotificationProvider`, bell widget, general preferences screen) see
> [`notifications_flutter_api.md`](notifications_flutter_api.md).

---

## Table of Contents

1. [What Changed / What Is New](#1-what-changed--what-is-new)
2. [Updated Dart Models](#2-updated-dart-models)
   - [NotificationType constants](#notificationtype-constants)
   - [NotificationCategory enum](#notificationcategory-enum)
   - [NotificationPreferenceModel](#notificationpreferencemodel)
3. [Vendor Notification Service](#3-vendor-notification-service)
4. [Admin Notification Service](#4-admin-notification-service)
5. [Deep-Link Router — Vendor & Admin Routes](#5-deep-link-router--vendor--admin-routes)
6. [Vendor Preferences Screen](#6-vendor-preferences-screen)
7. [Admin Preferences Screen](#7-admin-preferences-screen)
8. [Vendor Notification Type Reference](#8-vendor-notification-type-reference)
9. [Admin Notification Type Reference](#9-admin-notification-type-reference)
10. [Category Reference (Updated)](#10-category-reference-updated)
11. [data Payload Reference](#11-data-payload-reference)

---

## 1. What Changed / What Is New

### New notification types

| Group | New types |
|---|---|
| Vendor — Tier Subscription | `vendor_tier_activated` `vendor_tier_expiring` `vendor_tier_expired` `vendor_tier_past_due` `vendor_tier_cancelled` |
| Vendor — Inventory | `vendor_low_stock` `vendor_out_of_stock` |
| Vendor — Vetting | `vendor_vetting_passed` `vendor_vetting_failed` `vendor_vetting_resubmit` |
| Admin | `admin_new_business` `admin_vetting_submitted` `admin_payment_failed` `admin_tier_past_due` |

### New category

`inventory` — used for `vendor_low_stock` and `vendor_out_of_stock`.

### New preference field

`inventory_notifications` (`bool`, default `true`) added to `NotificationPreference`.

### Migration applied ✅

Migration `0002_notification_updates` has been applied:

```
python manage.py migrate notifications
# Applying notifications.0002_notification_updates... OK
```

---

## 2. Updated Dart Models

### `NotificationType` constants

Replace or extend the existing `NotificationType` class in
`lib/models/notification_model.dart` with the full version below.

```dart
// lib/models/notification_model.dart

/// Every backend notification_type string as typed Dart constants.
class NotificationType {
  // ── Customer-facing ────────────────────────────────────────────
  static const welcome                  = 'welcome';
  static const orderCreated             = 'order_created';
  static const orderProcessing          = 'order_processing';
  static const orderShipped             = 'order_shipped';
  static const orderDelivered           = 'order_delivered';
  static const orderCancelled           = 'order_cancelled';
  static const orderRefunded            = 'order_refunded';
  static const paymentSuccess           = 'payment_success';
  static const paymentFailed            = 'payment_failed';
  static const subscriptionCreated      = 'subscription_created';
  static const subscriptionExpiring     = 'subscription_expiring';
  static const subscriptionExpired      = 'subscription_expired';
  static const subscriptionPastDue      = 'subscription_past_due';
  static const creditAccountCreated     = 'credit_account_created';
  static const creditPurchaseCreated    = 'credit_purchase_created';
  static const creditRepayment          = 'credit_repayment_received';
  static const creditLowBalance         = 'credit_low_balance';
  static const creditOverdue            = 'credit_overdue';
  static const creditSuspended          = 'credit_suspended';
  static const creditUnsuspended        = 'credit_unsuspended';
  static const negotiationOffer         = 'negotiation_offer';
  static const negotiationCounter       = 'negotiation_counter';
  static const negotiationAccepted      = 'negotiation_accepted';
  static const negotiationRejected      = 'negotiation_rejected';
  static const negotiationReminder      = 'negotiation_reminder';
  static const negotiationExpired       = 'negotiation_expired';
  static const negotiationAgreed        = 'negotiation_agreed';
  static const deliveryAssigned         = 'delivery_assigned';
  static const deliveryPickedUp         = 'delivery_picked_up';
  static const deliveryInTransit        = 'delivery_in_transit';
  static const deliveryCompleted        = 'delivery_completed';
  static const vendorFollowed           = 'vendor_followed';
  static const vendorUnfollowed         = 'vendor_unfollowed';
  static const refundRequested          = 'refund_requested';
  static const refundProcessed          = 'refund_processed';
  static const disputeCreated           = 'dispute_created';
  static const disputeResolved          = 'dispute_resolved';

  // ── Vendor-facing — general ────────────────────────────────────
  static const newOrder                 = 'new_order';
  static const newFollower              = 'new_follower';
  static const unfollowedBy             = 'unfollowed_by';
  static const vendorNegotiationOffer   = 'vendor_negotiation_offer';
  static const vendorNegotiationReminder = 'vendor_negotiation_reminder';
  static const vendorPaymentReceived    = 'vendor_payment_received';
  static const verificationApproved     = 'verification_approved';
  static const verificationRejected     = 'verification_rejected';
  static const vendorOrderCancelled     = 'vendor_order_cancelled';
  static const vendorRefundRequested    = 'vendor_refund_requested';
  static const vendorDispute            = 'vendor_dispute';
  static const vendorFraudFlagged       = 'vendor_fraud_flagged';
  static const vendorFraudCleared       = 'vendor_fraud_cleared';

  // ── Vendor-facing — tier subscription (NEW) ───────────────────
  static const vendorTierActivated      = 'vendor_tier_activated';
  static const vendorTierExpiring       = 'vendor_tier_expiring';
  static const vendorTierExpired        = 'vendor_tier_expired';
  static const vendorTierPastDue        = 'vendor_tier_past_due';
  static const vendorTierCancelled      = 'vendor_tier_cancelled';

  // ── Vendor-facing — inventory (NEW) ───────────────────────────
  static const vendorLowStock           = 'vendor_low_stock';
  static const vendorOutOfStock         = 'vendor_out_of_stock';

  // ── Vendor-facing — vetting (NEW) ─────────────────────────────
  static const vendorVettingPassed      = 'vendor_vetting_passed';
  static const vendorVettingFailed      = 'vendor_vetting_failed';
  static const vendorVettingResubmit    = 'vendor_vetting_resubmit';

  // ── Admin-facing ───────────────────────────────────────────────
  static const adminNewUser             = 'admin_new_user';
  static const adminNewBusiness         = 'admin_new_business';        // NEW
  static const adminRefundPending       = 'admin_refund_pending';
  static const adminDispute             = 'admin_dispute';
  static const adminFraudHigh           = 'admin_fraud_high';
  static const adminFraudCritical       = 'admin_fraud_critical';
  static const adminCreditDefaulted     = 'admin_credit_defaulted';
  static const adminVendorPending       = 'admin_vendor_pending';
  static const adminVettingSubmitted    = 'admin_vetting_submitted';   // NEW
  static const adminPaymentFailed       = 'admin_payment_failed';      // NEW
  static const adminTierPastDue         = 'admin_tier_past_due';       // NEW
}
```

---

### `NotificationCategory` enum

Add `inventory` to the existing enum.

```dart
// lib/models/notification_model.dart  (enum section)

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
  inventory,   // NEW — stock alerts
  unknown;

  static NotificationCategory fromString(String v) {
    return NotificationCategory.values.firstWhere(
      (e) => e.name == v,
      orElse: () => NotificationCategory.unknown,
    );
  }
}
```

---

### `NotificationPreferenceModel`

Add the `inventoryNotifications` field (and wire it through `fromJson`, `toJson`, `copyWith`).

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
  final bool inventoryNotifications;   // NEW
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
    this.inventoryNotifications    = true,   // NEW
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
      inventoryNotifications:    json['inventory_notifications']    as bool? ?? true,  // NEW
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
    'inventory_notifications':    inventoryNotifications,   // NEW
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
    bool? inventoryNotifications,   // NEW
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
      inventoryNotifications:    inventoryNotifications    ?? this.inventoryNotifications,  // NEW
      inAppEnabled:              inAppEnabled              ?? this.inAppEnabled,
      pushEnabled:               pushEnabled               ?? this.pushEnabled,
    );
  }
}
```

---

## 3. Vendor Notification Service

A thin helper that wraps `NotificationProvider` with vendor-specific convenience
methods, icon resolvers, and badge helpers.

```dart
// lib/services/vendor_notification_service.dart

import 'package:flutter/material.dart';
import '../models/notification_model.dart';

/// Resolves icon, colour, and badge label for every vendor notification type.
class VendorNotificationService {

  // ── Icon resolver ──────────────────────────────────────────────

  static IconData iconFor(String type) {
    switch (type) {
      // Orders
      case NotificationType.newOrder:
        return Icons.shopping_bag_outlined;
      case NotificationType.vendorOrderCancelled:
        return Icons.remove_shopping_cart_outlined;

      // Payments
      case NotificationType.vendorPaymentReceived:
        return Icons.payments_outlined;
      case NotificationType.vendorRefundRequested:
        return Icons.assignment_return_outlined;
      case NotificationType.vendorDispute:
        return Icons.gavel_outlined;

      // Negotiations
      case NotificationType.vendorNegotiationOffer:
        return Icons.handshake_outlined;
      case NotificationType.vendorNegotiationReminder:
        return Icons.timer_outlined;
      case NotificationType.negotiationAgreed:
        return Icons.check_circle_outline;
      case NotificationType.negotiationExpired:
        return Icons.hourglass_disabled_outlined;

      // Followers / Social
      case NotificationType.newFollower:
        return Icons.person_add_outlined;
      case NotificationType.unfollowedBy:
        return Icons.person_remove_outlined;

      // Verification
      case NotificationType.verificationApproved:
        return Icons.verified_outlined;
      case NotificationType.verificationRejected:
        return Icons.cancel_outlined;

      // Vetting
      case NotificationType.vendorVettingPassed:
        return Icons.task_alt_outlined;
      case NotificationType.vendorVettingFailed:
        return Icons.highlight_off_outlined;
      case NotificationType.vendorVettingResubmit:
        return Icons.upload_file_outlined;

      // Fraud
      case NotificationType.vendorFraudFlagged:
        return Icons.gpp_bad_outlined;
      case NotificationType.vendorFraudCleared:
        return Icons.gpp_good_outlined;

      // Tier subscription
      case NotificationType.vendorTierActivated:
        return Icons.workspace_premium_outlined;
      case NotificationType.vendorTierExpiring:
        return Icons.access_alarm_outlined;
      case NotificationType.vendorTierExpired:
        return Icons.workspace_off_outlined;
      case NotificationType.vendorTierPastDue:
        return Icons.warning_amber_outlined;
      case NotificationType.vendorTierCancelled:
        return Icons.cancel_presentation_outlined;

      // Inventory
      case NotificationType.vendorLowStock:
        return Icons.inventory_2_outlined;
      case NotificationType.vendorOutOfStock:
        return Icons.production_quantity_limits_outlined;

      // Performance (via category)
      default:
        return Icons.notifications_outlined;
    }
  }

  // ── Colour resolver ────────────────────────────────────────────

  static Color colorFor(String type) {
    switch (type) {
      case NotificationType.newOrder:
        return const Color(0xFF1565C0);       // blue
      case NotificationType.vendorPaymentReceived:
        return const Color(0xFF2E7D32);       // green
      case NotificationType.vendorRefundRequested:
      case NotificationType.vendorDispute:
        return const Color(0xFFE65100);       // orange
      case NotificationType.vendorFraudFlagged:
      case NotificationType.vendorFraudCleared:
        return const Color(0xFFB71C1C);       // dark red
      case NotificationType.vendorTierActivated:
      case NotificationType.vendorTierExpiring:
      case NotificationType.vendorTierExpired:
      case NotificationType.vendorTierPastDue:
      case NotificationType.vendorTierCancelled:
        return const Color(0xFF6A1B9A);       // purple
      case NotificationType.vendorLowStock:
        return const Color(0xFFF57F17);       // amber
      case NotificationType.vendorOutOfStock:
        return const Color(0xFFC62828);       // red
      case NotificationType.vendorVettingPassed:
      case NotificationType.verificationApproved:
        return const Color(0xFF00695C);       // teal
      case NotificationType.vendorVettingFailed:
      case NotificationType.verificationRejected:
        return const Color(0xFFB71C1C);       // dark red
      case NotificationType.vendorVettingResubmit:
        return const Color(0xFF0277BD);       // light blue
      default:
        return const Color(0xFF37474F);       // grey
    }
  }

  // ── Urgency badge ──────────────────────────────────────────────

  /// Returns a short badge label shown in the tile if the event is urgent.
  /// Returns null if no badge is needed.
  static String? urgencyBadge(String type) {
    switch (type) {
      case NotificationType.vendorOutOfStock:
        return 'OUT OF STOCK';
      case NotificationType.vendorTierPastDue:
      case NotificationType.vendorTierExpired:
        return 'ACTION NEEDED';
      case NotificationType.vendorFraudFlagged:
        return 'REVIEW';
      case NotificationType.vendorDispute:
        return 'DISPUTE';
      case NotificationType.vendorVettingResubmit:
        return 'RESUBMIT';
      case NotificationType.vendorLowStock:
        return 'LOW STOCK';
      default:
        return null;
    }
  }

  // ── Category filter tabs for the vendor notifications screen ───

  /// Only the categories a vendor sees. Use as filter chips.
  static const List<(String?, String)> vendorCategoryTabs = [
    (null,           'All'),
    ('order',        'Orders'),
    ('payment',      'Payments'),
    ('negotiation',  'Offers'),
    ('inventory',    'Inventory'),
    ('subscription', 'Tier'),
    ('account',      'Account'),
    ('social',       'Followers'),
    ('fraud',        'Security'),
  ];
}
```

---

## 4. Admin Notification Service

```dart
// lib/services/admin_notification_service.dart

import 'package:flutter/material.dart';
import '../models/notification_model.dart';

/// Resolves icon, colour, and urgency badge for every admin notification type.
class AdminNotificationService {

  // ── Icon resolver ──────────────────────────────────────────────

  static IconData iconFor(String type) {
    switch (type) {
      case NotificationType.adminNewUser:
        return Icons.person_add_alt_1_outlined;
      case NotificationType.adminNewBusiness:
        return Icons.store_outlined;
      case NotificationType.adminVendorPending:
        return Icons.pending_actions_outlined;
      case NotificationType.adminVettingSubmitted:
        return Icons.assignment_outlined;
      case NotificationType.adminRefundPending:
        return Icons.assignment_return_outlined;
      case NotificationType.adminDispute:
        return Icons.gavel_outlined;
      case NotificationType.adminFraudHigh:
        return Icons.security_outlined;
      case NotificationType.adminFraudCritical:
        return Icons.gpp_bad_outlined;
      case NotificationType.adminCreditDefaulted:
        return Icons.credit_score_outlined;
      case NotificationType.adminPaymentFailed:
        return Icons.payment_outlined;
      case NotificationType.adminTierPastDue:
        return Icons.workspace_premium_outlined;
      default:
        return Icons.admin_panel_settings_outlined;
    }
  }

  // ── Colour resolver ────────────────────────────────────────────

  static Color colorFor(String type) {
    switch (type) {
      case NotificationType.adminFraudCritical:
        return const Color(0xFFB71C1C);       // dark red — critical
      case NotificationType.adminFraudHigh:
        return const Color(0xFFE53935);       // red — high
      case NotificationType.adminDispute:
      case NotificationType.adminRefundPending:
        return const Color(0xFFE65100);       // orange — needs action
      case NotificationType.adminCreditDefaulted:
        return const Color(0xFFF57F17);       // amber — financial risk
      case NotificationType.adminPaymentFailed:
        return const Color(0xFFC62828);       // red
      case NotificationType.adminTierPastDue:
        return const Color(0xFF6A1B9A);       // purple — revenue risk
      case NotificationType.adminNewBusiness:
      case NotificationType.adminVendorPending:
      case NotificationType.adminVettingSubmitted:
        return const Color(0xFF1565C0);       // blue — pending review
      case NotificationType.adminNewUser:
        return const Color(0xFF2E7D32);       // green — growth
      default:
        return const Color(0xFF4A148C);       // deep purple — admin default
    }
  }

  // ── Urgency badge ──────────────────────────────────────────────

  static String? urgencyBadge(String type) {
    switch (type) {
      case NotificationType.adminFraudCritical:
        return 'CRITICAL';
      case NotificationType.adminFraudHigh:
        return 'HIGH RISK';
      case NotificationType.adminDispute:
        return 'DISPUTE';
      case NotificationType.adminRefundPending:
        return 'APPROVAL';
      case NotificationType.adminCreditDefaulted:
        return 'DEFAULT';
      case NotificationType.adminPaymentFailed:
        return 'FAILED';
      case NotificationType.adminTierPastDue:
        return 'PAST DUE';
      case NotificationType.adminVendorPending:
      case NotificationType.adminVettingSubmitted:
      case NotificationType.adminNewBusiness:
        return 'REVIEW';
      default:
        return null;
    }
  }

  // ── Category filter tabs for the admin notifications screen ────

  static const List<(String?, String)> adminCategoryTabs = [
    (null,     'All'),
    ('admin',  'Admin'),
    ('fraud',  'Fraud'),
    ('payment','Payments'),
    ('order',  'Orders'),
    ('credit', 'Credit'),
  ];
}
```

---

## 5. Deep-Link Router — Vendor & Admin Routes

Extend your existing `NotificationRouter.navigate()` switch with all new cases.
Add these inside the `switch` block before the `default` fall-through.

```dart
// lib/navigation/notification_router.dart  — additions only
//
// Paste these cases into the existing switch(notification.notificationType) block.

// ── Vendor — tier subscription ─────────────────────────────────────────────
case NotificationType.vendorTierActivated:
case NotificationType.vendorTierExpiring:
case NotificationType.vendorTierExpired:
case NotificationType.vendorTierPastDue:
case NotificationType.vendorTierCancelled:
  // Navigate to the tier / subscription management screen
  Navigator.pushNamed(context, '/vendor/subscription/tier');
  break;

// ── Vendor — inventory ─────────────────────────────────────────────────────
case NotificationType.vendorLowStock:
case NotificationType.vendorOutOfStock:
  final productId = data['product_id'] as String?;
  if (productId != null) {
    // Open the specific product's inventory edit screen
    Navigator.pushNamed(
      context,
      '/vendor/products/inventory',
      arguments: productId,
    );
  } else {
    Navigator.pushNamed(context, '/vendor/inventory');
  }
  break;

// ── Vendor — vetting ──────────────────────────────────────────────────────
case NotificationType.vendorVettingPassed:
case NotificationType.vendorVettingFailed:
case NotificationType.vendorVettingResubmit:
  final vettingId = data['vetting_id'] as String?;
  if (vettingId != null) {
    Navigator.pushNamed(
      context,
      '/vendor/vetting/detail',
      arguments: vettingId,
    );
  } else {
    Navigator.pushNamed(context, '/vendor/vetting');
  }
  break;

// ── Admin — new business ──────────────────────────────────────────────────
case NotificationType.adminNewBusiness:
  final vendorProfileId = data['vendor_profile_id'] as String?;
  if (vendorProfileId != null) {
    Navigator.pushNamed(
      context,
      '/admin/vendors/detail',
      arguments: vendorProfileId,
    );
  } else {
    Navigator.pushNamed(context, '/admin/vendors');
  }
  break;

// ── Admin — vetting submitted ─────────────────────────────────────────────
case NotificationType.adminVettingSubmitted:
  final vettingId = data['vetting_id'] as String?;
  if (vettingId != null) {
    Navigator.pushNamed(
      context,
      '/admin/vetting/detail',
      arguments: vettingId,
    );
  } else {
    Navigator.pushNamed(context, '/admin/vetting/pending');
  }
  break;

// ── Admin — payment failed ────────────────────────────────────────────────
case NotificationType.adminPaymentFailed:
  final txId = data['transaction_id'] as String?;
  if (txId != null) {
    Navigator.pushNamed(
      context,
      '/admin/payments/detail',
      arguments: txId,
    );
  } else {
    Navigator.pushNamed(context, '/admin/payments');
  }
  break;

// ── Admin — tier past due ─────────────────────────────────────────────────
case NotificationType.adminTierPastDue:
  final vendorId = data['vendor_id'] as String?;
  if (vendorId != null) {
    Navigator.pushNamed(
      context,
      '/admin/vendors/tier',
      arguments: vendorId,
    );
  } else {
    Navigator.pushNamed(context, '/admin/tiers/past-due');
  }
  break;
```

---

## 6. Vendor Preferences Screen

Drop-in replacement for the vendor settings section — includes the new
`Inventory` toggle alongside all existing toggles.

```dart
// lib/screens/vendor/vendor_notification_preferences_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/notification_provider.dart';
import '../../models/notification_preference_model.dart';

class VendorNotificationPreferencesScreen extends StatefulWidget {
  const VendorNotificationPreferencesScreen({super.key});

  @override
  State<VendorNotificationPreferencesScreen> createState() =>
      _VendorNotificationPreferencesScreenState();
}

class _VendorNotificationPreferencesScreenState
    extends State<VendorNotificationPreferencesScreen> {
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
      return const Scaffold(
          body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Notification Settings')),
      body: ListView(
        children: [
          // ── Channels ──────────────────────────────────────────
          _section('Delivery Channels'),
          _toggle(
            label: 'In-App Notifications',
            subtitle: 'Show alerts inside the app',
            value: prefs.inAppEnabled,
            field: 'in_app_enabled',
            provider: provider,
          ),
          _toggle(
            label: 'Push Notifications',
            subtitle: 'Receive alerts when the app is closed',
            value: prefs.pushEnabled,
            field: 'push_enabled',
            provider: provider,
          ),

          // ── Business activity ─────────────────────────────────
          _section('Business Activity'),
          _toggle(
            label: 'New Orders',
            subtitle: 'Notified when a customer places an order',
            value: prefs.orderNotifications,
            field: 'order_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Payments Received',
            subtitle: 'Order payments, refund requests, disputes',
            value: prefs.paymentNotifications,
            field: 'payment_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Negotiations & Offers',
            subtitle: 'Buyer offers, counter-offers, expiry reminders',
            value: prefs.negotiationNotifications,
            field: 'negotiation_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Followers',
            subtitle: 'New followers and unfollows',
            value: prefs.socialNotifications,
            field: 'social_notifications',
            provider: provider,
          ),

          // ── Inventory ─────────────────────────────────────────
          _section('Inventory'),
          _toggle(
            label: 'Stock Alerts',
            subtitle: 'Low stock (≤ 5 units) and out-of-stock alerts',
            value: prefs.inventoryNotifications,
            field: 'inventory_notifications',
            provider: provider,
          ),

          // ── Account & Compliance ──────────────────────────────
          _section('Account & Compliance'),
          _toggle(
            label: 'Business Tier',
            subtitle: 'Tier activation, expiry warnings, payment overdue',
            value: prefs.subscriptionNotifications,
            field: 'subscription_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Verification & Vetting',
            subtitle: 'Profile verification and vetting check results',
            value: prefs.accountNotifications,
            field: 'account_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Fraud & Security Alerts',
            subtitle: 'Account review and fraud risk notifications',
            value: prefs.fraudNotifications,
            field: 'fraud_notifications',
            provider: provider,
          ),

          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _section(String title) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
        child: Text(
          title.toUpperCase(),
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: Colors.grey,
            letterSpacing: 1.2,
          ),
        ),
      );

  Widget _toggle({
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

## 7. Admin Preferences Screen

Admins only need to control the categories relevant to admin oversight.

```dart
// lib/screens/admin/admin_notification_preferences_screen.dart

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/notification_provider.dart';
import '../../models/notification_preference_model.dart';

class AdminNotificationPreferencesScreen extends StatefulWidget {
  const AdminNotificationPreferencesScreen({super.key});

  @override
  State<AdminNotificationPreferencesScreen> createState() =>
      _AdminNotificationPreferencesScreenState();
}

class _AdminNotificationPreferencesScreenState
    extends State<AdminNotificationPreferencesScreen> {
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
      return const Scaffold(
          body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Admin Notification Settings')),
      body: ListView(
        children: [
          // ── Channels ──────────────────────────────────────────
          _section('Delivery Channels'),
          _toggle(
            label: 'In-App Notifications',
            subtitle: 'Show alerts inside the app',
            value: prefs.inAppEnabled,
            field: 'in_app_enabled',
            provider: provider,
          ),
          _toggle(
            label: 'Push Notifications',
            subtitle: 'Receive alerts when the app is closed',
            value: prefs.pushEnabled,
            field: 'push_enabled',
            provider: provider,
          ),

          // ── Platform Oversight ────────────────────────────────
          _section('Platform Oversight'),
          _toggle(
            label: 'Admin Alerts',
            subtitle:
                'New users, new businesses, vendor verifications, tier payments',
            value: prefs.adminNotifications,
            field: 'admin_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Fraud & Security',
            subtitle: 'High and critical fraud risk scores',
            value: prefs.fraudNotifications,
            field: 'fraud_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Payments & Transactions',
            subtitle: 'Failed payments and transaction errors',
            value: prefs.paymentNotifications,
            field: 'payment_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Refunds & Disputes',
            subtitle: 'Refund approvals and dispute filings',
            value: prefs.paymentNotifications,
            field: 'payment_notifications',
            provider: provider,
          ),
          _toggle(
            label: 'Credit & BNPL',
            subtitle: 'Credit purchase defaults',
            value: prefs.creditNotifications,
            field: 'credit_notifications',
            provider: provider,
          ),

          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _section(String title) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
        child: Text(
          title.toUpperCase(),
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.bold,
            color: Colors.grey,
            letterSpacing: 1.2,
          ),
        ),
      );

  Widget _toggle({
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

## 8. Vendor Notification Type Reference

### Existing types (unchanged)

| `notification_type` | Triggered when |
|---|---|
| `new_order` | A customer places an order containing the vendor's product |
| `new_follower` | A customer follows the vendor's store |
| `unfollowed_by` | A customer unfollows |
| `vendor_negotiation_offer` | A buyer submits a price offer |
| `vendor_negotiation_reminder` | Agreed offer expires in < 24 hours (Celery) |
| `negotiation_agreed` | Both parties agree on a final price |
| `negotiation_expired` | Agreed-price window expired without buyer checkout |
| `vendor_payment_received` | Order payment confirmed |
| `verification_approved` | Admin approves the vendor's profile verification |
| `verification_rejected` | Admin rejects the verification |
| `vendor_order_cancelled` | A customer cancels an order |
| `vendor_refund_requested` | A customer requests a refund |
| `vendor_dispute` | A dispute is filed against the vendor's order |
| `vendor_fraud_flagged` | Account flagged for a security review |
| `vendor_fraud_cleared` | Fraud review passed — account reinstated |

### New types

| `notification_type` | Category | Triggered when |
|---|---|---|
| `vendor_tier_activated` | `subscription` | A new tier subscription is created (trialing or active) |
| `vendor_tier_expiring` | `subscription` | Tier expires within 7 days (Celery daily task) |
| `vendor_tier_expired` | `subscription` | Tier subscription status transitions to `expired` |
| `vendor_tier_past_due` | `subscription` | Tier payment is overdue (`past_due` status) |
| `vendor_tier_cancelled` | `subscription` | Vendor cancels the tier subscription |
| `vendor_low_stock` | `inventory` | A tracked product drops to ≤ 5 units |
| `vendor_out_of_stock` | `inventory` | A tracked product reaches 0 units |
| `vendor_vetting_passed` | `account` | A vetting check is approved by admin |
| `vendor_vetting_failed` | `account` | A vetting check is rejected |
| `vendor_vetting_resubmit` | `account` | Admin requests additional documents |

### Business performance alerts (via Celery)

These use existing notification types but carry `data.metric` and `data.period`
to distinguish them from regular events.

| `data.metric` | `notification_type` used | Fires when |
|---|---|---|
| `revenue_growth` | `vendor_payment_received` | Revenue grew ≥ 5 % this period |
| `revenue_decline` | `vendor_payment_received` | Revenue declined any amount |
| `no_orders` | `new_order` | Zero orders received in the period |
| `order_completion` | `new_order` | Order completion rate < 60 % |
| `cancellation_rate` | `vendor_order_cancelled` | Cancellation rate > 20 % |

Detect performance alerts in Dart:

```dart
bool isPerformanceAlert(NotificationModel n) =>
    n.data.containsKey('metric');

String performancePeriod(NotificationModel n) =>
    n.data['period'] as String? ?? 'this period';

String performanceMetric(NotificationModel n) =>
    n.data['metric'] as String? ?? '';
```

---

## 9. Admin Notification Type Reference

### Existing types (unchanged)

| `notification_type` | Triggered when |
|---|---|
| `admin_new_user` | Any new user signs up (customer or vendor) |
| `admin_refund_pending` | A customer submits a refund request needing approval |
| `admin_dispute` | A dispute is filed on the platform |
| `admin_fraud_high` | A user or vendor reaches a high fraud risk score (50–74) |
| `admin_fraud_critical` | A user or vendor reaches a critical fraud risk score (≥ 75) |
| `admin_credit_defaulted` | A BNPL credit purchase transitions to `defaulted` |
| `admin_vendor_pending` | An individual vendor registers and needs verification |

### New types

| `notification_type` | Category | Triggered when |
|---|---|---|
| `admin_new_business` | `admin` | A **business** vendor profile (`profile_type='business'`) registers |
| `admin_vetting_submitted` | `admin` | A vetting application is submitted by a vendor |
| `admin_payment_failed` | `payment` | A payment transaction fails on Paystack |
| `admin_tier_past_due` | `admin` | A vendor's tier subscription becomes past due |

### Business performance escalations (via Celery)

When vendor performance crosses a critical threshold, admins also receive an alert.

| Scenario | `notification_type` used | Threshold |
|---|---|---|
| Vendor revenue decline | `admin_vendor_pending` | Decline ≥ 30 % |
| Vendor no orders | `admin_vendor_pending` | Zero orders this period |
| Vendor low completion rate | `admin_vendor_pending` | Completion rate < 60 % |

---

## 10. Category Reference (Updated)

| `category` | Icon (Material) | Hex colour | Covers |
|---|---|---|---|
| `order` | `shopping_bag_outlined` | `#1565C0` | Order lifecycle |
| `payment` | `payment_outlined` | `#2E7D32` | Transactions, refunds, disputes |
| `subscription` | `workspace_premium_outlined` | `#6A1B9A` | Customer plans + vendor tier plans |
| `credit` | `credit_card_outlined` | `#E65100` | BNPL events |
| `negotiation` | `handshake_outlined` | `#00695C` | Offer events |
| `delivery` | `local_shipping_outlined` | `#0277BD` | Delivery tracking |
| `social` | `people_outline` | `#C62828` | Follow / unfollow |
| `fraud` | `security` | `#B71C1C` | Fraud risk |
| `account` | `person_outline` | `#37474F` | Verification, vetting, welcome |
| `admin` | `admin_panel_settings_outlined` | `#4A148C` | Admin oversight |
| `inventory` ★ NEW | `inventory_2_outlined` | `#F57F17` | Low stock & out-of-stock alerts |

Add the `inventory` case to the existing `_categoryIcon` and `_categoryColor`
helpers in `notification_tile.dart`:

```dart
// In _categoryIcon switch:
case NotificationCategory.inventory:
  return Icons.inventory_2_outlined;

// In _categoryColor switch:
case NotificationCategory.inventory:
  return const Color(0xFFF57F17);   // amber
```

---

## 11. `data` Payload Reference

Every notification carries a `data` map. Below are all keys per new type.

### Vendor tier (`vendor_tier_*`)

```json
{
  "subscription_id": "uuid",
  "tier": "Gold",
  "tier_level": 2,
  "vendor_id": "uuid"
}
```

### Vendor tier expiry warning (Celery)

```json
{
  "warning_type": "7day",
  "subscription_id": "uuid",
  "tier": "Gold",
  "tier_level": 2,
  "days_left": 5,
  "vendor_id": "uuid"
}
```

### Inventory — `vendor_low_stock` / `vendor_out_of_stock`

```json
{
  "product_id": "uuid",
  "product_name": "Organic Honey 500g",
  "sku": "HNY-500",
  "stock": 3
}
```

### Vetting — `vendor_vetting_*`

```json
{
  "vetting_id": "uuid",
  "vetting_type": "identity",
  "vendor_email": "vendor@example.com"
}
```

Possible `vetting_type` values: `identity` · `address` · `banking` · `business`

### Admin — `admin_new_business`

```json
{
  "vendor_profile_id": "uuid",
  "vendor_email": "biz@example.com",
  "profile_type": "business"
}
```

### Admin — `admin_vetting_submitted`

```json
{
  "vetting_id": "uuid",
  "vetting_type": "identity",
  "vendor_email": "vendor@example.com"
}
```

### Admin — `admin_payment_failed`

```json
{
  "transaction_id": "uuid",
  "user_id": 42,
  "amount": "1500.00",
  "intent": "order_payment",
  "reference": "PAY-REF-20260524-XYZ"
}
```

Possible `intent` values: `order_payment` · `subscription_payment` · `credit_repayment`

### Admin — `admin_tier_past_due`

```json
{
  "subscription_id": "uuid",
  "tier": "Gold",
  "tier_level": 2,
  "vendor_id": "uuid"
}
```

### Performance alert (`data.metric` present)

```json
{
  "vendor_id": "uuid",
  "metric": "revenue_decline",
  "value": "-35.2",
  "period": "this week"
}
```

Possible `metric` values:
- `revenue_growth` — `value` = percentage growth (positive float)
- `revenue_decline` — `value` = percentage decline (negative float)
- `no_orders` — `value` = `"0"`
- `order_completion` — `value` = completion rate % (float)
- `cancellation_rate` — `value` = cancellation rate % (float)

---

## Quick-Start Checklist — Vendor & Admin

- [x] Run `python manage.py migrate` on the backend (adds `inventory_notifications` column) ✅
- [ ] Replace `NotificationType` class in `notification_model.dart` with the version in [§ 2](#notificationtype-constants)
- [ ] Add `inventory` to `NotificationCategory` enum
- [ ] Add `inventoryNotifications` to `NotificationPreferenceModel` (`fromJson`, `toJson`, `copyWith`)
- [ ] Add `inventory` icon and colour cases to `NotificationTile._categoryIcon` / `_categoryColor`
- [ ] Add category filter tab `('inventory', 'Inventory')` to the vendor notifications screen
- [ ] Paste the new `case` blocks from [§ 5](#5-deep-link-router--vendor--admin-routes) into `NotificationRouter.navigate()`
- [ ] Add `VendorNotificationPreferencesScreen` to the vendor settings route
- [ ] Add `AdminNotificationPreferencesScreen` to the admin settings route
- [ ] Implement the named routes referenced in the router:
  - `/vendor/subscription/tier`
  - `/vendor/products/inventory` (takes `productId` argument)
  - `/vendor/inventory`
  - `/vendor/vetting/detail` (takes `vettingId`)
  - `/vendor/vetting`
  - `/admin/vendors/detail` (takes `vendorProfileId`)
  - `/admin/vendors`
  - `/admin/vetting/detail` (takes `vettingId`)
  - `/admin/vetting/pending`
  - `/admin/payments/detail` (takes `transactionId`)
  - `/admin/payments`
  - `/admin/vendors/tier` (takes `vendorId`)
  - `/admin/tiers/past-due`
