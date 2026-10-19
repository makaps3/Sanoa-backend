"""
Management command to seed buyer credit plans for the Sanoa marketplace.
Each plan has both a monthly and yearly billing option.
Yearly pricing gives ~2 months free (pay for 10 months).
"""
from django.core.management.base import BaseCommand

from subscriptions.models import Plan


PLANS = [
    # ── Sanoa Basic Monthly ──
    {
        "name": "Sanoa Basic Monthly",
        "slug": "sanoa-basic-monthly",
        "description": (
            "Start buying on credit with Sanoa Basic. Perfect for budget-conscious "
            "shoppers who want the flexibility to pay later on selected items. "
            "Get a R500 credit limit with affordable monthly payments and access "
            "to exclusive subscriber deals. Billed monthly — cancel anytime."
        ),
        "price": "49.00",
        "duration": 30,
        "duration_unit": "days",
        "credit_limit": "500.00",
        "interest_rate": "5.00",
        "max_items_on_credit": 1,
        "requires_follower": True,
        "trial_days": 7,
        "sort_order": 1,
        "features": [
            "R500 credit limit per cycle",
            "1 item on credit at a time",
            "5% monthly interest rate",
            "7-day free trial",
            "Must follow at least 1 business",
            "10% deposit required on credit purchases",
            "Basic purchase history & tracking",
            "Access to subscriber-only deals",
            "Email support",
        ],
    },
    # ── Sanoa Basic Yearly ──
    {
        "name": "Sanoa Basic Yearly",
        "slug": "sanoa-basic-yearly",
        "description": (
            "Start buying on credit with Sanoa Basic. Perfect for budget-conscious "
            "shoppers who want the flexibility to pay later on selected items. "
            "Get a R500 credit limit with affordable payments and access "
            "to exclusive subscriber deals. Billed yearly — save R98 (2 months free)."
        ),
        "price": "490.00",
        "duration": 1,
        "duration_unit": "years",
        "credit_limit": "500.00",
        "interest_rate": "5.00",
        "max_items_on_credit": 1,
        "requires_follower": True,
        "trial_days": 7,
        "sort_order": 2,
        "features": [
            "R500 credit limit per cycle",
            "1 item on credit at a time",
            "5% monthly interest rate",
            "7-day free trial",
            "Must follow at least 1 business",
            "10% deposit required on credit purchases",
            "Basic purchase history & tracking",
            "Access to subscriber-only deals",
            "Email support",
            "Save R98/year (2 months free)",
        ],
    },

    # ── Sanoa Plus Monthly ──
    {
        "name": "Sanoa Plus Monthly",
        "slug": "sanoa-plus-monthly",
        "description": (
            "Unlock more buying power with Sanoa Plus. Ideal for regular shoppers "
            "who want higher credit limits, the ability to have multiple items on "
            "credit, and a lower interest rate. Enjoy priority customer support "
            "and early access to sales and promotions. Billed monthly — cancel anytime."
        ),
        "price": "99.00",
        "duration": 30,
        "duration_unit": "days",
        "credit_limit": "2000.00",
        "interest_rate": "3.50",
        "max_items_on_credit": 3,
        "requires_follower": True,
        "trial_days": 7,
        "sort_order": 3,
        "features": [
            "R2,000 credit limit per cycle",
            "Up to 3 items on credit simultaneously",
            "3.5% monthly interest rate",
            "7-day free trial",
            "Must follow at least 1 business",
            "10% deposit required on credit purchases",
            "Detailed purchase history & analytics",
            "Early access to sales & promotions",
            "Priority email & chat support",
            "Monthly spending reports",
        ],
    },
    # ── Sanoa Plus Yearly ──
    {
        "name": "Sanoa Plus Yearly",
        "slug": "sanoa-plus-yearly",
        "description": (
            "Unlock more buying power with Sanoa Plus. Ideal for regular shoppers "
            "who want higher credit limits, the ability to have multiple items on "
            "credit, and a lower interest rate. Enjoy priority customer support "
            "and early access to sales and promotions. Billed yearly — save R198 (2 months free)."
        ),
        "price": "990.00",
        "duration": 1,
        "duration_unit": "years",
        "credit_limit": "2000.00",
        "interest_rate": "3.50",
        "max_items_on_credit": 3,
        "requires_follower": True,
        "trial_days": 7,
        "sort_order": 4,
        "features": [
            "R2,000 credit limit per cycle",
            "Up to 3 items on credit simultaneously",
            "3.5% monthly interest rate",
            "7-day free trial",
            "Must follow at least 1 business",
            "10% deposit required on credit purchases",
            "Detailed purchase history & analytics",
            "Early access to sales & promotions",
            "Priority email & chat support",
            "Monthly spending reports",
            "Save R198/year (2 months free)",
        ],
    },

    # ── Sanoa Premium Monthly ──
    {
        "name": "Sanoa Premium Monthly",
        "slug": "sanoa-premium-monthly",
        "description": (
            "The ultimate credit experience for power shoppers. Sanoa Premium "
            "gives you the highest credit limit, the lowest interest rate, and "
            "the ability to have up to 5 items on credit at once. Enjoy VIP "
            "customer support, exclusive deals, cashback rewards, and flexible "
            "repayment options. Billed monthly — cancel anytime."
        ),
        "price": "149.00",
        "duration": 30,
        "duration_unit": "days",
        "credit_limit": "5000.00",
        "interest_rate": "2.00",
        "max_items_on_credit": 5,
        "requires_follower": True,
        "trial_days": 7,
        "sort_order": 5,
        "features": [
            "R5,000 credit limit per cycle",
            "Up to 5 items on credit simultaneously",
            "2% monthly interest rate (lowest)",
            "7-day free trial",
            "Must follow at least 1 business",
            "10% deposit required on credit purchases",
            "Full purchase analytics & insights",
            "Exclusive VIP deals & early access",
            "Cashback rewards on repayments",
            "Flexible repayment schedules",
            "Dedicated VIP support (phone, email, chat)",
            "Monthly credit score reports",
        ],
    },
    # ── Sanoa Premium Yearly ──
    {
        "name": "Sanoa Premium Yearly",
        "slug": "sanoa-premium-yearly",
        "description": (
            "The ultimate credit experience for power shoppers. Sanoa Premium "
            "gives you the highest credit limit, the lowest interest rate, and "
            "the ability to have up to 5 items on credit at once. Enjoy VIP "
            "customer support, exclusive deals, cashback rewards, and flexible "
            "repayment options. Billed yearly — save R298 (2 months free)."
        ),
        "price": "1490.00",
        "duration": 1,
        "duration_unit": "years",
        "credit_limit": "5000.00",
        "interest_rate": "2.00",
        "max_items_on_credit": 5,
        "requires_follower": True,
        "trial_days": 7,
        "sort_order": 6,
        "features": [
            "R5,000 credit limit per cycle",
            "Up to 5 items on credit simultaneously",
            "2% monthly interest rate (lowest)",
            "7-day free trial",
            "Must follow at least 1 business",
            "10% deposit required on credit purchases",
            "Full purchase analytics & insights",
            "Exclusive VIP deals & early access",
            "Cashback rewards on repayments",
            "Flexible repayment schedules",
            "Dedicated VIP support (phone, email, chat)",
            "Monthly credit score reports",
            "Save R298/year (2 months free)",
        ],
    },
]


