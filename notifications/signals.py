"""
Signal receivers that create Notification records across the platform.

All receivers use daemon-thread wrappers for non-blocking execution so they
never slow down the request/response cycle.
"""
import logging
import threading
from django.db import transaction

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from .models import Notification, NotificationPreference
from .service import notify, notify_admins

logger = logging.getLogger('sanoa.notifications')


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _bg(fn, *args, **kwargs):
    """Never read uncommitted profile or review changes from another thread."""
    transaction.on_commit(lambda: threading.Thread(
        target=fn, args=args, kwargs=kwargs, daemon=True).start())


# ─────────────────────────────────────────────────────────────────
# User — welcome notification on signup
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='accounts.User')
def on_user_created(sender, instance, created, **kwargs):
    if not created:
        return
    # Auto-create preference record
    NotificationPreference.objects.get_or_create(user=instance)

    user_type = getattr(instance, 'user_type', 'customer')
    if user_type == 'customer':
        body = (
            'Welcome to Sanoa! Start exploring vendors, place your first order, '
            'and unlock buy-now-pay-later credit once you\'re subscribed.'
        )
    elif user_type == 'vendor':
        body = (
            'Welcome to Sanoa! Complete your vendor profile and verification '
            'to start receiving orders from customers.'
        )
    else:
        body = 'Welcome to Sanoa!'

    _bg(notify, instance, Notification.WELCOME,
        'Welcome to Sanoa!', body, category=Notification.CAT_ACCOUNT)

    if user_type in ('customer', 'vendor'):
        _bg(notify_admins, Notification.ADMIN_NEW_USER,
            'New User Registered',
            f'New {user_type} signed up: {instance.email}',
            category=Notification.CAT_ADMIN,
            data={'user_id': instance.pk, 'user_type': user_type, 'email': instance.email})


# ─────────────────────────────────────────────────────────────────
# Orders
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='orders.Order')
def on_order_saved(sender, instance, created, **kwargs):
    _bg(_handle_order, instance, created)


def _handle_order(order, created):
    try:
        if created:
            _notify_order_created(order)
        else:
            _notify_order_status(order)
    except Exception as exc:
        logger.warning('Order notification error: %s', exc)


def _notify_order_created(order):
    # Customer confirmation
    notify(
        order.user,
        Notification.ORDER_CREATED,
        'Order Placed Successfully',
        f'Your order #{order.order_number} has been placed and is awaiting processing.',
        category=Notification.CAT_ORDER,
        data={'order_id': str(order.id), 'order_number': order.order_number,
              'amount': str(order.total_price) if hasattr(order, 'total_price') else ''},
    )
    # Notify each vendor with items in this order
    vendor_ids = set(order.items.values_list('vendor_id', flat=True))
    for vendor_profile_id in vendor_ids:
        try:
            from business.models import VendorProfile
            vp = VendorProfile.objects.select_related('user').get(pk=vendor_profile_id)
            notify(
                vp.user,
                Notification.NEW_ORDER,
                'New Order Received',
                f'Order #{order.order_number} has been placed by a customer.',
                category=Notification.CAT_ORDER,
                data={'order_id': str(order.id), 'order_number': order.order_number},
            )
        except Exception:
            pass


_STATUS_TO_NOTIF = {
    'processing': (Notification.ORDER_PROCESSING, 'Order Being Processed',
                   'Your order is now being processed by the vendor.'),
    'shipped':    (Notification.ORDER_SHIPPED,    'Order Shipped',
                   'Great news! Your order is on its way.'),
    'delivered':  (Notification.ORDER_DELIVERED,  'Order Delivered',
                   'Your order has been delivered. Enjoy!'),
    'cancelled':  (Notification.ORDER_CANCELLED,  'Order Cancelled',
                   'Your order has been cancelled.'),
    'refunded':   (Notification.ORDER_REFUNDED,   'Order Refunded',
                   'Your order refund has been processed.'),
}


def _notify_order_status(order):
    notif_info = _STATUS_TO_NOTIF.get(order.status)
    if not notif_info:
        return
    ntype, title, body = notif_info
    notify(order.user, ntype, title, body,
           category=Notification.CAT_ORDER,
           data={'order_id': str(order.id), 'order_number': order.order_number,
                 'status': order.status})

    if order.status == 'cancelled':
        vendor_ids = set(order.items.values_list('vendor_id', flat=True))
        for vid in vendor_ids:
            try:
                from business.models import VendorProfile
                vp = VendorProfile.objects.select_related('user').get(pk=vid)
                notify(vp.user, Notification.VENDOR_ORDER_CANCELLED,
                       'Order Cancelled',
                       f'Order #{order.order_number} was cancelled by the customer.',
                       category=Notification.CAT_ORDER,
                       data={'order_id': str(order.id), 'order_number': order.order_number})
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────
# Payments — Transaction
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='payments.Transaction')
def on_transaction_saved(sender, instance, created, **kwargs):
    if not created:
        _bg(_notify_transaction_status_change, instance)


