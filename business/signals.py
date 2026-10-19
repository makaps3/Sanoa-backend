"""Business app signals.

On `VendorProfile` creation we auto-mint a `VendorEmployee` row
tagged `is_manager=True` and pointing at the same user. That row is
the CEO/founder/owner — the only seat capable of vetting the rest
of the employees on the profile (once the platform admin has
verified the manager themselves).

Keeps `register()` as the public entry point so `apps.py` can call
it without worrying about signal-wiring details.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver


def register():
    """Bind signal handlers. Called from ``business.apps.ready()``."""
    # Importing the model here avoids the AppConfig "not ready" trap
    # — `register()` runs after Django finishes loading apps.
    from .models import VendorProfile, VendorEmployee

    @receiver(post_save, sender=VendorProfile,
              dispatch_uid='business.vendor_profile_auto_manager')
    def _sync_manager_employee(sender, instance, created, **kwargs):
        """Auto-mint the manager row on profile create, and on
        subsequent saves keep the manager's role_title /
        department / is_active in sync with what the owner edits on
        their profile screen."""
        default_title = instance.role_title or (
            'CEO / Founder' if instance.profile_type == 'business'
            else 'Manager'
        )
        default_dept = instance.department or 'admin'

        manager, was_created = VendorEmployee.objects.get_or_create(
            vendor=instance,
            user=instance.user,
            defaults={
                'is_manager': True,
                'role_title': default_title,
                'department': default_dept,
                # Manager inherits the profile's verification
                # status — they're already going through the
                # vendor-vetting flow as the profile owner, so
                # there's no separate KYC step for them.
                'verification_status': instance.verification_status,
                'verified_at': instance.verified_at,
                'verified_by': instance.verified_by,
                'is_active': instance.status != 'suspended',
                # Seed the full permission set; `has_perm()` also
                # short-circuits to True for managers as a defence
                # in depth.
                'permissions':
                    VendorEmployee.default_permissions_for(is_manager=True),
            },
        )

        if was_created:
            return

        # Profile edit (not creation) — push the owner-side fields
        # the team screen reads. Only touch fields the owner can
        # actually change on the profile form; never overwrite
        # the manager's permissions / verified_by here.
        dirty = []
        new_title = instance.role_title or default_title
        if manager.role_title != new_title:
            manager.role_title = new_title
            dirty.append('role_title')
        new_dept = instance.department or default_dept
        if manager.department != new_dept:
            manager.department = new_dept
            dirty.append('department')
        is_active = instance.status != 'suspended'
        if manager.is_active != is_active:
            manager.is_active = is_active
            dirty.append('is_active')
        if dirty:
            dirty.append('updated_at')
            manager.save(update_fields=dirty)