class Command(BaseCommand):
    help = "Seed buyer credit plans for the Sanoa marketplace"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing plans before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count = Plan.objects.count()
            Plan.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing plans."))

        created = 0
        updated = 0

        for plan_data in PLANS:
            slug = plan_data.pop("slug")
            name = plan_data.get("name")

            plan, was_created = Plan.objects.update_or_create(
                slug=slug,
                defaults=plan_data,
            )

            if was_created:
                created += 1
                billing = "yearly" if plan.duration_unit == "years" else "monthly"
                self.stdout.write(f"  + {name} (R{plan.price}/{billing})")
            else:
                updated += 1
                self.stdout.write(f"  ~ {name} (updated)")

            # Re-add slug for idempotency
            plan_data["slug"] = slug

        self.stdout.write(
            self.style.SUCCESS(f"\nDone! Created {created}, updated {updated}.")
        )

        # Summary table
        self.stdout.write("\n  Buyer Credit Plan Summary:")
        self.stdout.write("  " + "-" * 95)
        self.stdout.write(
            f"  {'Plan':<28} {'Billing':<10} {'Price':<12} {'Credit Limit':<15} "
            f"{'Interest':<12} {'Max Items'}"
        )
        self.stdout.write("  " + "-" * 95)

        for plan in Plan.objects.all().order_by('sort_order'):
            billing = 'Yearly' if plan.duration_unit == 'years' else 'Monthly'
            self.stdout.write(
                f"  {plan.name:<28} {billing:<10} R{plan.price:<11} "
                f"R{plan.credit_limit:<14} {plan.interest_rate}%{'':<8} "
                f"{plan.max_items_on_credit}"
            )

        self.stdout.write("  " + "-" * 95)