def _notify_transaction_status_change(txn):
    try:
        intent = txn.payment_intent
        amount = f'R{txn.amount:.2f}'

        if txn.status == 'success':
            notify(
                txn.user,
                Notification.PAYMENT_SUCCESS,
                'Payment Successful',
                f'Your {intent.replace("_", " ")} of {amount} was successful.',
                category=Notification.CAT_PAYMENT,
                data={'transaction_id': str(txn.id), 'reference': txn.reference,
                      'amount': str(txn.amount), 'intent': intent},
            )
            # Notify vendor on order payment success
            if intent == 'order_payment' and txn.order:
                vendor_ids = set(txn.order.items.values_list('vendor_id', flat=True))
                for vid in vendor_ids:
                    try:
                        from business.models import VendorProfile
                        vp = VendorProfile.objects.select_related('user').get(pk=vid)
                        notify(
                            vp.user,
                            Notification.VENDOR_PAYMENT_RECEIVED,
                            'Payment Received',
                            f'Payment of {amount} received for order #{txn.order.order_number}.',
                            category=Notification.CAT_PAYMENT,
                            data={'transaction_id': str(txn.id), 'amount': str(txn.amount),
                                  'order_id': str(txn.order.id)},
                        )
                    except Exception:
                        pass

        elif txn.status == 'failed':
            notify(
                txn.user,
                Notification.PAYMENT_FAILED,
                'Payment Failed',
                f'Your {intent.replace("_", " ")} of {amount} failed. '
                f'Reason: {txn.failure_reason or "Unknown error"}.',
                category=Notification.CAT_PAYMENT,
                data={'transaction_id': str(txn.id), 'reference': txn.reference,
                      'amount': str(txn.amount)},
            )
            notify_admins(
                Notification.ADMIN_PAYMENT_FAILED,
                'Payment Transaction Failed',
                f'Payment of {amount} failed for {txn.user.email}. '
                f'Reason: {txn.failure_reason or "Unknown error"}.',
                category=Notification.CAT_PAYMENT,
                data={'transaction_id': str(txn.id), 'user_id': txn.user_id,
                      'amount': str(txn.amount), 'intent': intent,
                      'reference': txn.reference},
            )
        elif txn.status == 'abandoned':
            notify(
                txn.user,
                Notification.PAYMENT_FAILED,
                'Payment Abandoned',
                f'Your {intent.replace("_", " ")} of {amount} was not completed. '
                'Please try again.',
                category=Notification.CAT_PAYMENT,
                data={'transaction_id': str(txn.id), 'reference': txn.reference,
                      'amount': str(txn.amount)},
            )
    except Exception as exc:
        logger.warning('Transaction notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Payments — Refund
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='payments.Refund')
def on_refund_saved(sender, instance, created, **kwargs):
    _bg(_notify_refund, instance, created)


def _notify_refund(refund, created):
    try:
        amount = f'R{refund.amount:.2f}'
        if created:
            notify(
                refund.user,
                Notification.REFUND_REQUESTED,
                'Refund Request Submitted',
                f'Your refund of {amount} has been submitted and is pending approval.',
                category=Notification.CAT_PAYMENT,
                data={'refund_id': str(refund.id), 'amount': str(refund.amount)},
            )
            notify_admins(
                Notification.ADMIN_REFUND_PENDING,
                'Refund Request Needs Approval',
                f'{refund.user.email} requested a refund of {amount}.',
                category=Notification.CAT_ADMIN,
                data={'refund_id': str(refund.id), 'amount': str(refund.amount),
                      'user_id': refund.user_id},
            )
            # Notify vendor
            if refund.order:
                vendor_ids = set(refund.order.items.values_list('vendor_id', flat=True))
                for vid in vendor_ids:
                    try:
                        from business.models import VendorProfile
                        vp = VendorProfile.objects.select_related('user').get(pk=vid)
                        notify(
                            vp.user,
                            Notification.VENDOR_REFUND_REQUESTED,
                            'Customer Refund Request',
                            f'A customer requested a refund of {amount} on order '
                            f'#{refund.order.order_number}.',
                            category=Notification.CAT_PAYMENT,
                            data={'refund_id': str(refund.id), 'amount': str(refund.amount)},
                        )
                    except Exception:
                        pass
        elif refund.status == 'processed':
            notify(
                refund.user,
                Notification.REFUND_PROCESSED,
                'Refund Processed',
                f'Your refund of {amount} has been processed successfully.',
                category=Notification.CAT_PAYMENT,
                data={'refund_id': str(refund.id), 'amount': str(refund.amount)},
            )
    except Exception as exc:
        logger.warning('Refund notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Payments — Dispute
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='payments.Dispute')
def on_dispute_saved(sender, instance, created, **kwargs):
    _bg(_notify_dispute, instance, created)


