"""
WebSocket consumer for real-time negotiation chat.

Connection URL:
    ws://<host>/ws/negotiations/<room_uuid>/?token=<JWT_access_token>

Events the client sends:
    {"type": "message",      "content": "Hello"}
    {"type": "offer",        "price": 85.00}
    {"type": "counter_offer","price": 90.00}
    {"type": "accepted",     "offer_id": "<uuid>"}   # optional offer_id
    {"type": "rejected",     "offer_id": "<uuid>"}   # optional offer_id
    {"type": "typing"}
    {"type": "seen",         "message_id": "<uuid>"}

Events the server broadcasts to both parties:
    {"type": "history",      "room_id": "...", "mode": "...", "messages": [...]}
    {"type": "message",      ...message_fields}
    {"type": "offer",        ...message_fields, "offer": {...}}
    {"type": "counter_offer",...message_fields, "offer": {...}}
    {"type": "accepted",     "final_price": "90.00", "expires_at": "..."}
    {"type": "rejected",     "rejected_by": "buyer|vendor|ai", "message": {...}}
    {"type": "typing",       "sender_type": "buyer|vendor|ai"}
    {"type": "seen",         "message_id": "..."}
    {"type": "expired"}
    {"type": "error",        "message": "..."}
"""
import asyncio
import json
import logging
from decimal import Decimal, InvalidOperation

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

logger = logging.getLogger('sanoa.negotiations')


