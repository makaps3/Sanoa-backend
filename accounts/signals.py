"""
Signals for accounts app - auto-create profiles on user creation
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import CustomerProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create a profile when a new user is created.

    - customer → CustomerProfile
    - vendor   → VendorProfile (blank skeleton; vendor completes it later)
    """
    if not created:
        return

    if instance.user_type == 'customer':
        CustomerProfile.objects.get_or_create(user=instance)
    elif instance.user_type == 'vendor':
        # Import inside the handler to avoid circular imports at startup.
        from business.models import VendorProfile
        VendorProfile.objects.get_or_create(
            user=instance,
            defaults={
                'profile_type': 'individual',
                'name': '',
            },
        )
    # admin and driver don't get an auto-created profile here —
    # they complete their profile via dedicated endpoints after OTP verification.