def _notify_dispute(dispute, created):
    try:
        if created:
            notify(
                dispute.user,
                Notification.DISPUTE_CREATED,
                'Dispute Opened',
                'Your dispute has been filed and is under review.',
                category=Notification.CAT_PAYMENT,
                data={'dispute_id': str(dispute.id)},
            )
            notify_admins(
                Notification.ADMIN_DISPUTE,
                'New Dispute Filed',
                f'Dispute filed by {dispute.user.email}.',
                category=Notification.CAT_ADMIN,
                data={'dispute_id': str(dispute.id), 'user_id': dispute.user_id},
            )
            # Notify vendor
            if dispute.transaction and dispute.transaction.order:
                order = dispute.transaction.order
                vendor_ids = set(order.items.values_list('vendor_id', flat=True))
                for vid in vendor_ids:
                    try:
                        from business.models import VendorProfile
                        vp = VendorProfile.objects.select_related('user').get(pk=vid)
                        notify(
                            vp.user,
                            Notification.VENDOR_DISPUTE,
                            'Dispute Filed Against Your Order',
                            f'A dispute has been filed on order #{order.order_number}.',
                            category=Notification.CAT_PAYMENT,
                            data={'dispute_id': str(dispute.id), 'order_id': str(order.id)},
                        )
                    except Exception:
                        pass
        elif dispute.status == 'resolved':
            notify(
                dispute.user,
                Notification.DISPUTE_RESOLVED,
                'Dispute Resolved',
                f'Your dispute has been resolved: {dispute.resolution or "see details"}.',
                category=Notification.CAT_PAYMENT,
                data={'dispute_id': str(dispute.id), 'resolution': dispute.resolution or ''},
            )
    except Exception as exc:
        logger.warning('Dispute notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Subscriptions
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='subscriptions.Subscription')
def on_subscription_saved(sender, instance, created, **kwargs):
    _bg(_notify_subscription, instance, created)


def _notify_subscription(sub, created):
    try:
        plan_name = sub.plan.name if sub.plan else 'Unknown'
        if created:
            notify(
                sub.user,
                Notification.SUBSCRIPTION_CREATED,
                'Subscription Activated',
                f'Your {plan_name} subscription is now active. '
                f'Enjoy credit access and premium features!',
                category=Notification.CAT_SUBSCRIPTION,
                data={'subscription_id': str(sub.id), 'plan': plan_name},
            )
        elif sub.status == 'past_due':
            notify(
                sub.user,
                Notification.SUBSCRIPTION_PAST_DUE,
                'Subscription Payment Overdue',
                'Your subscription payment is overdue. Please update your payment method '
                'to avoid losing access.',
                category=Notification.CAT_SUBSCRIPTION,
                data={'subscription_id': str(sub.id), 'plan': plan_name},
            )
        elif sub.status == 'cancelled':
            notify(
                sub.user,
                Notification.SUBSCRIPTION_EXPIRED,
                'Subscription Cancelled',
                f'Your {plan_name} subscription has been cancelled.',
                category=Notification.CAT_SUBSCRIPTION,
                data={'subscription_id': str(sub.id), 'plan': plan_name},
            )
    except Exception as exc:
        logger.warning('Subscription notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Credit / Debit
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='debit.CreditAccount')
def on_credit_account_saved(sender, instance, created, **kwargs):
    if created:
        _bg(notify, instance.user, Notification.CREDIT_ACCOUNT_CREATED,
            'Credit Account Created',
            'Your buy-now-pay-later credit account is ready to use.',
            Notification.CAT_CREDIT,
            data={'credit_account_id': instance.pk,
                  'credit_limit': str(instance.credit_limit)})

    elif instance.status == 'suspended' and not created:
        _bg(notify, instance.user, Notification.CREDIT_SUSPENDED,
            'Credit Account Suspended',
            'Your credit account has been suspended due to an overdue payment. '
            'Please repay your outstanding balance to restore access.',
            Notification.CAT_CREDIT,
            data={'credit_account_id': instance.pk,
                  'outstanding': str(instance.current_balance)})

    elif instance.status == 'active' and not created:
        # Suspension just lifted — check if user was suspended
        if getattr(instance, '_was_suspended', False):
            _bg(notify, instance.user, Notification.CREDIT_UNSUSPENDED,
                'Account Reactivated',
                'Your credit account has been reactivated. Full platform access restored!',
                Notification.CAT_CREDIT,
                data={'credit_account_id': instance.pk})


@receiver(post_save, sender='debit.CreditPurchase')
def on_credit_purchase_saved(sender, instance, created, **kwargs):
    _bg(_notify_credit_purchase, instance, created)


