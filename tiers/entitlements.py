"""Current paid benefits, with the free plan as the inactive fallback."""
from .models import BusinessTier, VendorTierSubscription


def effective_tier(vendor):
    sub = VendorTierSubscription.objects.select_related('tier').filter(vendor=vendor).first()
    if sub and sub.is_active:
        return sub.tier
    return BusinessTier.objects.filter(price=0, is_active=True).order_by('tier_level').first()


def negotiation_allowed(vendor):
    tier = effective_tier(vendor)
    return bool(tier and tier.negotiation_enabled)


def product_limit(vendor):
    tier = effective_tier(vendor)
    return tier.max_products if tier else 20
