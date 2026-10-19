"""
Auto-provision a Conversation when a DeliveryJob first gets a driver
assigned. Keeps chat lifecycle aligned with the delivery lifecycle —
the customer can't message a driver who hasn't accepted the job yet,
and a "closed" delivery freezes new messages on its conversation.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from delivery.models import DeliveryJob

from .models import Conversation


@receiver(post_save, sender=DeliveryJob,
          dispatch_uid='chat.deliveryjob_sync_conversation')
def _sync_conversation(sender, instance, created, **kwargs):
    # No driver yet → nothing to chat about.
    if instance.driver_id is None:
        return

    driver_user = getattr(instance.driver, 'user', None)
    if driver_user is None:
        return

    conv, was_created = Conversation.objects.get_or_create(
        delivery_job=instance,
        defaults={
            'customer': instance.customer,
            'driver': driver_user,
        },
    )
    if not was_created and conv.driver_id != driver_user.id:
        # Job reassigned to a new driver → update the chat owner.
        conv.driver = driver_user
        conv.save(update_fields=['driver'])

    # Close the chat when the job is over.
    terminal = {'delivered', 'cancelled', 'failed'}
    if instance.status in terminal and conv.status != Conversation.STATUS_CLOSED:
        conv.status = Conversation.STATUS_CLOSED
        conv.closed_at = timezone.now()
        conv.save(update_fields=['status', 'closed_at'])
