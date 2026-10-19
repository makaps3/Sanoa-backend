"""
Celery tasks for orders app
"""
import logging
from celery import shared_task

logger = logging.getLogger('sanoa.orders')


@shared_task
def send_order_confirmation_email(order_id):
    """Send order confirmation email to customer"""
    from .models import Order
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        order = Order.objects.get(id=order_id)
        send_mail(
            subject=f'Order Confirmation - {order.order_number}',
            message=f'Thank you for your order {order.order_number}. '
                    f'Total: R{order.total_amount}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer_email],
            fail_silently=False,
        )
        logger.info(f"Order confirmation sent for {order.order_number}")
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for confirmation email")


@shared_task
def send_order_status_update_email(order_id, new_status):
    """Send order status update email to customer"""
    from .models import Order
    from django.core.mail import send_mail
    from django.conf import settings

    try:
        order = Order.objects.get(id=order_id)
        send_mail(
            subject=f'Order Update - {order.order_number}',
            message=f'Your order {order.order_number} status has been '
                    f'updated to: {new_status}.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.customer_email],
            fail_silently=False,
        )
        logger.info(f"Status update email sent for {order.order_number}: {new_status}")
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for status update email")
