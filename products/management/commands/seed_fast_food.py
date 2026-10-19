"""
Seed sample fast-food data:
  - Uses the top-level fast food categories from seed_categories
  - 5 fast-food vendors (User + IndividualVendorProfile, business_category=restaurant)
  - 15 sample products linked to those vendors
  - Real product images downloaded from Unsplash

Run:
    python manage.py seed_fast_food
    python manage.py seed_fast_food --clear
"""
import urllib.request
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from business.models import IndividualVendorProfile, VendorProfile
from products.management.commands.seed_categories import (
    FAST_FOOD_CATEGORIES, category_slug, get_taxonomy_category,
)
from products.models import Product, ProductImage, VendorCategory

User = get_user_model()


# ---------------------------------------------------------------------------
# Vendors — individual vendor profiles in restaurant mode
# ---------------------------------------------------------------------------
VENDORS = [
    {
        "email": "burgerbarn@sanoa.test",
        "username": "burgerbarn",
        "first_name": "Sipho",
        "last_name": "Dlamini",
        "phone_number": "+27821112201",
        "store_name": "Burger Barn",
        "store_description": "Home of the juiciest flame-grilled burgers in town.",
        "vendor_type": "food_vendor",
        "trading_city": "Johannesburg",
        "trading_province": "Gauteng",
    },
    {
        "email": "pizzapalace@sanoa.test",
        "username": "pizzapalace",
        "first_name": "Maria",
        "last_name": "Conti",
        "phone_number": "+27821112202",
        "store_name": "Pizza Palace",
        "store_description": "Authentic wood-fired pizzas baked to perfection.",
        "vendor_type": "food_vendor",
        "trading_city": "Cape Town",
        "trading_province": "Western Cape",
    },
    {
        "email": "chickenshack@sanoa.test",
        "username": "chickenshack",
        "first_name": "Thabo",
        "last_name": "Mokoena",
        "phone_number": "+27821112203",
        "store_name": "Chicken Shack",
        "store_description": "Crispy fried chicken, wings and family buckets.",
        "vendor_type": "food_vendor",
        "trading_city": "Durban",
        "trading_province": "KwaZulu-Natal",
    },
    {
        "email": "tacofiesta@sanoa.test",
        "username": "tacofiesta",
        "first_name": "Carlos",
        "last_name": "Mendoza",
        "phone_number": "+27821112204",
        "store_name": "Taco Fiesta",
        "store_description": "Mexican-inspired tacos, burritos and wraps made fresh daily.",
        "vendor_type": "food_vendor",
        "trading_city": "Pretoria",
        "trading_province": "Gauteng",
    },
    {
        "email": "sweettreats@sanoa.test",
        "username": "sweettreats",
        "first_name": "Lerato",
        "last_name": "Khumalo",
        "phone_number": "+27821112205",
        "store_name": "Sweet Treats Cafe",
        "store_description": "Donuts, milkshakes, coffee, ice cream and desserts.",
        "vendor_type": "food_vendor",
        "trading_city": "Port Elizabeth",
        "trading_province": "Eastern Cape",
    },
]