def _notify_credit_purchase(purchase, created):
    try:
        user = purchase.credit_account.user
        amount = f'R{purchase.total_amount:.2f}'
        if created:
            notify(
                user,
                Notification.CREDIT_PURCHASE_CREATED,
                'Credit Purchase Created',
                f'You purchased {amount} on credit. Deposit of '
                f'R{purchase.deposit_amount:.2f} recorded. '
                f'Repay by {purchase.due_date.strftime("%d %b %Y")}.',
                category=Notification.CAT_CREDIT,
                data={'purchase_id': str(purchase.id), 'total': str(purchase.total_amount),
                      'due_date': str(purchase.due_date)},
            )
        elif purchase.status == 'paid':
            notify(
                user,
                Notification.CREDIT_REPAYMENT,
                'Credit Purchase Fully Paid',
                f'Your credit purchase of {amount} is fully settled. Well done!',
                category=Notification.CAT_CREDIT,
                data={'purchase_id': str(purchase.id)},
            )
        elif purchase.status == 'defaulted':
            notify(
                user,
                Notification.CREDIT_OVERDUE,
                'Credit Payment Overdue',
                f'Your credit purchase of {amount} is overdue. '
                'Please repay immediately to avoid suspension.',
                category=Notification.CAT_CREDIT,
                data={'purchase_id': str(purchase.id), 'due_date': str(purchase.due_date)},
            )
            notify_admins(
                Notification.ADMIN_CREDIT_DEFAULTED,
                'Credit Purchase Defaulted',
                f'{user.email} has a defaulted credit purchase of {amount}.',
                category=Notification.CAT_ADMIN,
                data={'purchase_id': str(purchase.id), 'user_id': user.pk,
                      'amount': str(purchase.total_amount)},
            )
    except Exception as exc:
        logger.warning('Credit purchase notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Business — Follow / Unfollow
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='business.BusinessFollower')
def on_follower_created(sender, instance, created, **kwargs):
    if not created:
        return
    _bg(_notify_follow, instance)


def _notify_follow(follower):
    try:
        customer = follower.user
        vendor_user = follower.vendor
        vendor_name = _vendor_display_name(vendor_user)

        notify(
            customer,
            Notification.VENDOR_FOLLOWED,
            f'You followed {vendor_name}',
            f'You are now following {vendor_name}. '
            'Reach 3 orders to unlock buy-on-credit access!',
            category=Notification.CAT_SOCIAL,
            data={'vendor_id': vendor_user.pk, 'vendor_name': vendor_name},
        )
        notify(
            vendor_user,
            Notification.NEW_FOLLOWER,
            'New Follower',
            f'{customer.get_full_name() or customer.email} started following your store.',
            category=Notification.CAT_SOCIAL,
            data={'customer_id': customer.pk, 'customer_email': customer.email},
        )
    except Exception as exc:
        logger.warning('Follow notification error: %s', exc)


@receiver(post_delete, sender='business.BusinessFollower')
def on_follower_deleted(sender, instance, **kwargs):
    _bg(_notify_unfollow, instance)


def _notify_unfollow(follower):
    try:
        customer = follower.user
        vendor_user = follower.vendor
        vendor_name = _vendor_display_name(vendor_user)

        notify(
            customer,
            Notification.VENDOR_UNFOLLOWED,
            f'You unfollowed {vendor_name}',
            f'You have unfollowed {vendor_name}.',
            category=Notification.CAT_SOCIAL,
            data={'vendor_id': vendor_user.pk, 'vendor_name': vendor_name},
        )
        notify(
            vendor_user,
            Notification.UNFOLLOWED_BY,
            'A customer unfollowed your store',
            f'{customer.get_full_name() or customer.email} unfollowed your store.',
            category=Notification.CAT_SOCIAL,
            data={'customer_id': customer.pk},
        )
    except Exception as exc:
        logger.warning('Unfollow notification error: %s', exc)


def _vendor_display_name(vendor_user):
    vp = getattr(vendor_user, 'vendor_profile', None)
    if vp:
        return getattr(vp, 'name', None) or getattr(vp, 'business_name', None) or vendor_user.email
    return vendor_user.get_full_name() or vendor_user.email


# ─────────────────────────────────────────────────────────────────
# Vendor Profile — verification status changes
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='business.VendorProfile')
def on_vendor_profile_saved(sender, instance, created, **kwargs):
    _bg(_notify_vendor_verification, instance, created)


