"""
Delivery app signals.

post_save on DeliveryJob
  → dispatch_job_to_nearby_drivers() when a new job is created with
    status='pending' and pickup coordinates present.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='delivery.DeliveryJob')
def on_delivery_job_created(sender, instance, created, **kwargs):
    """
    When a new DeliveryJob is saved for the first time, broadcast it to all
    available drivers within DISPATCH_RADIUS_KM of the pickup location.

    Only fires on creation (created=True) and only when the job is in
    'pending' status so that subsequent saves (status changes, driver
    assignment, etc.) do not trigger a second broadcast.
    """
    if not created:
        return
    if instance.status != 'pending':
        return

    # Import here to avoid circular imports at module load time.
    from .services import dispatch_job_to_nearby_drivers
    dispatch_job_to_nearby_drivers(instance)