# ---------------------------------------------------------------------------
# Products — 15 sample fast food items
# Each entry maps to (vendor email, top-level fast food category name from
# seed_categories.FAST_FOOD_CATEGORIES, unsplash photo id)
# Photo IDs are stable Unsplash CDN identifiers (free to use under Unsplash license).
# ---------------------------------------------------------------------------
PRODUCTS = [
    {
        "name": "Classic Cheeseburger",
        "description": "200g flame-grilled beef patty, melted cheddar, lettuce, tomato, pickles and our signature burger sauce on a toasted brioche bun.",
        "short_description": "Juicy beef burger with cheddar and signature sauce.",
        "price": "75.00",
        "compare_at_price": "89.00",
        "vendor": "burgerbarn@sanoa.test",
        "category": "Burgers",
        "photo_id": "1568901346375-23c9450c58cd",
    },
    {
        "name": "Double Bacon Burger",
        "description": "Two beef patties, double cheese, crispy bacon, caramelised onions and BBQ sauce.",
        "short_description": "Double beef and bacon stacked burger.",
        "price": "115.00",
        "compare_at_price": "129.00",
        "vendor": "burgerbarn@sanoa.test",
        "category": "Burgers",
        "photo_id": "1572802419224-296b0aeee0d9",
    },
    {
        "name": "Crispy Chicken Burger",
        "description": "Buttermilk-fried chicken fillet, crisp lettuce, mayo and pickles in a soft sesame bun.",
        "short_description": "Buttermilk-fried chicken burger.",
        "price": "82.00",
        "vendor": "burgerbarn@sanoa.test",
        "category": "Burgers",
        "photo_id": "1606755962773-d324e0a13086",
    },
    {
        "name": "Margherita Pizza",
        "description": "San Marzano tomato sauce, fresh mozzarella, basil and extra virgin olive oil on a hand-stretched base.",
        "short_description": "Classic Margherita with fresh basil.",
        "price": "120.00",
        "vendor": "pizzapalace@sanoa.test",
        "category": "Pizza",
        "photo_id": "1604382354936-07c5d9983bd3",
    },
    {
        "name": "Pepperoni Pizza",
        "description": "Loaded with spicy pepperoni, mozzarella and a rich tomato sauce. Wood-fired to perfection.",
        "short_description": "Wood-fired pepperoni pizza.",
        "price": "139.00",
        "compare_at_price": "159.00",
        "vendor": "pizzapalace@sanoa.test",
        "category": "Pizza",
        "photo_id": "1565299624946-b28f40a0ae38",
    },
    {
        "name": "BBQ Chicken Pizza",
        "description": "Smoky BBQ sauce, grilled chicken, red onion, peppers and mozzarella.",
        "short_description": "Smoky BBQ chicken pizza.",
        "price": "145.00",
        "vendor": "pizzapalace@sanoa.test",
        "category": "Pizza",
        "photo_id": "1513104890138-7c749659a591",
    },
    {
        "name": "Crispy Fried Chicken Bucket",
        "description": "8 pieces of golden, crispy fried chicken seasoned with our secret 11-spice blend.",
        "short_description": "8-piece secret-recipe fried chicken.",
        "price": "189.00",
        "compare_at_price": "215.00",
        "vendor": "chickenshack@sanoa.test",
        "category": "Chicken & Wings",
        "photo_id": "1626082927389-6cd097cdc6ec",
    },
    {
        "name": "Buffalo Hot Wings",
        "description": "Crispy chicken wings tossed in tangy buffalo sauce, served with blue cheese dip.",
        "short_description": "Spicy buffalo wings with blue cheese dip.",
        "price": "95.00",
        "vendor": "chickenshack@sanoa.test",
        "category": "Chicken & Wings",
        "photo_id": "1608039829572-78524f79c4c7",
    },
    {
        "name": "Chicken Tenders & Fries",
        "description": "5 hand-breaded chicken tenders served with golden fries and dipping sauce.",
        "short_description": "Chicken tenders with golden fries.",
        "price": "89.00",
        "vendor": "chickenshack@sanoa.test",
        "category": "Chicken & Wings",
        "photo_id": "1562967914-608f82629710",
    },
    {
        "name": "Beef Tacos (3pcs)",
        "description": "Three soft tacos filled with seasoned beef, lettuce, cheese, salsa and sour cream.",
        "short_description": "Three soft beef tacos.",
        "price": "78.00",
        "vendor": "tacofiesta@sanoa.test",
        "category": "Wraps, Subs & Tacos",
        "photo_id": "1565299585323-38d6b0865b47",
    },
    {
        "name": "Chicken Burrito",
        "description": "Large flour tortilla packed with grilled chicken, rice, beans, cheese, salsa and guacamole.",
        "short_description": "Loaded chicken burrito with guac.",
        "price": "92.00",
        "compare_at_price": "105.00",
        "vendor": "tacofiesta@sanoa.test",
        "category": "Wraps, Subs & Tacos",
        "photo_id": "1626700051175-6818013e1d4f",
    },
    {
        "name": "Loaded Beef Nachos",
        "description": "Crispy tortilla chips topped with seasoned beef, melted cheese, jalapeños, guacamole and sour cream.",
        "short_description": "Loaded nachos with beef and cheese.",
        "price": "85.00",
        "vendor": "tacofiesta@sanoa.test",
        "category": "Sides & Snacks",
        "photo_id": "1582169296194-e4d644c48063",
    },
    {
        "name": "Golden French Fries",
        "description": "Crispy golden fries lightly salted, served hot. The perfect side.",
        "short_description": "Crispy salted golden fries.",
        "price": "35.00",
        "vendor": "burgerbarn@sanoa.test",
        "category": "Sides & Snacks",
        "photo_id": "1573080496219-bb080dd4f877",
    },
    {
        "name": "Chocolate Milkshake",
        "description": "Thick and creamy chocolate milkshake topped with whipped cream and chocolate sauce.",
        "short_description": "Thick chocolate milkshake with whipped cream.",
        "price": "55.00",
        "vendor": "sweettreats@sanoa.test",
        "category": "Desserts & Shakes",
        "photo_id": "1572490122747-3968b75cc699",
    },
    {
        "name": "Glazed Donuts (6pcs)",
        "description": "Half a dozen freshly baked donuts with sweet sugar glaze. Soft and fluffy.",
        "short_description": "6 freshly glazed donuts.",
        "price": "65.00",
        "compare_at_price": "75.00",
        "vendor": "sweettreats@sanoa.test",
        "category": "Desserts & Shakes",
        "photo_id": "1551024601-bec78aea704b",
    },
]


def unsplash_url(photo_id, w=900):
    return f"https://images.unsplash.com/photo-{photo_id}?w={w}&q=80&auto=format&fit=crop"


