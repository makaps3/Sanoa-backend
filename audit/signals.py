"""
Django signals for automatic model-level audit logging.

Listens to post_save and post_delete on all tracked models
and records changes in the AuditLog table.
"""
import logging
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed

logger = logging.getLogger('sanoa.audit')

# Models to track automatically.
# Format: 'app_label.ModelName'
TRACKED_MODELS = [
    'accounts.User',
    'accounts.CustomerProfile',
    'accounts.IndividualVendorProfile',
    'accounts.BusinessVendorProfile',
    'accounts.VendorDocument',
    'accounts.VettingApplication',
    'accounts.Address',
    'accounts.APIToken',
    'products.Product',
    'products.Category',
    'products.Brand',
    'products.ProductVariant',
    'products.ProductReview',
    'products.VendorReview',
    'orders.Order',
    'orders.OrderItem',
    'orders.ShoppingCart',
    'orders.CartItem',
    'orders.Coupon',
    'orders.OrderStatusHistory',
    'payments.Transaction',
    'payments.Refund',
    'payments.PaystackSubaccount',
    'inventory.Warehouse',
    'inventory.InventoryItem',
    'inventory.StockMovement',
    'inventory.PurchaseOrder',
    'inventory.StockAlert',
    'debit.CreditAccount',
    'debit.CreditPurchase',
    'debit.CreditRepayment',
    'subscriptions.Plan',
    'subscriptions.Subscription',
    'negotiations.PricePolicy',
    'negotiations.NegotiationRoom',
    'negotiations.NegotiationOffer',
    'tiers.BusinessTier',
    'tiers.VendorTierSubscription',
]

# Fields to exclude from change tracking (sensitive / noisy)
EXCLUDED_FIELDS = {
    'password', 'last_login', 'updated_at', 'created_at',
}


def _get_model_label(instance):
    """Return 'app_label.ModelName' for an instance."""
    return f"{instance._meta.app_label}.{instance.__class__.__name__}"


def _is_tracked(instance):
    """Check if this model instance should be tracked."""
    return _get_model_label(instance) in TRACKED_MODELS


def _get_changes(instance):
    """
    Compare the instance's current state with what is in the DB
    to produce a dict of changed fields.
    """
    if instance.pk is None:
        return None

    model_class = instance.__class__
    try:
        old = model_class.objects.get(pk=instance.pk)
    except model_class.DoesNotExist:
        return None

    changes = {}
    for field in instance._meta.fields:
        if field.name in EXCLUDED_FIELDS:
            continue
        old_val = getattr(old, field.name, None)
        new_val = getattr(instance, field.name, None)
        if old_val != new_val:
            changes[field.name] = {
                'old': str(old_val) if old_val is not None else None,
                'new': str(new_val) if new_val is not None else None,
            }
    return changes if changes else None


def _get_audit_user():
    """Get the current user from the request via middleware thread-local."""
    try:
        from audit.middleware import get_current_user
        return get_current_user()
    except Exception:
        return None


def _get_request_info():
    """Get IP and user-agent from the current request."""
    try:
        from audit.middleware import get_current_request
        from core.utils import get_client_ip
        request = get_current_request()
        if request:
            return {
                'ip': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            }
    except Exception:
        pass
    return {'ip': None, 'user_agent': ''}