class NegotiationConsumer(AsyncWebsocketConsumer):

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.group_name = f"negotiation_{self.room_id}"
        self.user = None
        self.room = None
        self.role = None   # 'buyer' | 'vendor'

        user = await self._authenticate()
        if user is None:
            await self.close(code=4001)
            return
        self.user = user

        room, role = await self._get_room_and_role(self.room_id, user)
        if room is None:
            await self.close(code=4004)
            return
        self.room = room
        self.role = role
        if not await self._subscription_allows_negotiation():
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        history = await self._get_history()
        await self.send(text_data=json.dumps({
            'type': 'history',
            'room_id': str(room.id),
            'mode': room.mode,
            'status': room.status,
            'product_price': str(room.product.price),
            'messages': history,
        }))

        # If buyer opens an AI room for the first time, send greeting
        if role == 'buyer' and room.mode == 'ai' and room.status == 'open':
            count = await self._message_count()
            if count == 0:
                await self._do_ai_greeting()

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ------------------------------------------------------------------
    # Incoming event router
    # ------------------------------------------------------------------

    async def receive(self, text_data):
        if not await self._subscription_allows_negotiation():
            await self._error('The vendor subscription has expired. Negotiation is unavailable.')
            await self.close(code=4403)
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._error("Invalid JSON")
            return

        event_type = data.get('type')

        # Refresh room status from DB before processing state-sensitive events.
        # Accept / reject are also valid while the room is `pending_vendor`
        # (AI agreed → vendor still needs to confirm); offers/counters must
        # wait until the room is back to `open`.
        if event_type in ('offer', 'counter_offer', 'accepted', 'rejected'):
            await self._refresh_room()
            allowed = {'open'}
            if event_type in ('accepted', 'rejected'):
                allowed.add('pending_vendor')
            if self.room.status not in allowed:
                await self._error(f"Room is already {self.room.status}")
                return

        if event_type == 'message':
            await self._on_message(data)
        elif event_type == 'offer':
            await self._on_offer(data)
        elif event_type == 'counter_offer':
            await self._on_counter_offer(data)
        elif event_type == 'accepted':
            await self._on_accepted(data)
        elif event_type == 'rejected':
            await self._on_rejected(data)
        elif event_type == 'typing':
            await self._on_typing()
        elif event_type == 'seen':
            await self._on_seen(data)
        elif event_type == 'ping':
            # Heartbeat — reply with pong so the client knows the socket is alive
            await self.send(text_data=json.dumps({'type': 'pong'}))
        else:
            await self._error(f"Unknown event type: {event_type}")

    # ------------------------------------------------------------------
    # Client event handlers
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _subscription_allows_negotiation(self):
        from tiers.entitlements import negotiation_allowed
        return negotiation_allowed(self.room.vendor)

    async def _on_message(self, data):
        content = str(data.get('content', '')).strip()
        if not content:
            return
        if len(content) > 2000:
            await self._error("Message too long (max 2000 chars)")
            return

        msg = await self._save_message(
            content=content, message_type='text',
            sender_type=self.role, sender=self.user,
        )
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.message',
            'message': self._ser_msg(msg),
        })

        # In AI mode, plain-text messages from the buyer don't trigger the
        # negotiation engine (it only evaluates price offers). Send a short
        # nudge so the buyer isn't left staring at silence.
        if self.room.mode == 'ai' and self.role == 'buyer':
            await self._ai_nudge()

    async def _on_offer(self, data):
        """Buyer submits a new price offer."""
        if self.role != 'buyer':
            await self._error("Only buyers can make offers")
            return

        price = self._parse_price(data.get('price'))
        if price is None:
            await self._error("Invalid price")
            return

        original = await self._product_price()
        msg = await self._save_message(
            content=f"I'd like to buy this for R{price:.2f}",
            message_type='offer', sender_type='buyer', sender=self.user,
            price_value=price,
        )
        offer = await self._save_offer(
            message=msg, offered_by='buyer',
            original_price=original, offered_price=price,
        )

        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.offer',
            'message': self._ser_msg(msg),
            'offer': self._ser_offer(offer),
        })

        # Fire AI response in the background so the buyer's offer is flushed
        # to both clients immediately and receive() can keep processing events
        # (typing, seen, etc.) while the model runs.
        if self.room.mode == 'ai':
            asyncio.create_task(self._ai_respond(offer, price))

    async def _on_counter_offer(self, data):
        """Vendor (manual mode) or buyer (countering AI's counter) submits a counter."""
        price = self._parse_price(data.get('price'))
        if price is None:
            await self._error("Invalid price")
            return

        original = await self._product_price()
        sender_type = 'vendor' if self.role == 'vendor' else 'buyer'
        msg = await self._save_message(
            content=f"How about R{price:.2f}?",
            message_type='counter_offer', sender_type=sender_type, sender=self.user,
            price_value=price,
        )
        offer = await self._save_offer(
            message=msg, offered_by=sender_type,
            original_price=original, offered_price=price,
        )

        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.counter_offer',
            'message': self._ser_msg(msg),
            'offer': self._ser_offer(offer),
        })

        # Buyer countered AI's proposal — AI evaluates again (non-blocking)
        if self.room.mode == 'ai' and sender_type == 'buyer':
            asyncio.create_task(self._ai_respond(offer, price))

    async def _on_accepted(self, data):
        """Accept the latest (or a specific) pending offer.

        For `pending_vendor` rooms (AI agreed, waiting on vendor) only the
        vendor may finalize — the buyer is already on record as agreeing.
        """
        if self.room.status == 'pending_vendor' and self.role != 'vendor':
            await self._error("Only the vendor can confirm this deal.")
            return

        offer_id = data.get('offer_id')
        offer, error = await self._accept_offer(offer_id)
        if error:
            await self._error(error)
            return

        expires_at = await self._expires_at()
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.accepted',
            'final_price': str(offer.offered_price),
            'expires_at': expires_at,
        })

        # Auto-add the item to the buyer's cart at the agreed price
        await self._post_agreement_cart_add()

    async def _on_rejected(self, data):
        """Reject the latest (or a specific) pending offer.

        If the room is `pending_vendor`, only the vendor may reject —
        and doing so reopens the room so the buyer can offer again
        rather than killing it outright.
        """
        if self.room.status == 'pending_vendor':
            if self.role != 'vendor':
                await self._error("Only the vendor can override this deal.")
                return
            # Hard cancel — the room moves to history and the cart row
            # is purged so the buyer can't checkout the rejected deal.
            await self._cancel_pending_vendor_room()

        offer_id = data.get('offer_id')
        error = await self._reject_offer(offer_id)
        if error:
            await self._error(error)
            return

        msg = await self._save_message(
            content="Offer rejected.",
            message_type='rejected', sender_type=self.role, sender=self.user,
        )
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.rejected',
            'rejected_by': self.role,
            'message': self._ser_msg(msg),
        })

    async def _on_typing(self):
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.typing',
            'sender_type': self.role,
            'origin_channel': self.channel_name,
        })

    async def _on_seen(self, data):
        msg_id = data.get('message_id')
        if msg_id:
            await self._mark_seen(msg_id)
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.seen',
                'message_id': msg_id,
            })

    # ------------------------------------------------------------------
    # Channel-layer message handlers (dispatched to all group members)
    # ------------------------------------------------------------------

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({'type': 'message', **event['message']}))

    async def chat_offer(self, event):
        room = await self._ser_room_fresh()
        await self.send(text_data=json.dumps({
            'type': 'offer',
            **event['message'],
            'offer': event['offer'],
            'message': event['message'],
            'room': room,
        }))

    async def chat_counter_offer(self, event):
        room = await self._ser_room_fresh()
        await self.send(text_data=json.dumps({
            'type': 'counter_offer',
            **event['message'],
            'offer': event['offer'],
            'message': event['message'],
            'room': room,
        }))

    async def chat_accepted(self, event):
        room = await self._ser_room_fresh()
        await self.send(text_data=json.dumps({
            'type': 'accepted',
            'final_price': event['final_price'],
            'expires_at': event['expires_at'],
            'room': room,
        }))

    async def chat_pending_vendor(self, event):
        """AI accepted; both sides need to know the deal is now waiting
        on the vendor's confirmation rather than ready for checkout."""
        room = await self._ser_room_fresh()
        await self.send(text_data=json.dumps({
            'type': 'pending_vendor',
            'final_price': event['final_price'],
            'expires_at': event['expires_at'],
            'room': room,
        }))

    async def chat_rejected(self, event):
        room = await self._ser_room_fresh()
        await self.send(text_data=json.dumps({
            'type': 'rejected',
            'rejected_by': event['rejected_by'],
            'message': event.get('message', {}),
            'room': room,
        }))

    async def chat_typing(self, event):
        # Don't echo back to the sender
        if event.get('origin_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'sender_type': event['sender_type'],
            }))

    async def chat_seen(self, event):
        await self.send(text_data=json.dumps({
            'type': 'seen', 'message_id': event['message_id'],
        }))

    async def chat_expired(self, event):
        room = await self._ser_room_fresh()
        await self.send(text_data=json.dumps({
            'type': 'expired',
            'room': room,
        }))

    # ------------------------------------------------------------------
    # AI response pipeline
    # ------------------------------------------------------------------

    async def _do_ai_greeting(self):
        greeting = await database_sync_to_async(self._run_greeting)()
        msg = await self._save_message(
            content=greeting, message_type='system',
            sender_type='ai', sender=None,
        )
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.message',
            'message': self._ser_msg(msg),
        })

    async def _ai_nudge(self):
        """Reply to a plain-text message in an AI room so the buyer isn't left waiting."""
        nudge = (
            "I'm your AI price negotiator — I can only evaluate price offers. "
            "Please tap the offer button and propose a price to get started!"
        )
        msg = await self._save_message(
            content=nudge, message_type='system',
            sender_type='ai', sender=None,
        )
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.message',
            'message': self._ser_msg(msg),
        })

    async def _ai_respond(self, buyer_offer, offered_price):
        # Show "AI is typing…" immediately so the buyer sees activity
        # while the model evaluates the offer.
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.typing',
            'sender_type': 'ai',
            'origin_channel': '',  # always broadcast (no sender to skip)
        })

        try:
            response = await database_sync_to_async(self._run_ai)(offered_price)
        except Exception as exc:
            logger.error(f"AI engine error in room {self.room_id}: {exc}")
            return

        original = await self._product_price()

        if response['action'] == 'accept':
            # AI says yes, but the deal is held pending vendor confirmation
            # for up to 24 h. We deliberately do NOT mark the buyer's offer
            # accepted, do NOT add to the buyer's cart, and do NOT flip the
            # room to `agreed` here — the vendor's accept event does all of
            # that. If the vendor doesn't act in time the Celery expiry task
            # will close the room.
            ai_msg = await self._save_message(
                content=(
                    f"Great deal at R{offered_price:.2f}! I've locked it in "
                    "pending the vendor's confirmation. They have 24 hours "
                    "to approve — you'll be notified the moment they do."
                ),
                message_type='system',
                sender_type='ai', sender=None, price_value=offered_price,
            )
            await self._do_set_pending_vendor(offered_price)
            vendor_expires_at = await self._expires_at()
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.message', 'message': self._ser_msg(ai_msg),
            })
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.pending_vendor',
                'final_price': str(offered_price),
                'expires_at': vendor_expires_at,
            })
            # Drop the item into the buyer's cart at the AI-agreed
            # price. The checkout view rejects carts whose linked room
            # isn't `agreed` yet, so the buyer can see the deal lined
            # up but cannot proceed until the vendor confirms.
            await self._post_agreement_cart_add()

        elif response['action'] == 'counter':
            counter_price = response['counter_price']
            ai_msg = await self._save_message(
                content=response['message'], message_type='counter_offer',
                sender_type='ai', sender=None, price_value=counter_price,
            )
            ai_offer = await self._save_offer(
                message=ai_msg, offered_by='ai',
                original_price=original, offered_price=counter_price,
                ai_action='counter', ai_confidence=response['confidence'],
            )
            await self._mark_offer_countered(buyer_offer, counter_price)
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.counter_offer',
                'message': self._ser_msg(ai_msg),
                'offer': self._ser_offer(ai_offer),
            })

        else:  # reject
            ai_msg = await self._save_message(
                content=response['message'], message_type='rejected',
                sender_type='ai', sender=None,
            )
            await self._mark_offer_rejected(buyer_offer)
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.rejected',
                'rejected_by': 'ai',
                'message': self._ser_msg(ai_msg),
            })

    def _run_greeting(self):
        from .engine import get_engine
        return get_engine().get_opening_message(self.room)

    def _run_ai(self, offered_price):
        from .engine import get_engine
        return get_engine().respond_to_offer(self.room, offered_price)

    # ------------------------------------------------------------------
    # DB helpers (all run in Django's sync thread pool)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _authenticate(self):
        from rest_framework_simplejwt.tokens import AccessToken
        qs = self.scope.get('query_string', b'').decode()
        params = {k: v for k, v in (p.split('=', 1) for p in qs.split('&') if '=' in p)}
        token_str = params.get('token')
        if not token_str:
            return None
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            payload = AccessToken(token_str)
            return User.objects.get(id=payload['user_id'])
        except Exception:
            return None

    @database_sync_to_async
    def _get_room_and_role(self, room_id, user):
        from .models import NegotiationRoom
        try:
            room = (
                NegotiationRoom.objects
                .select_related('product', 'buyer', 'vendor', 'vendor__user')
                .get(id=room_id)
            )
        except NegotiationRoom.DoesNotExist:
            return None, None
        if room.buyer_id == user.id:
            return room, 'buyer'
        try:
            if room.vendor.user_id == user.id:
                return room, 'vendor'
        except Exception:
            pass
        return None, None

    @database_sync_to_async
    def _refresh_room(self):
        self.room.refresh_from_db()

    @database_sync_to_async
    def _get_history(self):
        msgs = (
            self.room.messages.order_by('created_at')
            .select_related('sender')[:100]
        )
        return [self._ser_msg(m) for m in msgs]

    @database_sync_to_async
    def _message_count(self):
        return self.room.messages.count()

    @database_sync_to_async
    def _product_price(self):
        return self.room.product.price

    @database_sync_to_async
    def _save_message(self, content, message_type, sender_type, sender, price_value=None):
        from .models import NegotiationMessage
        return NegotiationMessage.objects.create(
            room=self.room, content=content, message_type=message_type,
            sender_type=sender_type, sender=sender, price_value=price_value,
        )

    @database_sync_to_async
    def _save_offer(self, message, offered_by, original_price, offered_price,
                    ai_action=None, ai_confidence=None):
        from .models import NegotiationOffer
        round_n = self.room.offers.count() + 1
        return NegotiationOffer.objects.create(
            room=self.room, message=message,
            offered_by=offered_by,
            original_price=original_price,
            offered_price=offered_price,
            ai_action=ai_action,
            ai_confidence=ai_confidence,
            round_number=round_n,
        )

    @database_sync_to_async
    def _accept_offer(self, offer_id):
        from .models import NegotiationOffer
        try:
            if offer_id:
                offer = NegotiationOffer.objects.get(
                    id=offer_id, room=self.room, status='pending'
                )
            else:
                offer = (
                    self.room.offers.filter(status='pending')
                    .order_by('-created_at').first()
                )
            if offer is None:
                return None, "No pending offer found"
        except NegotiationOffer.DoesNotExist:
            return None, "Offer not found"

        offer.status = 'accepted'
        offer.responded_at = timezone.now()
        offer.save(update_fields=['status', 'responded_at'])
        self.room.set_agreed(offer.offered_price)
        return offer, None

    @database_sync_to_async
    def _reject_offer(self, offer_id):
        from .models import NegotiationOffer
        try:
            if offer_id:
                offer = NegotiationOffer.objects.get(
                    id=offer_id, room=self.room, status='pending'
                )
            else:
                offer = (
                    self.room.offers.filter(status='pending')
                    .order_by('-created_at').first()
                )
            if offer is None:
                return "No pending offer found"
        except NegotiationOffer.DoesNotExist:
            return "Offer not found"

        offer.status = 'rejected'
        offer.responded_at = timezone.now()
        offer.save(update_fields=['status', 'responded_at'])
        return None

    @database_sync_to_async
    def _do_accept_latest_buyer_offer(self, price):
        offer = (
            self.room.offers.filter(offered_by='buyer', status='pending')
            .order_by('-created_at').first()
        )
        if offer:
            offer.status = 'accepted'
            offer.responded_at = timezone.now()
            offer.save(update_fields=['status', 'responded_at'])
        self.room.set_agreed(price)

    @database_sync_to_async
    def _do_set_pending_vendor(self, price):
        """AI agreed — hold the room as pending until vendor confirms."""
        self.room.set_pending_vendor(price)

    @database_sync_to_async
    def _cancel_pending_vendor_room(self):
        """Vendor rejected the AI-recommended deal — cancel the room
        outright so it lands in the buyer's history, clear the agreed
        price + expiry, and yank any cart row the AI accept already
        created. The buyer's cart should not keep a stale negotiated
        item the vendor refused to honour.
        """
        self.room.status = 'cancelled'
        self.room.agreed_price = None
        self.room.offer_expires_at = None
        self.room.save(update_fields=[
            'status', 'agreed_price', 'offer_expires_at', 'updated_at',
        ])
        from orders.models import CartItem
        from restaurant.models import RestaurantCartItem
        CartItem.objects.filter(negotiation=self.room).delete()
        RestaurantCartItem.objects.filter(negotiation=self.room).delete()

    @database_sync_to_async
    def _mark_offer_countered(self, offer, counter_price):
        offer.status = 'countered'
        offer.counter_offer_price = counter_price
        offer.responded_at = timezone.now()
        offer.save(update_fields=['status', 'counter_offer_price', 'responded_at'])

    @database_sync_to_async
    def _mark_offer_rejected(self, offer):
        offer.status = 'rejected'
        offer.responded_at = timezone.now()
        offer.save(update_fields=['status', 'responded_at'])

    @database_sync_to_async
    def _mark_seen(self, message_id):
        from .models import NegotiationMessage
        try:
            NegotiationMessage.objects.get(id=message_id, room=self.room).mark_seen()
        except NegotiationMessage.DoesNotExist:
            pass

    @database_sync_to_async
    def _expires_at(self):
        self.room.refresh_from_db(fields=['offer_expires_at'])
        return self.room.offer_expires_at.isoformat() if self.room.offer_expires_at else None

    # ------------------------------------------------------------------
    # Cart auto-add after agreement
    # ------------------------------------------------------------------

    async def _post_agreement_cart_add(self):
        """
        After acceptance, drop the product into the buyer's cart at the
        negotiated price and broadcast a system message confirming it.
        Restaurant products go to RestaurantCart; everything else goes
        to the retail ShoppingCart.
        """
        try:
            note = await self._add_to_cart()
        except Exception as exc:
            logger.exception(f"Cart auto-add failed for room {self.room_id}: {exc}")
            note = "Couldn't auto-add to cart. Please add the item manually."

        if not note:
            return

        msg = await self._save_message(
            content=note, message_type='system',
            sender_type='system', sender=None,
        )
        await self.channel_layer.group_send(self.group_name, {
            'type': 'chat.message',
            'message': self._ser_msg(msg),
        })

    @database_sync_to_async
    def _add_to_cart(self):
        """
        Drop the negotiated item into the buyer's cart. Runs in two
        moments:

          • AI accepted the buyer's offer (room is `pending_vendor`) —
            the item is added but the orders checkout view rejects any
            cart with a non-`agreed` negotiation, so the buyer can see
            the item but cannot proceed until the vendor confirms.
          • Vendor confirmed (room is `agreed`) — same row, price
            refreshed, status now lets checkout through.

        Returns a status-aware system chat message (or None if there's
        nothing meaningful to say).
        """
        self.room.refresh_from_db()
        if self.room.status not in ('agreed', 'pending_vendor'):
            return None
        if self.room.agreed_price is None:
            return None

        product = self.room.product
        buyer = self.room.buyer
        vendor = self.room.vendor
        agreed = self.room.agreed_price
        is_pending = self.room.status == 'pending_vendor'

        is_restaurant = False
        if product.category_id:
            biz = getattr(product.category, 'business_category', None)
            is_restaurant = biz in ('restaurant', 'both')

        if is_restaurant:
            from restaurant.models import RestaurantCart, RestaurantCartItem
            cart, _ = RestaurantCart.objects.get_or_create(user=buyer, vendor=vendor)
            # RestaurantCartItem now mirrors orders.CartItem's
            # `negotiation` FK — the restaurant checkout view rejects
            # any cart whose linked room isn't `agreed`, giving us the
            # same pending_vendor block + vendor-reject purge behaviour
            # as retail.
            item, created = RestaurantCartItem.objects.get_or_create(
                cart=cart, product=product, negotiation=self.room,
                defaults={'quantity': 1},
            )
            if not created and item.price_at_time != agreed:
                item.price_at_time = agreed
                item.save(update_fields=['price_at_time', 'updated_at'])
            if is_pending:
                return (
                    f"🛒 Added **{product.name}** to your restaurant cart at "
                    f"R{agreed:.2f}. Checkout will unlock once the vendor "
                    f"approves the AI deal (they have 24 hours)."
                )
            if not created:
                return (
                    f"✅ Vendor approved — **{product.name}** at R{agreed:.2f} "
                    f"is now checkout-ready. Please complete the order within "
                    f"24 hours."
                )
            return (
                f"🛒 Added **{product.name}** to your restaurant cart at "
                f"R{agreed:.2f}. Please checkout within 24 hours to lock in this price."
            )

        from orders.models import ShoppingCart, CartItem
        cart, _ = ShoppingCart.objects.get_or_create(user=buyer, vendor=vendor)
        # Negotiation FK is the checkout gate — orders/views.py rejects
        # any cart whose linked room is not in `agreed`, which keeps the
        # buyer out of checkout during the pending_vendor hold.
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, negotiation=self.room,
            defaults={'quantity': 1},
        )
        if not created and item.price_at_time != agreed:
            item.price_at_time = agreed
            item.save(update_fields=['price_at_time', 'updated_at'])

        if is_pending:
            return (
                f"🛒 Added **{product.name}** to your cart at R{agreed:.2f}. "
                f"Checkout will unlock once the vendor approves the AI deal "
                f"(they have 24 hours)."
            )
        # status == 'agreed' — distinguish a fresh manual-mode add from
        # the vendor confirming an item that was already staged during
        # the pending_vendor hold; in the latter case the cart already
        # has the row, so the user-facing line is "deal confirmed".
        if not created:
            return (
                f"✅ Vendor approved — **{product.name}** at R{agreed:.2f} "
                f"is now checkout-ready. Please complete the order within "
                f"24 hours."
            )
        return (
            f"🛒 Added **{product.name}** to your cart at R{agreed:.2f}. "
            f"Please checkout within 24 hours to lock in this price."
        )

    # ------------------------------------------------------------------
    # Serialisers (plain dicts — no DRF overhead in the WS path)
    # ------------------------------------------------------------------

    def _ser_msg(self, msg):
        return {
            'id': str(msg.id),
            'sender_type': msg.sender_type,
            'sender_id': str(msg.sender_id) if msg.sender_id else None,
            'content': msg.content,
            'message_type': msg.message_type,
            'price_value': str(msg.price_value) if msg.price_value else None,
            'is_seen': msg.is_seen,
            'created_at': msg.created_at.isoformat(),
        }

    def _ser_offer(self, offer):
        return {
            'id': str(offer.id),
            'offered_by': offer.offered_by,
            'original_price': str(offer.original_price),
            'offered_price': str(offer.offered_price),
            'counter_offer_price': str(offer.counter_offer_price) if offer.counter_offer_price else None,
            'status': offer.status,
            'round_number': offer.round_number,
            'ai_confidence': offer.ai_confidence,
            'expires_at': offer.expires_at.isoformat(),
        }

    def _ser_room(self):
        """Lightweight room snapshot for WS broadcasts.

        Matches the frontend NegotiationRoom.fromJson contract so the client
        can update its local state without a separate REST refetch.
        """
        room = self.room
        time_remaining = None
        if room.status == 'agreed' and room.offer_expires_at:
            delta = room.offer_expires_at - timezone.now()
            time_remaining = max(int(delta.total_seconds()), 0)

        return {
            'id': str(room.id),
            'product': str(room.product_id),
            'product_name': room.product.name,
            'product_price': str(room.product.price),
            'product_image': None,  # already known from initial REST fetch
            'buyer': room.buyer_id,
            'buyer_email': room.buyer.email if room.buyer_id else '',
            'vendor': str(room.vendor_id),
            'vendor_name': (
                getattr(room.vendor, 'trading_name', None)
                or getattr(room.vendor, 'name', None)
                or str(room.vendor_id)
            ),
            'mode': room.mode,
            'status': room.status,
            'agreed_price': str(room.agreed_price) if room.agreed_price else None,
            'offer_expires_at': room.offer_expires_at.isoformat() if room.offer_expires_at else None,
            'time_remaining_seconds': time_remaining,
            'latest_offer': None,  # frontend uses event.offer for this
            'unread_count': 0,
            'created_at': room.created_at.isoformat(),
            'updated_at': room.updated_at.isoformat(),
        }

    @database_sync_to_async
    def _ser_room_fresh(self):
        """Refresh from DB and return a serialized room dict."""
        self.room.refresh_from_db()
        # Re-fetch the related product to get current price etc.
        self.room = type(self.room).objects.select_related(
            'product', 'buyer', 'vendor'
        ).get(id=self.room.id)
        return self._ser_room()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_price(raw):
        try:
            p = Decimal(str(raw)).quantize(Decimal('0.01'))
            return p if p > 0 else None
        except (InvalidOperation, TypeError):
            return None

    async def _error(self, message):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))
