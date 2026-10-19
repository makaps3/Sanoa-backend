"""
Seed business tiers for the Sanoa marketplace.

Four tiers, each with a monthly + annual billing option. The annual
plan charges 11 × the monthly fee — one month free.

The `commission_discount` field is the percentage-points rebate the
platform subtracts from `PlatformFee.merchant_commission_percent`
when a vendor on this tier settles. The effective commission is
``platform_fee.merchant_commission_percent − tier.commission_discount``,
floored at 0.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from tiers.models import BusinessTier


def _annual(monthly: str) -> str:
    """Annual price = 11 × monthly (one month free)."""
    return str((Decimal(monthly) * 11).quantize(Decimal('0.01')))


# Per-tier feature catalogue — keep monthly + yearly identical apart
# from the trailing "save 1 month" perk on the yearly row.
STARTER_FEATURES = [
    "List up to 20 products",
    "Standard 0% commission discount (pays full platform commission)",
    "Customer ↔ driver chat for every order",
    "Basic order management",
    "QR code for your store",
    "Standard search placement",
    "Up to 1 staff seat (the owner)",
    "Email support — community SLA",
]

GROWTH_FEATURES = [
    "List up to 80 products",
    "5 percentage points off platform commission",
    "Customer ↔ driver chat with 30-day history retention",
    "14-day free trial",
    "Priority search placement",
    "Promotional tools & discount codes",
    "Negotiation engine access (up to 10% markup)",
    "Basic analytics dashboard",
    "Up to 3 staff seats with role permissions",
    "Email + in-app support",
]

PREMIUM_FEATURES = [
    "List up to 150 products",
    "8 percentage points off platform commission",
    "Customer ↔ driver chat with full history retention",
    "14-day free trial",
    "Featured listings in search results",
    "Advanced negotiation engine (up to 15% markup)",
    "Full analytics suite with exportable reports",
    "Marketing campaign manager + QR promotions",
    "Inventory management & low-stock alerts",
    "Up to 8 staff seats with custom permissions",
    "Priority email + chat support",
]

ENTERPRISE_FEATURES = [
    "Unlimited products (150+)",
    "15 percentage points off platform commission",
    "Customer ↔ driver chat with audit-grade history",
    "7-day free trial",
    "Top search priority + premium featured listings",
    "Enterprise negotiation engine (up to 20% markup)",
    "Multi-location / branch support",
    "Bulk product upload & catalogue tooling",
    "Custom storefront branding",
    "Full analytics + custom report builder",
    "Complete API access & webhooks",
    "Unlimited staff seats with full RBAC",
    "Dedicated account manager",
    "Priority phone, email & chat support",
    "Invoice & tax management",
]


TIERS = [
    # ── Starter (free, no monthly/yearly distinction) ─────────────
    {
        "name": "Starter",
        "slug": "starter",
        "description": (
            "Get your business on Sanoa at no cost. Perfect for new "
            "vendors who want to test the marketplace, list a few "
            "products, and start selling — ideal for tuck shops, small "
            "stalls and home-based businesses."
        ),
        "price": "0.00",
        "tier_level": 0,
        "duration": 30,
        "duration_unit": "days",
        "max_products": 20,
        "commission_rate": "0.00",
        "commission_discount": "0.00",
        "search_priority_boost": "0.00",
        "featured_listings": False,
        "negotiation_enabled": False,
        "max_markup_percent": "0.00",
        "max_discount_percent": "0.00",
        "trial_days": 0,
        "sort_order": 1,
        "features": STARTER_FEATURES,
    },

    # ── Growth ────────────────────────────────────────────────────
    {
        "name": "Growth Monthly",
        "slug": "growth-monthly",
        "description": (
            "Designed for tuck shops, street vendors, freelancers and "
            "small traders ready to grow. Get priority in search, "
            "access the negotiation engine, list up to 80 products and "
            "claim a 5%-point platform commission discount on every "
            "sale. Billed monthly — cancel anytime."
        ),
        "price": "199.00",
        "tier_level": 1,
        "duration": 30,
        "duration_unit": "days",
        "max_products": 80,
        "commission_rate": "0.00",
        "commission_discount": "5.00",
        "search_priority_boost": "0.15",
        "featured_listings": False,
        "negotiation_enabled": True,
        "max_markup_percent": "10.00",
        "max_discount_percent": "5.00",
        "trial_days": 14,
        "sort_order": 2,
        "features": GROWTH_FEATURES,
    },
    {
        "name": "Growth Yearly",
        "slug": "growth-yearly",
        "description": (
            "Designed for tuck shops, street vendors, freelancers and "
            "small traders ready to grow. Get priority in search, "
            "access the negotiation engine, list up to 80 products and "
            "claim a 5%-point platform commission discount on every "
            f"sale. Billed yearly — pay 11 months, get 1 month free "
            f"(save R{Decimal('199.00')} / year)."
        ),
        "price": _annual("199.00"),
        "tier_level": 1,
        "duration": 1,
        "duration_unit": "years",
        "max_products": 80,
        "commission_rate": "0.00",
        "commission_discount": "5.00",
        "search_priority_boost": "0.15",
        "featured_listings": False,
        "negotiation_enabled": True,
        "max_markup_percent": "10.00",
        "max_discount_percent": "5.00",
        "trial_days": 14,
        "sort_order": 3,
        "features": GROWTH_FEATURES + [
            "Save R199/year (1 month free)",
        ],
    },

    # ── Premium ───────────────────────────────────────────────────
    {
        "name": "Premium Monthly",
        "slug": "premium-monthly",
        "description": (
            "Built for established vendors and growing storefronts. "
            "Get featured listings, advanced negotiation, marketing "
            "tools and an 8%-point commission discount — list up to "
            "150 products and bring 8 staff into the platform. Billed "
            "monthly — cancel anytime."
        ),
        "price": "699.00",
        "tier_level": 2,
        "duration": 30,
        "duration_unit": "days",
        "max_products": 150,
        "commission_rate": "0.00",
        "commission_discount": "8.00",
        "search_priority_boost": "0.35",
        "featured_listings": True,
        "negotiation_enabled": True,
        "max_markup_percent": "15.00",
        "max_discount_percent": "10.00",
        "trial_days": 14,
        "sort_order": 4,
        "features": PREMIUM_FEATURES,
    },
    {
        "name": "Premium Yearly",
        "slug": "premium-yearly",
        "description": (
            "Built for established vendors and growing storefronts. "
            "Get featured listings, advanced negotiation, marketing "
            "tools and an 8%-point commission discount — list up to "
            "150 products and bring 8 staff into the platform. Billed "
            f"yearly — pay 11 months, get 1 month free "
            f"(save R{Decimal('699.00')} / year)."
        ),
        "price": _annual("699.00"),
        "tier_level": 2,
        "duration": 1,
        "duration_unit": "years",
        "max_products": 150,
        "commission_rate": "0.00",
        "commission_discount": "8.00",
        "search_priority_boost": "0.35",
        "featured_listings": True,
        "negotiation_enabled": True,
        "max_markup_percent": "15.00",
        "max_discount_percent": "10.00",
        "trial_days": 14,
        "sort_order": 5,
        "features": PREMIUM_FEATURES + [
            "Save R699/year (1 month free)",
        ],
    },

    # ── Enterprise ────────────────────────────────────────────────
    {
        "name": "Enterprise Monthly",
        "slug": "enterprise-monthly",
        "description": (
            "The flagship tier for high-volume merchants, wholesalers "
            "and multi-branch businesses. Unlimited products, the "
            "largest 15%-point commission discount, full API access, "
            "multi-location support, unlimited staff and a dedicated "
            "account manager. Billed monthly — cancel anytime."
        ),
        "price": "1499.00",
        "tier_level": 3,
        "duration": 30,
        "duration_unit": "days",
        "max_products": 0,  # 150+ → unlimited
        "commission_rate": "0.00",
        "commission_discount": "15.00",
        "search_priority_boost": "0.80",
        "featured_listings": True,
        "negotiation_enabled": True,
        "max_markup_percent": "20.00",
        "max_discount_percent": "15.00",
        "trial_days": 7,
        "sort_order": 6,
        "features": ENTERPRISE_FEATURES,
    },
    {
        "name": "Enterprise Yearly",
        "slug": "enterprise-yearly",
        "description": (
            "The flagship tier for high-volume merchants, wholesalers "
            "and multi-branch businesses. Unlimited products, the "
            "largest 15%-point commission discount, full API access, "
            "multi-location support, unlimited staff and a dedicated "
            "account manager. Billed yearly — pay 11 months, get 1 "
            f"month free (save R{Decimal('1499.00')} / year)."
        ),
        "price": _annual("1499.00"),
        "tier_level": 3,
        "duration": 1,
        "duration_unit": "years",
        "max_products": 0,
        "commission_rate": "0.00",
        "commission_discount": "15.00",
        "search_priority_boost": "0.80",
        "featured_listings": True,
        "negotiation_enabled": True,
        "max_markup_percent": "20.00",
        "max_discount_percent": "15.00",
        "trial_days": 7,
        "sort_order": 7,
        "features": ENTERPRISE_FEATURES + [
            "Save R1,499/year (1 month free)",
        ],
    },
]


class Command(BaseCommand):
    help = "Seed business tiers for the Sanoa marketplace"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing tiers before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count = BusinessTier.objects.count()
            BusinessTier.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Deleted {count} existing tiers."
                )
            )

        # Anything not in the new TIERS list is from the old 5-tier
        # layout (Professional Monthly / Yearly) — retire it so the
        # admin dropdowns stop offering it. We don't hard-delete to
        # keep historical subscriptions intact.
        new_slugs = {t["slug"] for t in TIERS}
        deactivated = (
            BusinessTier.objects
            .exclude(slug__in=new_slugs)
            .filter(is_active=True)
        )
        if deactivated.exists():
            count = deactivated.count()
            deactivated.update(is_active=False)
            self.stdout.write(
                self.style.WARNING(
                    f"Deactivated {count} legacy tier row(s)."
                )
            )

        created = 0
        updated = 0

        for tier_data in TIERS:
            slug = tier_data.pop("slug")
            tier, was_created = BusinessTier.objects.update_or_create(
                slug=slug,
                defaults=tier_data,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. created={created} updated={updated}."
        ))
        for tier in BusinessTier.objects.all().order_by('sort_order'):
            billing = (
                'free' if tier.is_free else
                f'{tier.duration}{tier.duration_unit[:1]}'
            )
            price = (
                'Free' if tier.is_free else f'R{tier.price}'
            )
            self.stdout.write(
                f"  {tier.name:<22} {billing:<6} {price:<10} "
                f"disc {tier.commission_discount}%  "
                f"limit {tier.product_limit_display}"
            )