def _create_audit_log(action, instance, changes=None, deferred=False):
    """Create an AuditLog entry for a model change.

    If deferred=True, the log is created via transaction.on_commit()
    to avoid FK constraint issues when deleting objects.
    """
    from audit.models import AuditLog
    from django.db import transaction

    user = _get_audit_user()
    req_info = _get_request_info()
    model_label = _get_model_label(instance)

    # Determine category from app label
    category_map = {
        'accounts': 'user',
        'business': 'vendor',
        'products': 'product',
        'orders': 'order',
        'payments': 'payment',
        'inventory': 'inventory',
        'debit': 'debit',
        'subscriptions': 'subscription',
        'negotiations': 'negotiation',
        'tiers': 'tier',
        'otp': 'otp',
    }
    category = category_map.get(instance._meta.app_label, 'system')

    target_repr = ''
    try:
        target_repr = str(instance)[:255]
    except Exception:
        pass

    # Snapshot values now since the instance may not exist after commit
    user_id = user.pk if user else None
    user_email = user.email if user else ''
    target_id = str(instance.pk) if instance.pk else ''

    # If deleting a User, don't reference them as the acting user
    # (they'll be gone after the transaction commits)
    User = get_user_model()
    if action == 'delete' and isinstance(instance, User):
        # The instance is the user being deleted - don't set as actor
        if user and user.pk == instance.pk:
            user_id = None

    def _do_create():
        # Re-validate that the user FK still exists
        acting_user = None
        if user_id is not None:
            try:
                acting_user = User.objects.filter(pk=user_id).first()
            except Exception:
                pass

        AuditLog.objects.create(
            user=acting_user,
            user_email=user_email,
            ip_address=req_info['ip'],
            user_agent=req_info['user_agent'],
            category=category,
            action=action,
            status='success',
            description=f"{action.title()} {model_label}: {target_repr}",
            target_model=model_label,
            target_id=target_id,
            target_repr=target_repr,
            changes=changes,
        )

    if deferred:
        transaction.on_commit(_do_create)
    else:
        _do_create()


# ---- Pre-save: capture old state for diff ----

@receiver(pre_save)
def audit_pre_save(sender, instance, **kwargs):
    """Capture field changes before save."""
    if not _is_tracked(instance):
        return
    if instance.pk is not None:
        try:
            instance._audit_changes = _get_changes(instance)
        except Exception:
            instance._audit_changes = None


# ---- Post-save: log create / update ----

@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    """Log model creation or update."""
    if not _is_tracked(instance):
        return

    try:
        if created:
            _create_audit_log('create', instance)
        else:
            changes = getattr(instance, '_audit_changes', None)
            if changes:
                _create_audit_log('update', instance, changes=changes)
    except Exception:
        logger.exception(f'Error creating audit log for {_get_model_label(instance)}')


# ---- Post-delete: log deletion ----

@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    """Log model deletion."""
    if not _is_tracked(instance):
        return

    try:
        _create_audit_log('delete', instance, deferred=True)
    except Exception:
        logger.exception(f'Error creating audit log for delete of {_get_model_label(instance)}')


# ---- Authentication signals ----

@receiver(user_logged_in)
def audit_user_login(sender, request, user, **kwargs):
    """Log successful login."""
    from audit.models import AuditLog, LoginAttempt
    from core.utils import get_client_ip

    ip = get_client_ip(request) if request else None
    ua = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''

    AuditLog.objects.create(
        user=user,
        user_email=user.email,
        ip_address=ip,
        user_agent=ua,
        category='auth',
        action='login',
        status='success',
        description=f"User {user.email} logged in",
        target_model='accounts.User',
        target_id=str(user.pk),
        target_repr=user.email,
    )

    LoginAttempt.objects.create(
        email=user.email,
        ip_address=ip,
        user_agent=ua,
        status='success',
    )


@receiver(user_logged_out)
def audit_user_logout(sender, request, user, **kwargs):
    """Log logout."""
    from audit.models import AuditLog
    from core.utils import get_client_ip

    if user is None:
        return

    ip = get_client_ip(request) if request else None
    ua = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''

    AuditLog.objects.create(
        user=user,
        user_email=user.email,
        ip_address=ip,
        user_agent=ua,
        category='auth',
        action='logout',
        status='success',
        description=f"User {user.email} logged out",
        target_model='accounts.User',
        target_id=str(user.pk),
        target_repr=user.email,
    )


@receiver(user_login_failed)
def audit_user_login_failed(sender, credentials, request, **kwargs):
    """Log failed login attempt."""
    from audit.models import AuditLog, LoginAttempt
    from core.utils import get_client_ip

    email = credentials.get('email', credentials.get('username', 'unknown'))
    ip = get_client_ip(request) if request else None
    ua = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''

    AuditLog.objects.create(
        user=None,
        user_email=email,
        ip_address=ip,
        user_agent=ua,
        category='auth',
        action='login_failed',
        status='failure',
        description=f"Failed login attempt for {email}",
        target_model='accounts.User',
        target_id='',
        target_repr=email,
    )

    LoginAttempt.objects.create(
        email=email,
        ip_address=ip,
        user_agent=ua,
        status='failed',
        failure_reason='Invalid credentials',
    )