def _notify_vendor_verification(vp, created):
    try:
        if created:
            vendor_label = vp.trading_name or vp.name or vp.user.email
            profile_type = getattr(vp, 'profile_type', 'individual')
            if profile_type == 'business':
                notif_type = Notification.ADMIN_NEW_BUSINESS
                title = 'New Business Registered'
                body = (
                    f'Business "{vendor_label}" ({vp.user.email}) has registered '
                    f'and is awaiting verification.'
                )
            else:
                notif_type = Notification.ADMIN_VENDOR_PENDING
                title = 'New Vendor Awaiting Verification'
                body = (
                    f'Vendor "{vendor_label}" ({vp.user.email}) has registered '
                    f'and needs verification.'
                )
            notify_admins(
                notif_type, title, body,
                category=Notification.CAT_ADMIN,
                data={'vendor_profile_id': str(vp.id), 'vendor_email': vp.user.email,
                      'profile_type': profile_type},
            )
            return

        status = vp.verification_status
        if status == 'verified':
            notify(
                vp.user,
                Notification.VERIFICATION_APPROVED,
                'Verification Approved!',
                'Congratulations! Your vendor account has been verified. '
                'Your store is now live and visible to customers.',
                category=Notification.CAT_ACCOUNT,
                data={'vendor_profile_id': str(vp.id)},
            )
        elif status == 'rejected':
            notify(
                vp.user,
                Notification.VERIFICATION_REJECTED,
                'Verification Not Approved',
                'Unfortunately your vendor verification was not approved. '
                'Please check your documents and resubmit.',
                category=Notification.CAT_ACCOUNT,
                data={'vendor_profile_id': str(vp.id)},
            )
        elif status == 'suspended':
            notify(
                vp.user,
                Notification.VENDOR_FRAUD_FLAGGED,
                'Store Suspended',
                'Your store has been temporarily suspended. '
                'Please contact support for more information.',
                category=Notification.CAT_ACCOUNT,
                data={'vendor_profile_id': str(vp.id)},
            )
    except Exception as exc:
        logger.warning('Vendor verification notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Negotiations
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='negotiations.NegotiationOffer')
def on_negotiation_offer_saved(sender, instance, created, **kwargs):
    if created:
        _bg(_notify_new_offer, instance)
    else:
        _bg(_notify_offer_status_change, instance)


def _notify_new_offer(offer):
    try:
        room = offer.room
        buyer = room.buyer
        vendor_user = room.vendor.user
        price = f'R{offer.offered_price:.2f}'
        product_name = room.product.name if room.product else 'Item'

        if offer.offered_by == 'buyer':
            # Notify vendor
            notify(
                vendor_user,
                Notification.VENDOR_NEGOTIATION_OFFER,
                'New Price Offer',
                f'Buyer offered {price} for "{product_name}".',
                category=Notification.CAT_NEGOTIATION,
                data={'room_id': str(room.id), 'offer_id': str(offer.id),
                      'price': str(offer.offered_price), 'product': product_name},
            )
        elif offer.offered_by in ('vendor', 'ai'):
            # Notify buyer
            notify(
                buyer,
                Notification.NEGOTIATION_COUNTER,
                'Counter-Offer Received',
                f'The vendor countered with {price} for "{product_name}".',
                category=Notification.CAT_NEGOTIATION,
                data={'room_id': str(room.id), 'offer_id': str(offer.id),
                      'price': str(offer.offered_price), 'product': product_name},
            )
    except Exception as exc:
        logger.warning('Negotiation offer notification error: %s', exc)


def _notify_offer_status_change(offer):
    try:
        room = offer.room
        buyer = room.buyer
        vendor_user = room.vendor.user
        price = f'R{offer.offered_price:.2f}'
        product_name = room.product.name if room.product else 'Item'

        if offer.status == 'accepted':
            notify(
                buyer,
                Notification.NEGOTIATION_ACCEPTED,
                'Offer Accepted!',
                f'Your offer of {price} for "{product_name}" was accepted!',
                category=Notification.CAT_NEGOTIATION,
                data={'room_id': str(room.id), 'agreed_price': str(offer.offered_price)},
            )
        elif offer.status == 'rejected':
            notify(
                buyer,
                Notification.NEGOTIATION_REJECTED,
                'Offer Rejected',
                f'Your offer for "{product_name}" was not accepted.',
                category=Notification.CAT_NEGOTIATION,
                data={'room_id': str(room.id)},
            )
        elif offer.status == 'expired':
            notify(
                buyer,
                Notification.NEGOTIATION_EXPIRED,
                'Negotiation Offer Expired',
                f'Your agreed price for "{product_name}" has expired.',
                category=Notification.CAT_NEGOTIATION,
                data={'room_id': str(room.id)},
            )
            notify(
                vendor_user,
                Notification.NEGOTIATION_EXPIRED,
                'Negotiation Offer Expired',
                f'The agreed offer for "{product_name}" expired without checkout.',
                category=Notification.CAT_NEGOTIATION,
                data={'room_id': str(room.id)},
            )
    except Exception as exc:
        logger.warning('Offer status notification error: %s', exc)


@receiver(post_save, sender='negotiations.NegotiationRoom')
def on_negotiation_room_saved(sender, instance, created, **kwargs):
    if not created and instance.status == 'agreed':
        _bg(_notify_negotiation_agreed, instance)