def download_image(photo_id):
    url = unsplash_url(photo_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------
class Command(BaseCommand):
    help = "Seed fast-food vendors and 15 sample products (with Unsplash images) into the fast food categories."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete previously seeded fast-food products and vendors before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            self._clear()

        # 1. Categories (top-level fast food categories from the taxonomy)
        categories = self._get_categories()

        # 2. Vendors
        vendors = self._create_vendors()

        # 3. Products + images
        self._create_products(vendors, categories)

        self.stdout.write(self.style.SUCCESS("\nFast-food seeding complete!"))

    # -- helpers ----------------------------------------------------------

    def _clear(self):
        emails = [v["email"] for v in VENDORS]
        product_names = [p["name"] for p in PRODUCTS]
        deleted_p = Product.objects.filter(name__in=product_names).delete()[0]
        deleted_v = User.objects.filter(email__in=emails).delete()[0]
        self.stdout.write(self.style.WARNING(
            f"Cleared {deleted_p} products and {deleted_v} vendor users."
        ))

    def _get_categories(self):
        categories = {}
        for name in FAST_FOOD_CATEGORIES:
            categories[name] = get_taxonomy_category(category_slug(name))
        self.stdout.write(f"Using {len(categories)} fast food categories.")
        return categories

    def _create_vendors(self):
        vendors = {}
        for v in VENDORS:
            user, created = User.objects.get_or_create(
                email=v["email"],
                defaults={
                    "username": v["username"],
                    "first_name": v["first_name"],
                    "last_name": v["last_name"],
                    "phone_number": v["phone_number"],
                    "user_type": "vendor",
                    "is_verified": True,
                },
            )
            if created:
                user.set_password("Sanoa12345!")
                user.save()
                self.stdout.write(f"Vendor + created: {v['store_name']} ({user.email})")
            else:
                self.stdout.write(f"Vendor = exists: {v['store_name']} ({user.email})")

            profile, p_created = IndividualVendorProfile.objects.get_or_create(
                user=user,
                defaults={
                    "vendor_type": v["vendor_type"],
                    "business_category": "restaurant",
                    "store_name": v["store_name"],
                    "store_description": v["store_description"],
                    "id_number": "0000000000000",
                    "trading_city": v["trading_city"],
                    "trading_province": v["trading_province"],
                    "verification_status": "verified",
                    "store_active": True,
                },
            )
            if p_created:
                # Required FileFields — write tiny placeholder content
                placeholder = ContentFile(b"placeholder", name="placeholder.txt")
                profile.id_document.save("id_doc.txt", placeholder, save=False)
                profile.proof_of_address.save("address.txt", ContentFile(b"placeholder"), save=False)
                profile.save()

            # Keep the unified VendorProfile (used by Product.vendor and the
            # storefront filters) in restaurant mode with a display name.
            unified, _ = VendorProfile.objects.get_or_create(
                user=user,
                defaults={"profile_type": "individual", "name": v["store_name"]},
            )
            unified_desired = {
                "business_category": "restaurant",
                "name": unified.name or v["store_name"],
                "vendor_type": unified.vendor_type or v["vendor_type"],
                "description": unified.description or v["store_description"],
                "city": unified.city or v["trading_city"],
                "province": unified.province or v["trading_province"],
            }
            dirty = [f for f, val in unified_desired.items() if getattr(unified, f) != val]
            for f in dirty:
                setattr(unified, f, unified_desired[f])
            if dirty:
                unified.save(update_fields=dirty)

            vendors[v["email"]] = user
        return vendors

    def _create_products(self, vendors, categories):
        for p in PRODUCTS:
            vendor_user = vendors[p["vendor"]]
            # Product.vendor is a VendorProfile; the post_save signal on
            # User creates an empty unified VendorProfile for vendor users,
            # so we just look it up here.
            vendor_profile, _ = VendorProfile.objects.get_or_create(
                user=vendor_user,
                defaults={'profile_type': 'individual', 'name': vendor_user.email},
            )
            category = categories[p["category"]]
            VendorCategory.objects.get_or_create(vendor=vendor_profile, category=category)

            product, created = Product.objects.get_or_create(
                name=p["name"],
                vendor=vendor_profile,
                defaults={
                    "description": p["description"],
                    "short_description": p["short_description"],
                    "category": category,
                    "price": Decimal(p["price"]),
                    "compare_at_price": (
                        Decimal(p["compare_at_price"]) if p.get("compare_at_price") else None
                    ),
                    "stock": 100,
                    "status": "active",
                    "is_featured": True,
                    "requires_shipping": False,
                    "track_inventory": True,
                },
            )

            if not created and product.category_id != category.id:
                product.category = category
                product.save(update_fields=["category"])
                self.stdout.write(f"  ~ {product.name} moved to {category.name}")

            if not created and product.images.exists():
                self.stdout.write(f"  = {product.name} (already seeded)")
                continue

            self.stdout.write(f"  + {product.name} — downloading image...")
            try:
                img_bytes = download_image(p["photo_id"])
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f"    ! Failed to download image for {product.name}: {exc}"
                ))
                continue

            filename = f"{slugify(product.name)}.jpg"
            pi = ProductImage(
                product=product,
                alt_text=f"{product.name} - product image",
                is_primary=True,
                sort_order=0,
            )
            pi.image.save(filename, ContentFile(img_bytes), save=True)
            self.stdout.write(self.style.SUCCESS(f"    image saved: {filename}"))
