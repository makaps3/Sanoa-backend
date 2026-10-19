# Negotiations API — Flutter Integration Reference

**Base URL:** `http://<host>/api/negotiations/`  
**WebSocket URL:** `ws://<host>/ws/negotiations/<room_uuid>/?token=<JWT_access_token>`  
**Auth:** All REST endpoints require `Authorization: Bearer <access_token>` header.

---

## Table of Contents

1. [Dart Models](#1-dart-models)
2. [Customer Endpoints](#2-customer-endpoints)
3. [Vendor Endpoints](#3-vendor-endpoints)
4. [Admin Notes](#4-admin-notes)
5. [WebSocket — Real-Time Chat](#5-websocket--real-time-chat)
6. [Enums & Constants](#6-enums--constants)
7. [Full User Flow](#7-full-user-flow)
8. [Error Handling](#8-error-handling)

## Endpoint Quick Reference

| Method | URL | Role | Description |
|--------|-----|------|-------------|
| `POST` | `/start/` | Customer | Create or resume a negotiation room |
| `GET` | `/rooms/` | Customer | My open rooms (filterable by status) |
| `GET` | `/rooms/<uuid>/` | Customer / Vendor | Room detail |
| `GET` | `/rooms/<uuid>/messages/` | Customer / Vendor | Message history |
| `GET` | `/rooms/<uuid>/offers/` | Customer / Vendor | **Offer history for a room** |
| `GET` | `/active/` | Customer | **Active agreed deals (within 24 h window)** |
| `GET` | `/history/` | Customer | **Past negotiations (expired / agreed / cancelled)** |
| `GET` | `/vendor/rooms/` | Vendor | Incoming negotiations |
| `POST` | `/vendor/rooms/<uuid>/switch-mode/` | Vendor | Toggle AI ↔ manual |
| `GET` | `/vendor/active/` | Vendor | **Active agreed deals (within 24 h window)** |
| `GET` | `/vendor/history/` | Vendor | **Past negotiations (expired / agreed / cancelled)** |
| `GET` | `/policy/my-policy/` | Vendor | Get pricing rules |
| `POST` | `/policy/set-policy/` | Vendor | Create / update pricing rules |

---

## 1. Dart Models

### 1.1 PricePolicy

```dart
class PricePolicy {
  final int id;
  final String vendor;         // VendorProfile ID
  final String vendorEmail;
  final double maxMarkupPercent;   // 0–50, default 15.00
  final double maxDiscountPercent; // 0–50, default 10.00
  final double minFloorPercent;    // 0–50, default 5.00
  final bool autoNegotiate;
  final bool isActive;
  final DateTime createdAt;
  final DateTime updatedAt;

  PricePolicy({
    required this.id,
    required this.vendor,
    required this.vendorEmail,
    required this.maxMarkupPercent,
    required this.maxDiscountPercent,
    required this.minFloorPercent,
    required this.autoNegotiate,
    required this.isActive,
    required this.createdAt,
    required this.updatedAt,
  });

  factory PricePolicy.fromJson(Map<String, dynamic> json) => PricePolicy(
    id: json['id'],
    vendor: json['vendor'].toString(),
    vendorEmail: json['vendor_email'] ?? '',
    maxMarkupPercent: double.parse(json['max_markup_percent'].toString()),
    maxDiscountPercent: double.parse(json['max_discount_percent'].toString()),
    minFloorPercent: double.parse(json['min_floor_percent'].toString()),
    autoNegotiate: json['auto_negotiate'] ?? true,
    isActive: json['is_active'] ?? true,
    createdAt: DateTime.parse(json['created_at']),
    updatedAt: DateTime.parse(json['updated_at']),
  );
}
```

---

### 1.2 NegotiationRoom

```dart
enum NegotiationMode { ai, manual }
enum NegotiationStatus { open, agreed, expired, cancelled }

class NegotiationRoom {
  final String id;             // UUID
  final String product;        // Product ID (UUID)
  final String productName;
  final double productPrice;
  final String? productImage;  // absolute URL or null
  final String buyer;          // User ID
  final String buyerEmail;
  final String vendor;         // VendorProfile ID
  final String vendorName;
  final NegotiationMode mode;
  final NegotiationStatus status;
  final double? agreedPrice;
  final DateTime? offerExpiresAt;  // buyer must checkout before this
  final NegotiationOffer? latestOffer;
  final int unreadCount;
  /// Seconds left before the agreed checkout window closes.
  /// Non-null only when status == agreed. Returns 0 when window has passed.
  final int? timeRemainingSeconds;
  final DateTime createdAt;
  final DateTime updatedAt;

  NegotiationRoom({
    required this.id,
    required this.product,
    required this.productName,
    required this.productPrice,
    this.productImage,
    required this.buyer,
    required this.buyerEmail,
    required this.vendor,
    required this.vendorName,
    required this.mode,
    required this.status,
    this.agreedPrice,
    this.offerExpiresAt,
    this.latestOffer,
    required this.unreadCount,
    this.timeRemainingSeconds,
    required this.createdAt,
    required this.updatedAt,
  });

  factory NegotiationRoom.fromJson(Map<String, dynamic> json) => NegotiationRoom(
    id: json['id'],
    product: json['product'].toString(),
    productName: json['product_name'] ?? '',
    productPrice: double.parse(json['product_price'].toString()),
    productImage: json['product_image'],
    buyer: json['buyer'].toString(),
    buyerEmail: json['buyer_email'] ?? '',
    vendor: json['vendor'].toString(),
    vendorName: json['vendor_name'] ?? '',
    mode: json['mode'] == 'manual' ? NegotiationMode.manual : NegotiationMode.ai,
    status: _parseStatus(json['status']),
    agreedPrice: json['agreed_price'] != null
        ? double.parse(json['agreed_price'].toString())
        : null,
    offerExpiresAt: json['offer_expires_at'] != null
        ? DateTime.parse(json['offer_expires_at'])
        : null,
    latestOffer: json['latest_offer'] != null
        ? NegotiationOffer.fromJson(json['latest_offer'])
        : null,
    unreadCount: json['unread_count'] ?? 0,
    timeRemainingSeconds: json['time_remaining_seconds'] as int?,
    createdAt: DateTime.parse(json['created_at']),
    updatedAt: DateTime.parse(json['updated_at']),
  );

  static NegotiationStatus _parseStatus(String s) => switch (s) {
    'agreed'    => NegotiationStatus.agreed,
    'expired'   => NegotiationStatus.expired,
    'cancelled' => NegotiationStatus.cancelled,
    _           => NegotiationStatus.open,
  };
}
```

---

### 1.3 NegotiationMessage

```dart
enum MessageSenderType { buyer, vendor, ai, system }
enum MessageType { text, offer, counterOffer, accepted, rejected, expired, system }

class NegotiationMessage {
  final String id;            // UUID
  final String room;          // NegotiationRoom ID
  final MessageSenderType senderType;
  final String? sender;       // User ID (null for AI/system)
  final String? senderEmail;
  final String content;
  final MessageType messageType;
  final double? priceValue;   // set for offer / counter_offer / accepted
  final bool isSeen;
  final DateTime? seenAt;
  final DateTime createdAt;

  NegotiationMessage({
    required this.id,
    required this.room,
    required this.senderType,
    this.sender,
    this.senderEmail,
    required this.content,
    required this.messageType,
    this.priceValue,
    required this.isSeen,
    this.seenAt,
    required this.createdAt,
  });

  factory NegotiationMessage.fromJson(Map<String, dynamic> json) => NegotiationMessage(
    id: json['id'],
    room: json['room'].toString(),
    senderType: _parseSenderType(json['sender_type']),
    sender: json['sender']?.toString(),
    senderEmail: json['sender_email'],
    content: json['content'] ?? '',
    messageType: _parseMessageType(json['message_type']),
    priceValue: json['price_value'] != null
        ? double.parse(json['price_value'].toString())
        : null,
    isSeen: json['is_seen'] ?? false,
    seenAt: json['seen_at'] != null ? DateTime.parse(json['seen_at']) : null,
    createdAt: DateTime.parse(json['created_at']),
  );

  static MessageSenderType _parseSenderType(String s) => switch (s) {
    'vendor' => MessageSenderType.vendor,
    'ai'     => MessageSenderType.ai,
    'system' => MessageSenderType.system,
    _        => MessageSenderType.buyer,
  };

  static MessageType _parseMessageType(String s) => switch (s) {
    'offer'         => MessageType.offer,
    'counter_offer' => MessageType.counterOffer,
    'accepted'      => MessageType.accepted,
    'rejected'      => MessageType.rejected,
    'expired'       => MessageType.expired,
    'system'        => MessageType.system,
    _               => MessageType.text,
  };
}
```

---

### 1.4 NegotiationOffer

```dart
enum OfferOfferedBy { buyer, vendor, ai }
enum OfferStatus { pending, accepted, rejected, countered, expired }

class NegotiationOffer {
  final String id;                    // UUID
  final String room;                  // NegotiationRoom ID
  final OfferOfferedBy offeredBy;
  final double originalPrice;
  final double offeredPrice;
  final double? counterOfferPrice;
  final OfferStatus status;
  final double? aiConfidence;         // 0.0–1.0, null if not AI
  final String? aiAction;             // "accept" | "counter" | "reject" | null
  final int roundNumber;
  final DateTime expiresAt;
  final DateTime createdAt;
  final DateTime? respondedAt;

  NegotiationOffer({
    required this.id,
    required this.room,
    required this.offeredBy,
    required this.originalPrice,
    required this.offeredPrice,
    this.counterOfferPrice,
    required this.status,
    this.aiConfidence,
    this.aiAction,
    required this.roundNumber,
    required this.expiresAt,
    required this.createdAt,
    this.respondedAt,
  });

  factory NegotiationOffer.fromJson(Map<String, dynamic> json) => NegotiationOffer(
    id: json['id'],
    room: json['room'].toString(),
    offeredBy: _parseOfferedBy(json['offered_by']),
    originalPrice: double.parse(json['original_price'].toString()),
    offeredPrice: double.parse(json['offered_price'].toString()),
    counterOfferPrice: json['counter_offer_price'] != null
        ? double.parse(json['counter_offer_price'].toString())
        : null,
    status: _parseOfferStatus(json['status']),
    aiConfidence: json['ai_confidence'] != null
        ? (json['ai_confidence'] as num).toDouble()
        : null,
    aiAction: json['ai_action'],
    roundNumber: json['round_number'] ?? 1,
    expiresAt: DateTime.parse(json['expires_at']),
    createdAt: DateTime.parse(json['created_at']),
    respondedAt: json['responded_at'] != null
        ? DateTime.parse(json['responded_at'])
        : null,
  );

  static OfferOfferedBy _parseOfferedBy(String s) => switch (s) {
    'vendor' => OfferOfferedBy.vendor,
    'ai'     => OfferOfferedBy.ai,
    _        => OfferOfferedBy.buyer,
  };

  static OfferStatus _parseOfferStatus(String s) => switch (s) {
    'accepted'  => OfferStatus.accepted,
    'rejected'  => OfferStatus.rejected,
    'countered' => OfferStatus.countered,
    'expired'   => OfferStatus.expired,
    _           => OfferStatus.pending,
  };
}
```

---

## 2. Customer Endpoints

> All customer endpoints require `user_type == "customer"`.

---

### 2.1 Start a Negotiation

```
POST /api/negotiations/start/
```

Creates a new room or returns the existing open room for that product.  
After this call, open the WebSocket using the returned `id`.

**Request body:**
```json
{
  "product_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "mode": "ai"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_id` | UUID string | yes | The product to negotiate on |
| `mode` | `"ai"` \| `"manual"` | no (default `"ai"`) | AI bot or live vendor chat |

**Response `201 Created` (new room) / `200 OK` (existing room):**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "product": "prod-uuid",
  "product_name": "iPhone 15 Pro",
  "product_price": "22999.00",
  "product_image": "http://host/media/products/iphone.jpg",
  "buyer": 42,
  "buyer_email": "buyer@example.com",
  "vendor": "vendor-profile-uuid",
  "vendor_name": "TechStore SA",
  "mode": "ai",
  "status": "open",
  "agreed_price": null,
  "offer_expires_at": null,
  "latest_offer": null,
  "unread_count": 0,
  "created_at": "2026-05-06T10:00:00Z",
  "updated_at": "2026-05-06T10:00:00Z"
}
```

**Error responses:**

| Status | Body |
|--------|------|
| `403` | `{"error": "Only customers can start negotiations."}` |
| `404` | `{"error": "Product not found or not active."}` |

---

### 2.2 List My Negotiation Rooms

```
GET /api/negotiations/rooms/
GET /api/negotiations/rooms/?status=open
```

Returns the authenticated buyer's rooms, newest first.

**Query params:**

| Param | Values | Description |
|-------|--------|-------------|
| `status` | `open` \| `agreed` \| `expired` \| `cancelled` | Filter by status |

**Response `200 OK`:** Paginated list of `NegotiationRoom` objects (same shape as 2.1).

```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [ { ...NegotiationRoom }, ... ]
}
```

---

### 2.3 Get Room Detail

```
GET /api/negotiations/rooms/<room_uuid>/
```

Accessible to both the buyer and the vendor of that room.

**Response `200 OK`:** Single `NegotiationRoom` object.

**Error:**

| Status | Body |
|--------|------|
| `404` | Room not found or you are not the buyer/vendor |

---

### 2.4 Get Room Message History

```
GET /api/negotiations/rooms/<room_uuid>/messages/
```

Returns all messages in chronological order (oldest first).  
Use this to pre-populate the chat before connecting to WebSocket.

**Response `200 OK`:** Paginated list of `NegotiationMessage` objects.

```json
{
  "count": 12,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "msg-uuid",
      "room": "room-uuid",
      "sender_type": "ai",
      "sender": null,
      "sender_email": null,
      "content": "Hi! I'm the AI negotiator. What price did you have in mind?",
      "message_type": "system",
      "price_value": null,
      "is_seen": true,
      "seen_at": "2026-05-06T10:01:00Z",
      "created_at": "2026-05-06T10:00:05Z"
    },
    {
      "id": "msg-uuid-2",
      "room": "room-uuid",
      "sender_type": "buyer",
      "sender": 42,
      "sender_email": "buyer@example.com",
      "content": "I'd like to buy this for R19500.00",
      "message_type": "offer",
      "price_value": "19500.00",
      "is_seen": true,
      "seen_at": "2026-05-06T10:02:00Z",
      "created_at": "2026-05-06T10:01:30Z"
    }
  ]
}
```

---

### 2.5 Offers History for a Room

```
GET /api/negotiations/rooms/<room_uuid>/offers/
```

Returns every price proposal made in a room (buyer offers, vendor/AI counters) in chronological order. Use this to render the full offer back-and-forth timeline.

Accessible to both the buyer and the vendor of that room.

**Response `200 OK`:** Paginated list of `NegotiationOffer` objects.

```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "offer-uuid-1",
      "room": "room-uuid",
      "offered_by": "buyer",
      "original_price": "22999.00",
      "offered_price": "18000.00",
      "counter_offer_price": "21000.00",
      "status": "countered",
      "ai_confidence": null,
      "ai_action": null,
      "round_number": 1,
      "expires_at": "2026-05-07T10:01:30Z",
      "created_at": "2026-05-06T10:01:30Z",
      "responded_at": "2026-05-06T10:01:32Z"
    },
    {
      "id": "offer-uuid-2",
      "room": "room-uuid",
      "offered_by": "ai",
      "original_price": "22999.00",
      "offered_price": "21000.00",
      "counter_offer_price": null,
      "status": "countered",
      "ai_confidence": 0.82,
      "ai_action": "counter",
      "round_number": 2,
      "expires_at": "2026-05-07T10:01:32Z",
      "created_at": "2026-05-06T10:01:32Z",
      "responded_at": "2026-05-06T10:02:00Z"
    },
    {
      "id": "offer-uuid-3",
      "room": "room-uuid",
      "offered_by": "buyer",
      "original_price": "22999.00",
      "offered_price": "21000.00",
      "counter_offer_price": null,
      "status": "accepted",
      "ai_confidence": null,
      "ai_action": null,
      "round_number": 3,
      "expires_at": "2026-05-07T10:02:00Z",
      "created_at": "2026-05-06T10:02:00Z",
      "responded_at": "2026-05-06T10:02:01Z"
    }
  ]
}
```

---

### 2.6 Active Deals (within 24-hour checkout window)

```
GET /api/negotiations/active/
```

Returns the buyer's rooms where `status == "agreed"` **and** `offer_expires_at` is still in the future. Sorted by most urgent (soonest expiry first).

Use `time_remaining_seconds` to drive a countdown timer in the UI.

**Response `200 OK`:**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "room-uuid",
      "product_name": "iPhone 15 Pro",
      "product_price": "22999.00",
      "agreed_price": "21000.00",
      "status": "agreed",
      "offer_expires_at": "2026-05-07T10:02:01Z",
      "time_remaining_seconds": 72400,
      "mode": "ai",
      "unread_count": 0,
      ...
    }
  ]
}
```

> **Flutter tip:** Use `time_remaining_seconds` to start a `Timer.periodic` countdown. When it hits 0, refresh the room — it will have moved to `status: "expired"`.

---

### 2.7 Negotiation History (Past Negotiations)

```
GET /api/negotiations/history/
GET /api/negotiations/history/?status=expired
GET /api/negotiations/history/?status=agreed
GET /api/negotiations/history/?status=cancelled
```

Returns the buyer's closed/completed negotiations — everything except `open` rooms. Sorted by most recently updated first.

| `status` filter | What you get |
|-----------------|--------------|
| _(none)_ | All non-open rooms (expired + agreed + cancelled) |
| `agreed` | Rooms where a price was successfully agreed (buyer checked out or window passed) |
| `expired` | Rooms where the negotiation or checkout window timed out |
| `cancelled` | Rooms manually cancelled |

**Response `200 OK`:** Paginated list of `NegotiationRoom` objects (same shape as 2.1, with `time_remaining_seconds: null` for non-agreed rooms).

> For agreed rooms that have already passed their checkout window, `time_remaining_seconds` will be `0`.

---

## 3. Vendor Endpoints

> All vendor endpoints require `user_type == "vendor"`.

---

### 3.1 List Incoming Negotiation Rooms

```
GET /api/negotiations/vendor/rooms/
GET /api/negotiations/vendor/rooms/?status=open
```

Returns all rooms where this vendor's products are being negotiated, newest first.

**Query params:**

| Param | Values | Description |
|-------|--------|-------------|
| `status` | `open` \| `agreed` \| `expired` \| `cancelled` | Filter by status |

**Response `200 OK`:** Paginated list of `NegotiationRoom` objects.

---

### 3.2 Switch Negotiation Mode

```
POST /api/negotiations/vendor/rooms/<room_uuid>/switch-mode/
```

Toggles the room between `ai` and `manual` mode. Only works on `open` rooms.

**Request body:** _(empty)_

**Response `200 OK`:**
```json
{
  "room_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "mode": "manual"
}
```

**Error responses:**

| Status | Body |
|--------|------|
| `404` | Room not found, not yours, or not open |

---

### 3.3 Active Deals (within 24-hour checkout window)

```
GET /api/negotiations/vendor/active/
```

Returns the vendor's rooms where `status == "agreed"` and `offer_expires_at` is still in the future. Sorted by most urgent first.

Same response shape as [2.6 Active Deals](#26-active-deals-within-24-hour-checkout-window).

> Use this to show the vendor a "deals awaiting checkout" badge/list.

---

### 3.4 Negotiation History (Past Negotiations)

```
GET /api/negotiations/vendor/history/
GET /api/negotiations/vendor/history/?status=expired
GET /api/negotiations/vendor/history/?status=agreed
GET /api/negotiations/vendor/history/?status=cancelled
```

Returns the vendor's closed negotiations — everything except `open` rooms. Sorted by most recently updated first.

Same response shape and filter behaviour as [2.7 Negotiation History](#27-negotiation-history-past-negotiations).

> Use this to display the vendor's deal history, win/loss record, and past pricing.

---

### 3.5 Get My Price Policy


```
GET /api/negotiations/policy/my-policy/
```

**Response `200 OK` (policy exists):**
```json
{
  "id": 1,
  "vendor": "vendor-profile-uuid",
  "vendor_email": "vendor@example.com",
  "max_markup_percent": "15.00",
  "max_discount_percent": "10.00",
  "min_floor_percent": "5.00",
  "auto_negotiate": true,
  "is_active": true,
  "created_at": "2026-05-01T09:00:00Z",
  "updated_at": "2026-05-06T08:00:00Z"
}
```

**Response `200 OK` (no policy set yet):**
```json
{
  "status": "none",
  "message": "No policy set. Defaults apply.",
  "defaults": {
    "max_markup_percent": "15.00",
    "max_discount_percent": "10.00",
    "min_floor_percent": "5.00",
    "auto_negotiate": true
  }
}
```

**Error:**

| Status | Body |
|--------|------|
| `403` | `{"error": "Only vendors can manage price policies."}` |
| `403` | `{"error": "Vendor profile required."}` |

---

### 3.6 Create or Update Price Policy

```
POST /api/negotiations/policy/set-policy/
```

Creates the policy if it doesn't exist, or updates it (upsert).

**Request body:**
```json
{
  "max_markup_percent": 20.00,
  "max_discount_percent": 15.00,
  "min_floor_percent": 8.00,
  "auto_negotiate": true
}
```

| Field | Type | Required | Range | Default |
|-------|------|----------|-------|---------|
| `max_markup_percent` | decimal | no | 0–50 | 15.00 |
| `max_discount_percent` | decimal | no | 0–50 | 10.00 |
| `min_floor_percent` | decimal | no | 0–50 | 5.00 |
| `auto_negotiate` | boolean | no | — | true |

> **`min_floor_percent`** is the hard floor. The AI will never accept any offer below `(product_price − min_floor_percent%)`, regardless of other settings.

**Response `200 OK`:** Full `PricePolicy` object (same shape as 3.3).

**Validation errors `400 Bad Request`:**
```json
{
  "max_markup_percent": ["max_markup_percent must be between 0 and 50."]
}
```

---

## 4. Admin Notes

Admins access the negotiations data exclusively through the **Django Admin panel** at `/admin/negotiations/`.  
There are no dedicated admin REST endpoints — admin actions (edit, delete, override) are performed directly via the admin interface.

**Admin-accessible models:**

| Admin URL | Model | What to manage |
|-----------|-------|----------------|
| `/admin/negotiations/pricepolicy/` | `PricePolicy` | View/edit all vendor pricing rules |
| `/admin/negotiations/negotiationroom/` | `NegotiationRoom` | View all rooms, override status, agreed_price |
| `/admin/negotiations/negotiationmessage/` | `NegotiationMessage` | Audit message history |
| `/admin/negotiations/negotiationoffer/` | `NegotiationOffer` | Inspect all offers, AI decisions |

**For Flutter admin dashboards**, use the standard `GET` room/message endpoints with an admin-level token — the `NegotiationRoomDetailView` and `RoomMessagesView` both accept buyer **or** vendor tokens. For full admin listing across all vendors, you would need a separate admin-specific endpoint (not yet implemented — use Django admin for now).

---

## 5. WebSocket — Real-Time Chat

### 5.1 Connection

```
ws://<host>/ws/negotiations/<room_uuid>/?token=<JWT_access_token>
```

- Use the `id` returned from `POST /start/` as `<room_uuid>`.
- Pass the JWT **access token** as a query parameter (not in the header — WebSocket doesn't support headers easily).
- Both buyer and vendor connect to the same URL. The server determines role from the token.

**Close codes:**

| Code | Meaning |
|------|---------|
| `4001` | Invalid or missing JWT token |
| `4004` | Room not found or you are not the buyer/vendor |

---

### 5.2 On Connect — History Event

Immediately after the WebSocket is accepted, the server sends a `history` event:

```json
{
  "type": "history",
  "room_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "mode": "ai",
  "status": "open",
  "product_price": "22999.00",
  "messages": [
    {
      "id": "msg-uuid",
      "sender_type": "ai",
      "sender_id": null,
      "content": "Hi! I'm the AI negotiator...",
      "message_type": "system",
      "price_value": null,
      "is_seen": false,
      "created_at": "2026-05-06T10:00:05Z"
    }
  ]
}
```

> The `messages` array contains up to the last **100 messages**. For older history use `GET /rooms/<uuid>/messages/`.

---

### 5.3 Client → Server Events

Send JSON over the WebSocket. The `type` field routes the event.

#### Send a text message
```json
{ "type": "message", "content": "Is this price negotiable?" }
```
> Max content length: 2000 characters.

#### Make a price offer *(buyer only)*
```json
{ "type": "offer", "price": 19500.00 }
```
> Triggers the AI response automatically if `mode == "ai"`.

#### Make a counter offer *(buyer countering AI / vendor in manual mode)*
```json
{ "type": "counter_offer", "price": 20000.00 }
```
> If mode is `ai` and the buyer is countering, the AI evaluates again.

#### Accept the latest pending offer
```json
{ "type": "accepted" }
```
> Optionally specify which offer: `{ "type": "accepted", "offer_id": "<uuid>" }`

#### Reject the latest pending offer
```json
{ "type": "rejected" }
```
> Optionally: `{ "type": "rejected", "offer_id": "<uuid>" }`

#### Typing indicator
```json
{ "type": "typing" }
```
> Send while the user is typing. Not echoed back to the sender.

#### Mark a message as seen
```json
{ "type": "seen", "message_id": "<msg-uuid>" }
```

#### Heartbeat (keep connection alive)
```json
{ "type": "ping" }
```
> Server replies with `{"type": "pong"}`. Send every 25–30s if you need to keep the socket alive through proxies that drop idle connections.

---

### 5.4 Server → Client Events

All events are broadcast to **both** buyer and vendor in the room.

#### `history` — initial load (on connect only)
```json
{
  "type": "history",
  "room_id": "string",
  "mode": "ai | manual",
  "status": "open | agreed | expired | cancelled",
  "product_price": "22999.00",
  "messages": [ ...NegotiationMessage objects ]
}
```

#### `message` — plain text message
```json
{
  "type": "message",
  "id": "msg-uuid",
  "sender_type": "buyer | vendor | ai | system",
  "sender_id": "42 | null",
  "content": "Is this negotiable?",
  "message_type": "text",
  "price_value": null,
  "is_seen": false,
  "created_at": "2026-05-06T10:01:00Z"
}
```

#### `offer` — buyer submits a price
```json
{
  "type": "offer",
  "message": { ...NegotiationMessage object },
  "offer": {
    "id": "offer-uuid",
    "offered_by": "buyer",
    "original_price": "22999.00",
    "offered_price": "19500.00",
    "counter_offer_price": null,
    "status": "pending",
    "round_number": 1,
    "ai_confidence": null,
    "expires_at": "2026-05-07T10:01:30Z"
  },
  "room": { ...full NegotiationRoom snapshot }
}
```
> The message fields are also spread at the top level for convenience (`id`, `sender_type`, `content`, `price_value`, etc.) — same shape as the `message` event.

#### `counter_offer` — AI or vendor proposes a different price
```json
{
  "type": "counter_offer",
  "message": { ...NegotiationMessage object },
  "offer": {
    "id": "offer-uuid-2",
    "offered_by": "ai",
    "original_price": "22999.00",
    "offered_price": "21000.00",
    "counter_offer_price": null,
    "status": "pending",
    "round_number": 2,
    "ai_confidence": 0.82,
    "expires_at": "2026-05-07T10:01:32Z"
  },
  "room": { ...full NegotiationRoom snapshot }
}
```
> Message fields are also spread at the top level.

#### `accepted` — price agreed
```json
{
  "type": "accepted",
  "final_price": "21000.00",
  "expires_at": "2026-05-07T10:02:00Z",
  "room": { ...full NegotiationRoom snapshot, status="agreed", time_remaining_seconds=86400 }
}
```
> After this event, room `status` becomes `"agreed"`. The buyer has **24 hours** to check out. Use `room.time_remaining_seconds` to drive your countdown timer. The cart auto-add happens server-side — a system message confirming it appears in the chat.

#### `rejected` — offer rejected
```json
{
  "type": "rejected",
  "rejected_by": "ai | buyer | vendor",
  "message": {
    "id": "msg-uuid",
    "sender_type": "ai",
    "sender_id": null,
    "content": "Offer rejected.",
    "message_type": "rejected",
    "price_value": null,
    "is_seen": false,
    "created_at": "2026-05-06T10:01:35Z"
  },
  "room": { ...full NegotiationRoom snapshot, status still "open" }
}
```
> Room stays `"open"` after rejection. The buyer can make another offer.

#### `typing` — other party is typing
```json
{
  "type": "typing",
  "sender_type": "ai | buyer | vendor"
}
```
> Never sent back to the party who triggered it.

#### `seen` — message read receipt
```json
{
  "type": "seen",
  "message_id": "msg-uuid"
}
```

#### `expired` — room timed out
```json
{
  "type": "expired",
  "room": { ...full NegotiationRoom snapshot, status="expired" }
}
```
> Sent by Celery when `offer_expires_at` passes without checkout, or when an agreed room expires. Disable the chat UI and show an expiry message.

#### `error` — server-side error
```json
{
  "type": "error",
  "message": "Room is already agreed"
}
```

#### `pong` — heartbeat reply
```json
{ "type": "pong" }
```
> Sent in response to a client `ping`.

---

### 5.5 Flutter WebSocket Service Example

```dart
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

class NegotiationSocketService {
  WebSocketChannel? _channel;
  final String roomId;
  final String token;
  final void Function(Map<String, dynamic>) onEvent;

  NegotiationSocketService({
    required this.roomId,
    required this.token,
    required this.onEvent,
  });

  void connect() {
    final uri = Uri.parse(
      'ws://your-host/ws/negotiations/$roomId/?token=$token',
    );
    _channel = WebSocketChannel.connect(uri);
    _channel!.stream.listen(
      (data) => onEvent(jsonDecode(data as String)),
      onError: (e) => onEvent({'type': 'error', 'message': e.toString()}),
      onDone: () => onEvent({'type': 'disconnected'}),
    );
  }

  void sendMessage(String content) => _send({'type': 'message', 'content': content});
  void sendOffer(double price) => _send({'type': 'offer', 'price': price});
  void sendCounterOffer(double price) => _send({'type': 'counter_offer', 'price': price});
  void accept({String? offerId}) => _send({'type': 'accepted', if (offerId != null) 'offer_id': offerId});
  void reject({String? offerId}) => _send({'type': 'rejected', if (offerId != null) 'offer_id': offerId});
  void sendTyping() => _send({'type': 'typing'});
  void markSeen(String messageId) => _send({'type': 'seen', 'message_id': messageId});

  void _send(Map<String, dynamic> data) =>
      _channel?.sink.add(jsonEncode(data));

  void disconnect() => _channel?.sink.close();
}
```

---

## 6. Enums & Constants

### NegotiationMode
| Value | Meaning |
|-------|---------|
| `"ai"` | XGBoost bot negotiates on the vendor's behalf |
| `"manual"` | Vendor types responses in real time |

### NegotiationStatus (room)
| Value | Meaning |
|-------|---------|
| `"open"` | Negotiation in progress |
| `"agreed"` | Price agreed — buyer must checkout within 24 h |
| `"expired"` | Agreement expired without checkout, or timed out |
| `"cancelled"` | Manually cancelled |

### MessageSenderType
| Value | Who sent it |
|-------|-------------|
| `"buyer"` | The customer |
| `"vendor"` | The human vendor (manual mode) |
| `"ai"` | The XGBoost AI bot |
| `"system"` | Automated system message |

### MessageType
| Value | Meaning |
|-------|---------|
| `"text"` | Plain chat message |
| `"offer"` | Buyer's price proposal |
| `"counter_offer"` | AI/vendor counter-proposal |
| `"accepted"` | Agreement confirmed |
| `"rejected"` | Offer declined |
| `"expired"` | Room/offer expired |
| `"system"` | AI greeting or system notification |

### OfferStatus
| Value | Meaning |
|-------|---------|
| `"pending"` | Awaiting response |
| `"accepted"` | Accepted — price locked |
| `"rejected"` | Declined |
| `"countered"` | A counter was made |
| `"expired"` | Timed out |

---

## 7. Full User Flow

### Customer (Buyer) Flow

```
1. Browse product detail page
2. Tap "Negotiate Price"
3. POST /api/negotiations/start/  →  get room_id
4. Open WebSocket: ws://host/ws/negotiations/<room_id>/?token=<jwt>
5. Receive `history` event  →  render existing messages
6. If AI mode: receive AI greeting message automatically
7. Send offer: {"type": "offer", "price": 19500}
8. Receive `offer` event (echoed back to confirm)
9. Receive `counter_offer` from AI or vendor
10. Either:
    a. Accept: {"type": "accepted"}  →  receive `accepted` event with final_price + expires_at
    b. Counter: {"type": "counter_offer", "price": 20000}  →  loop back to step 9
    c. Reject: {"type": "rejected"}  →  room stays open, can re-offer
11. On `accepted`:  
    - Show final price + checkout countdown (24 h)
    - Add to cart via orders API with negotiation_id = room_id
    - Complete checkout within 24 h
12. If countdown expires, receive `expired` event  →  show expiry message
```

### Vendor (Seller) Flow — Manual Mode

```
1. Receive push notification: new negotiation room
2. GET /api/negotiations/vendor/rooms/?status=open  →  see list
3. Open WebSocket for the specific room
4. Receive `history` (buyer's messages so far)
5. Send counter offer: {"type": "counter_offer", "price": 21500}
6. Buyer responds; loop
7. Accept: {"type": "accepted"}  →  price locked
8. Optional: switch to AI mid-conversation:
   POST /api/negotiations/vendor/rooms/<uuid>/switch-mode/
```

### Vendor (Seller) Flow — AI Mode

```
1. Set price policy: POST /api/negotiations/policy/set-policy/
   - max_discount_percent: how much the AI can discount
   - min_floor_percent: the hard floor (AI never goes below this)
   - auto_negotiate: true (AI active)
2. The AI handles all negotiations automatically
3. Vendor can monitor via GET /api/negotiations/vendor/rooms/
4. Vendor can take over any room:
   POST /api/negotiations/vendor/rooms/<uuid>/switch-mode/  →  mode becomes "manual"
5. Vendor joins WebSocket and starts typing manually
```

---

## 8. Error Handling

### REST API Errors

All errors follow DRF's standard format:

```json
{ "error": "Human-readable message" }
```
or field-level validation:
```json
{ "price": ["This field is required."] }
```

| HTTP Status | When |
|-------------|------|
| `400` | Validation error in request body |
| `401` | Missing or expired JWT token |
| `403` | Wrong user_type (e.g. vendor calling buyer endpoint) |
| `404` | Resource not found or access denied |

### WebSocket Errors

```json
{ "type": "error", "message": "Room is already agreed" }
```

| Message | When |
|---------|------|
| `"Invalid or expired token"` | JWT auth failed on connect (close code 4001) |
| `"Room not found"` | Room UUID invalid or you're not the buyer/vendor (close code 4004) |
| `"Only buyers can make offers"` | Vendor tried to send `offer` event |
| `"Room is already agreed"` | Action on a non-open room |
| `"Room is already expired"` | Action on an expired room |
| `"No pending offer found"` | Accept/reject with no active offer |
| `"Invalid price"` | Price ≤ 0 or not a number |
| `"Message too long (max 2000 chars)"` | Content > 2000 chars |