def _notify_negotiation_agreed(room):
    try:
        product_name = room.product.name if room.product else 'Item'
        price = f'R{room.agreed_price:.2f}' if room.agreed_price else 'agreed price'
        data = {'room_id': str(room.id), 'agreed_price': str(room.agreed_price or ''),
                'product': product_name}
        # Notify buyer
        notify(
            room.buyer,
            Notification.NEGOTIATION_AGREED,
            'Price Agreed!',
            f'You and the vendor agreed on {price} for "{product_name}". '
            'Complete checkout within 24 hours.',
            category=Notification.CAT_NEGOTIATION,
            data=data,
        )
        # Notify vendor — the buyer accepted and the deal is locked
        notify(
            room.vendor.user,
            Notification.NEGOTIATION_AGREED,
            'Negotiation Finalised',
            f'A buyer agreed on {price} for "{product_name}". '
            'Await their checkout — the offer expires in 24 hours.',
            category=Notification.CAT_NEGOTIATION,
            data=data,
        )
    except Exception as exc:
        logger.warning('Negotiation agreed notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Delivery
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='delivery.DeliveryJob')
def on_delivery_job_saved(sender, instance, created, **kwargs):
    _bg(_notify_delivery, instance, created)


def _notify_delivery(job, created):
    try:
        order = job.retail_order
        if order is None:
            return
        customer = order.user

        status = job.status
        if status == 'accepted' or created:
            notify(
                customer,
                Notification.DELIVERY_ASSIGNED,
                'Delivery Driver Assigned',
                'A driver has been assigned and is heading to the vendor.',
                category=Notification.CAT_DELIVERY,
                data={'job_id': str(job.id), 'order_id': str(order.id)},
            )
        elif status == 'picked_up':
            notify(
                customer,
                Notification.DELIVERY_PICKED_UP,
                'Order Picked Up',
                'The driver has picked up your order and is on the way!',
                category=Notification.CAT_DELIVERY,
                data={'job_id': str(job.id), 'order_id': str(order.id)},
            )
        elif status == 'in_transit':
            notify(
                customer,
                Notification.DELIVERY_IN_TRANSIT,
                'Order In Transit',
                'Your order is in transit. Sit tight!',
                category=Notification.CAT_DELIVERY,
                data={'job_id': str(job.id), 'order_id': str(order.id)},
            )
        elif status == 'delivered':
            notify(
                customer,
                Notification.DELIVERY_COMPLETED,
                'Order Delivered!',
                'Your order has been delivered. Enjoy!',
                category=Notification.CAT_DELIVERY,
                data={'job_id': str(job.id), 'order_id': str(order.id)},
            )
    except Exception as exc:
        logger.warning('Delivery notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Fraud
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='fraud.FraudProfile')
def on_fraud_profile_saved(sender, instance, created, **kwargs):
    if created:
        return
    _bg(_notify_fraud, instance)


def _notify_fraud(profile):
    try:
        risk = profile.risk_level  # low/medium/high/critical
        if risk not in ('high', 'critical'):
            return

        # Notify the user/vendor being flagged
        target_user = None
        if profile.user:
            target_user = profile.user
        elif profile.vendor:
            target_user = profile.vendor.user

        if target_user and profile.is_flagged:
            notify(
                target_user,
                Notification.VENDOR_FRAUD_FLAGGED,
                'Account Under Review',
                'Your account has been flagged for a security review. '
                'Our team will contact you shortly.',
                category=Notification.CAT_FRAUD,
                data={'risk_level': risk, 'risk_score': str(profile.risk_score)},
            )

        # Notify admins
        admin_type = (
            Notification.ADMIN_FRAUD_CRITICAL
            if risk == 'critical' else Notification.ADMIN_FRAUD_HIGH
        )
        entity = target_user.email if target_user else str(profile.id)
        notify_admins(
            admin_type,
            f'{risk.capitalize()} Fraud Risk Detected',
            f'Entity {entity} has a {risk} fraud risk score of {profile.risk_score}/100.',
            category=Notification.CAT_FRAUD,
            data={'profile_id': str(profile.id), 'risk_level': risk,
                  'risk_score': str(profile.risk_score)},
        )
    except Exception as exc:
        logger.warning('Fraud notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Vendor Tier Subscription
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='tiers.VendorTierSubscription')
def on_vendor_tier_subscription_saved(sender, instance, created, **kwargs):
    _bg(_notify_tier_subscription, instance, created)


def _notify_tier_subscription(sub, created):
    try:
        vendor_user = sub.vendor.user
        tier_name = sub.tier.name
        price = f'R{sub.tier.price:.2f}' if sub.tier.price else 'free'
        data = {'subscription_id': str(sub.id), 'tier': tier_name,
                'tier_level': sub.tier.tier_level, 'vendor_id': str(sub.vendor.id)}

        if created:
            if sub.status == 'trialing':
                notify(
                    vendor_user,
                    Notification.VENDOR_TIER_ACTIVATED,
                    f'{tier_name} Free Trial Started',
                    f'Your {sub.tier.trial_days}-day free trial of the {tier_name} plan '
                    'has started. Explore all your new features!',
                    category=Notification.CAT_SUBSCRIPTION,
                    data=data,
                )
            else:
                notify(
                    vendor_user,
                    Notification.VENDOR_TIER_ACTIVATED,
                    f'{tier_name} Plan Activated',
                    f'Your {tier_name} business tier ({price}/month) is now active. '
                    'Enjoy reduced commissions and enhanced store features!',
                    category=Notification.CAT_SUBSCRIPTION,
                    data=data,
                )
            return

        if sub.status == 'past_due':
            notify(
                vendor_user,
                Notification.VENDOR_TIER_PAST_DUE,
                'Tier Subscription Payment Overdue',
                f'Your {tier_name} plan payment is overdue. '
                'Update your payment method on Paystack to keep your tier benefits.',
                category=Notification.CAT_SUBSCRIPTION,
                data=data,
            )
            notify_admins(
                Notification.ADMIN_TIER_PAST_DUE,
                'Vendor Tier Payment Overdue',
                f'Vendor {sub.vendor.trading_name or sub.vendor.name} '
                f'({vendor_user.email}) has a past-due {tier_name} tier subscription.',
                category=Notification.CAT_ADMIN,
                data=data,
            )

        elif sub.status == 'cancelled':
            notify(
                vendor_user,
                Notification.VENDOR_TIER_CANCELLED,
                f'{tier_name} Plan Cancelled',
                f'Your {tier_name} subscription has been cancelled. '
                'You will revert to the free tier at the end of your current billing period.',
                category=Notification.CAT_SUBSCRIPTION,
                data=data,
            )

        elif sub.status == 'expired':
            notify(
                vendor_user,
                Notification.VENDOR_TIER_EXPIRED,
                f'{tier_name} Plan Expired',
                f'Your {tier_name} tier has expired. '
                'Renew now to restore your commission savings and product limits.',
                category=Notification.CAT_SUBSCRIPTION,
                data=data,
            )

    except Exception as exc:
        logger.warning('Tier subscription notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Vetting Application
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='business.VettingApplication')
def on_vetting_application_saved(sender, instance, created, **kwargs):
    _bg(_notify_vetting, instance, created)


def _notify_vetting(vetting, created):
    try:
        # Resolve the vendor user from whichever FK is set
        if vetting.individual_vendor:
            vendor_user = vetting.individual_vendor.user
            vendor_label = getattr(vetting.individual_vendor, 'store_name', '') or vendor_user.email
        elif vetting.business_vendor:
            vendor_user = vetting.business_vendor.user
            vendor_label = getattr(vetting.business_vendor, 'business_name', '') or vendor_user.email
        else:
            return

        vetting_type_label = vetting.get_vetting_type_display()
        data = {'vetting_id': str(vetting.pk), 'vetting_type': vetting.vetting_type,
                'vendor_email': vendor_user.email}

        if created:
            notify_admins(
                Notification.ADMIN_VETTING_SUBMITTED,
                'New Vetting Application Submitted',
                f'"{vendor_label}" has submitted a {vetting_type_label} vetting application '
                f'and is awaiting review.',
                category=Notification.CAT_ADMIN,
                data=data,
            )
            return

        if vetting.status == 'passed':
            notify(
                vendor_user,
                Notification.VENDOR_VETTING_PASSED,
                'Verification Check Passed!',
                f'Your {vetting_type_label} verification has been approved. '
                'Your store is one step closer to being fully verified.',
                category=Notification.CAT_ACCOUNT,
                data=data,
            )

        elif vetting.status == 'failed':
            notify(
                vendor_user,
                Notification.VENDOR_VETTING_FAILED,
                'Verification Check Failed',
                f'Your {vetting_type_label} verification was not approved. '
                f'Reason: {vetting.rejection_reason or "Please contact support for details."}',
                category=Notification.CAT_ACCOUNT,
                data=data,
            )

        elif vetting.status == 'requires_resubmission':
            notify(
                vendor_user,
                Notification.VENDOR_VETTING_RESUBMIT,
                'Resubmission Required',
                f'Your {vetting_type_label} verification requires additional documents. '
                'Please log in and resubmit your application.',
                category=Notification.CAT_ACCOUNT,
                data=data,
            )

    except Exception as exc:
        logger.warning('Vetting notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Inventory — low stock & out of stock
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='products.Product')
def on_product_saved(sender, instance, created, **kwargs):
    if created:
        return
    if not instance.track_inventory:
        return
    _bg(_notify_stock_alert, instance)


def _notify_stock_alert(product):
    try:
        vendor_user = product.vendor.user
        data = {'product_id': str(product.id), 'product_name': product.name,
                'stock': product.stock, 'sku': product.sku}

        if product.stock == 0 and not product.continue_selling_when_out_of_stock:
            notify(
                vendor_user,
                Notification.VENDOR_OUT_OF_STOCK,
                'Product Out of Stock',
                f'"{product.name}" (SKU: {product.sku}) is now out of stock. '
                'Restock soon to avoid losing sales.',
                category=Notification.CAT_INVENTORY,
                data=data,
            )
        elif 0 < product.stock <= 5:
            notify(
                vendor_user,
                Notification.VENDOR_LOW_STOCK,
                'Low Stock Alert',
                f'"{product.name}" (SKU: {product.sku}) has only {product.stock} '
                'unit(s) remaining. Consider restocking now.',
                category=Notification.CAT_INVENTORY,
                data=data,
            )
    except Exception as exc:
        logger.warning('Stock alert notification error: %s', exc)


# ─────────────────────────────────────────────────────────────────
# Business Performance Alerts (vendor + admin)
# Fired from Celery beat tasks that compute periodic metrics.
# The helper below is called explicitly from tasks, not a signal.
# ─────────────────────────────────────────────────────────────────

def notify_vendor_performance(vendor_profile, metric: str, value, period: str = 'this week'):
    """
    Called by Celery analytics tasks to alert vendors and admins about
    significant business performance changes.

    metric examples:
      'revenue_growth'    value = % change (float, positive = growth)
      'revenue_decline'   value = % decline (float, negative)
      'order_completion'  value = completion rate % (float)
      'cancellation_rate' value = cancellation rate % (float)
      'new_orders'        value = total new orders (int)
      'no_orders'         value = 0 (no orders this period)
    """
    try:
        from .models import Notification
        vendor_user = vendor_profile.user
        vendor_label = vendor_profile.trading_name or vendor_profile.name or vendor_user.email
        data = {'vendor_id': str(vendor_profile.id), 'metric': metric,
                'value': str(value), 'period': period}

        if metric == 'revenue_growth':
            pct = float(value)
            if pct >= 20:
                notify(vendor_user, Notification.VENDOR_PAYMENT_RECEIVED,
                       '🚀 Revenue Surging!',
                       f'Your revenue grew {pct:.1f}% {period} — excellent performance! '
                       'Keep it up and consider upgrading your tier for even lower commissions.',
                       category=Notification.CAT_PAYMENT, data=data)
            elif pct >= 5:
                notify(vendor_user, Notification.VENDOR_PAYMENT_RECEIVED,
                       '📈 Revenue Growing',
                       f'Your revenue is up {pct:.1f}% {period}. '
                       'Consistent growth — keep your product listings fresh.',
                       category=Notification.CAT_PAYMENT, data=data)

        elif metric == 'revenue_decline':
            pct = abs(float(value))
            notify(vendor_user, Notification.VENDOR_PAYMENT_RECEIVED,
                   '📉 Revenue Declined',
                   f'Your revenue dropped {pct:.1f}% {period}. '
                   'Review your pricing, stock levels, and product visibility.',
                   category=Notification.CAT_PAYMENT, data=data)
            if pct >= 30:
                notify_admins(Notification.ADMIN_VENDOR_PENDING,
                              'Vendor Revenue Decline Alert',
                              f'Vendor "{vendor_label}" revenue dropped {pct:.1f}% {period}.',
                              category=Notification.CAT_ADMIN, data=data)

        elif metric == 'no_orders':
            notify(vendor_user, Notification.NEW_ORDER,
                   'No Orders This Period',
                   f'You received no orders {period}. '
                   'Check your store is active, products are in stock, and prices are competitive.',
                   category=Notification.CAT_ORDER, data=data)
            notify_admins(Notification.ADMIN_VENDOR_PENDING,
                          'Inactive Vendor Alert',
                          f'Vendor "{vendor_label}" had zero orders {period}.',
                          category=Notification.CAT_ADMIN, data=data)

        elif metric == 'order_completion':
            rate = float(value)
            if rate < 60:
                notify(vendor_user, Notification.NEW_ORDER,
                       '⚠️ Low Order Completion Rate',
                       f'Your order completion rate is {rate:.1f}% {period}. '
                       'Fulfil orders promptly — low completion hurts your performance score.',
                       category=Notification.CAT_ORDER, data=data)
                notify_admins(Notification.ADMIN_VENDOR_PENDING,
                              'Vendor Low Completion Rate',
                              f'Vendor "{vendor_label}" has a {rate:.1f}% completion rate {period}.',
                              category=Notification.CAT_ADMIN, data=data)

        elif metric == 'cancellation_rate':
            rate = float(value)
            if rate > 20:
                notify(vendor_user, Notification.VENDOR_ORDER_CANCELLED,
                       '⚠️ High Cancellation Rate',
                       f'{rate:.1f}% of your orders were cancelled {period}. '
                       'Review stock availability and order processing times.',
                       category=Notification.CAT_ORDER, data=data)

    except Exception as exc:
        logger.warning('Performance notification error: %s', exc)
