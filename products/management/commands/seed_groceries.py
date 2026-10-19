"""
Seed sample grocery data:
  - Uses the grocery categories from seed_categories (products go into CHILD categories)
  - 5 grocery vendors (User + IndividualVendorProfile, business_category=retail)
  - 25 sample grocery products linked to those vendors
  - Real product images downloaded from Unsplash

Run:
    python manage.py seed_groceries
    python manage.py seed_groceries --clear
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
    category_slug, get_taxonomy_category,
)
from products.models import Product, ProductImage, VendorCategory

User = get_user_model()

VENDOR_PASSWORD = "Sanoa12345!"

OPENING_HOURS = {
    "0": [{"open": "07:00", "close": "19:00"}],
    "1": [{"open": "07:00", "close": "19:00"}],
    "2": [{"open": "07:00", "close": "19:00"}],
    "3": [{"open": "07:00", "close": "19:00"}],
    "4": [{"open": "07:00", "close": "20:00"}],
    "5": [{"open": "08:00", "close": "20:00"}],
    "6": [{"open": "08:00", "close": "15:00"}],
}


# ---------------------------------------------------------------------------
# Vendors — individual vendor profiles in groceries (retail) mode
# ---------------------------------------------------------------------------
VENDORS = [
    {
        "email": "freshmarket@sanoa.test",
        "username": "freshmarket",
        "first_name": "Nomsa",
        "last_name": "Ndlovu",
        "phone_number": "+27821112301",
        "store_name": "Fresh Market",
        "store_description": "Farm-fresh fruit, veg and juices from Joburg's best growers.",
        "vendor_type": "market_trader",
        "trading_city": "Johannesburg",
        "trading_province": "Gauteng",
        "latitude": Decimal("-26.195246"),
        "longitude": Decimal("28.034088"),
    },
    {
        "email": "kasibutchery@sanoa.test",
        "username": "kasibutchery",
        "first_name": "Bongani",
        "last_name": "Zulu",
        "phone_number": "+27821112302",
        "store_name": "Kasi Butchery",
        "store_description": "Quality braai meat and everyday cuts, cut fresh every morning.",
        "vendor_type": "local_brand",
        "trading_city": "Soweto",
        "trading_province": "Gauteng",
        "latitude": Decimal("-26.267800"),
        "longitude": Decimal("27.858500"),
    },
    {
        "email": "capedairy@sanoa.test",
        "username": "capedairy",
        "first_name": "Pieter",
        "last_name": "Botha",
        "phone_number": "+27821112303",
        "store_name": "Cape Dairy Farm",
        "store_description": "Fresh milk and free-range eggs straight from our Boland farm.",
        "vendor_type": "local_brand",
        "trading_city": "Stellenbosch",
        "trading_province": "Western Cape",
        "latitude": Decimal("-33.932105"),
        "longitude": Decimal("18.860152"),
    },
    {
        "email": "oumasbakery@sanoa.test",
        "username": "oumasbakery",
        "first_name": "Annatjie",
        "last_name": "van der Merwe",
        "phone_number": "+27821112304",
        "store_name": "Ouma's Bakery",
        "store_description": "Old-fashioned loaves and rolls baked fresh before sunrise.",
        "vendor_type": "home_business",
        "trading_city": "Bloemfontein",
        "trading_province": "Free State",
        "latitude": Decimal("-29.085214"),
        "longitude": Decimal("26.159576"),
    },
    {
        "email": "spazacorner@sanoa.test",
        "username": "spazacorner",
        "first_name": "Lwazi",
        "last_name": "Mthembu",
        "phone_number": "+27821112305",
        "store_name": "Spaza Corner",
        "store_description": "Your neighbourhood spaza for pantry staples, snacks and treats.",
        "vendor_type": "tuck_shop",
        "trading_city": "Durban",
        "trading_province": "KwaZulu-Natal",
        "latitude": Decimal("-29.858680"),
        "longitude": Decimal("31.021840"),
    },
]


# ---------------------------------------------------------------------------
# Products — 25 sample grocery items.
# "category" is (grocery parent name, child name) from
# seed_categories.GROCERY_CATEGORIES. Photo IDs are Unsplash CDN identifiers.
# ---------------------------------------------------------------------------
PRODUCTS = [
    # --- Fresh Market: fruit, veg, juice ---------------------------------
    {
        "name": "Bananas 1kg",
        "description": "Sweet, ripe bananas from Tzaneen — perfect for lunchboxes, smoothies and banana bread.",
        "short_description": "Ripe Tzaneen bananas, sold per kg.",
        "price": "24.99",
        "stock": 120,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Fruit"),
        "photo_id": "1528825871115-3581a5387919",
    },
    {
        "name": "Strawberries 400g Punnet",
        "description": "Juicy red strawberries picked in the Western Cape. Rinse and enjoy, or serve with cream.",
        "short_description": "Fresh strawberries, 400g punnet.",
        "price": "44.99",
        "compare_at_price": "54.99",
        "stock": 60,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Fruit"),
        "photo_id": "1601004890684-d8cbf643f5f2",
    },
    {
        "name": "Seasonal Fruit Box 5kg",
        "description": "A mixed box of the best fruit in season — mangoes, kiwis, grapes and more, hand-packed daily.",
        "short_description": "5kg box of mixed seasonal fruit.",
        "price": "189.00",
        "compare_at_price": "219.00",
        "stock": 25,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Fruit"),
        "photo_id": "1619566636858-adf3ef46400b",
    },
    {
        "name": "Whole Watermelon",
        "description": "A big, sweet summer watermelon (approx. 6-8kg). Ideal for braais and hot Highveld afternoons.",
        "short_description": "Whole sweet watermelon, approx. 6-8kg.",
        "price": "59.99",
        "stock": 30,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Fruit"),
        "photo_id": "1587049352846-4a222e784d38",
    },
    {
        "name": "Fresh Cherries 250g",
        "description": "Plump, dark summer cherries from Ceres. A seasonal treat.",
        "short_description": "Ceres cherries, 250g.",
        "price": "69.99",
        "stock": 40,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Fruit"),
        "photo_id": "1559181567-c3190ca9959b",
    },
    {
        "name": "Tropical Fruit Mix 2kg",
        "description": "Papaya, oranges, lemons and avocados — a bright, vitamin-packed mix for the week.",
        "short_description": "2kg mix of papaya, citrus and avo.",
        "price": "99.00",
        "stock": 35,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Fruit"),
        "photo_id": "1610832958506-aa56368176cf",
    },
    {
        "name": "Veggie Market Box 4kg",
        "description": "Potatoes, onions, tomatoes, carrots, butternut and greens — everything for a week of cooking.",
        "short_description": "4kg box of mixed market vegetables.",
        "price": "129.00",
        "compare_at_price": "149.00",
        "stock": 40,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Vegetables"),
        "photo_id": "1488459716781-31db52582fe9",
    },
    {
        "name": "Weekly Produce Hamper",
        "description": "Our biggest hamper: a full family's worth of fresh fruit and vegetables, packed to order.",
        "short_description": "Family-size fruit & veg hamper.",
        "price": "349.00",
        "compare_at_price": "399.00",
        "stock": 15,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Vegetables"),
        "photo_id": "1542838132-92c53300491e",
    },
    {
        "name": "Salad Greens & Cucumber Pack",
        "description": "Crisp lettuce, baby spinach, spring onions and an English cucumber — salad sorted.",
        "short_description": "Mixed salad greens with cucumber.",
        "price": "34.99",
        "stock": 50,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Fresh Produce", "Herbs & Salad Greens"),
        "photo_id": "1584473457406-6240486418e9",
    },
    {
        "name": "100% Orange Juice 2L",
        "description": "Freshly squeezed orange juice with no added sugar or preservatives. Keep refrigerated.",
        "short_description": "Fresh-squeezed orange juice, 2L.",
        "price": "42.99",
        "stock": 70,
        "vendor": "freshmarket@sanoa.test",
        "category": ("Beverages", "Juices"),
        "photo_id": "1600271886742-f049cd451bba",
    },
    # --- Kasi Butchery: beef ------------------------------------------------
    {
        "name": "Beef Rump Steak 1kg",
        "description": "Matured, tender rump steak cut to braai thickness. Season with braai spice and flame-grill.",
        "short_description": "Matured rump steak, 1kg.",
        "price": "189.99",
        "compare_at_price": "209.99",
        "stock": 30,
        "vendor": "kasibutchery@sanoa.test",
        "category": ("Meat, Poultry & Fish", "Beef"),
        "photo_id": "1607623814075-e51df1bdc82f",
    },
    {
        "name": "Beef Stewing Cubes 1kg",
        "description": "Bone-in and boneless beef chunks for potjiekos, stews and curries.",
        "short_description": "Beef stewing cubes, 1kg.",
        "price": "119.99",
        "stock": 45,
        "vendor": "kasibutchery@sanoa.test",
        "category": ("Meat, Poultry & Fish", "Beef"),
        "photo_id": "1607623814075-e51df1bdc82f",
    },
    # --- Cape Dairy Farm: milk & eggs ----------------------------------------
    {
        "name": "Full Cream Fresh Milk 2L",
        "description": "Rich, creamy full cream milk from grass-fed Boland cows. Pasteurised and bottled daily.",
        "short_description": "Full cream fresh milk, 2L.",
        "price": "32.99",
        "stock": 100,
        "vendor": "capedairy@sanoa.test",
        "category": ("Dairy & Eggs", "Milk & Maas"),
        "photo_id": "1550583724-b2692b85b150",
    },
    {
        "name": "Low Fat Milk 1L",
        "description": "Light and fresh 2% low fat milk — all the goodness with less fat.",
        "short_description": "Low fat fresh milk, 1L carton.",
        "price": "18.99",
        "stock": 100,
        "vendor": "capedairy@sanoa.test",
        "category": ("Dairy & Eggs", "Milk & Maas"),
        "photo_id": "1563636619-e9143da7973b",
    },
    {
        "name": "Farm Milk Glass Bottle 1L",
        "description": "Old-school farm milk in a returnable glass bottle. Bring the bottle back for a deposit refund.",
        "short_description": "Farm milk in a returnable glass bottle.",
        "price": "24.99",
        "stock": 50,
        "vendor": "capedairy@sanoa.test",
        "category": ("Dairy & Eggs", "Milk & Maas"),
        "photo_id": "1576186726115-4d51596775d1",
    },
    {
        "name": "Free-Range Large Eggs (18)",
        "description": "Eighteen large free-range eggs from happy, pasture-raised hens.",
        "short_description": "18 large free-range eggs.",
        "price": "64.99",
        "compare_at_price": "72.99",
        "stock": 80,
        "vendor": "capedairy@sanoa.test",
        "category": ("Dairy & Eggs", "Eggs"),
        "photo_id": "1606787366850-de6330128bfc",
    },
    # --- Ouma's Bakery: bread -------------------------------------------------
    {
        "name": "Farm-Style White Loaf 700g",
        "description": "A soft, crusty farm-style white loaf baked fresh every morning. Lekker with butter and jam.",
        "short_description": "Fresh farm-style white loaf, 700g.",
        "price": "19.99",
        "stock": 60,
        "vendor": "oumasbakery@sanoa.test",
        "category": ("Bakery", "Bread & Rolls"),
        "photo_id": "1509440159596-0249088772ff",
    },
    {
        "name": "Assorted Bread Rolls (12)",
        "description": "A dozen mixed rolls — white, wholewheat and seeded. Perfect for boerewors rolls at the braai.",
        "short_description": "12 assorted fresh bread rolls.",
        "price": "32.99",
        "compare_at_price": "38.99",
        "stock": 50,
        "vendor": "oumasbakery@sanoa.test",
        "category": ("Bakery", "Bread & Rolls"),
        "photo_id": "1608198093002-ad4e005484ec",
    },
    # --- Spaza Corner: pantry & snacks ---------------------------------------
    {
        "name": "Long Grain White Rice 2kg",
        "description": "Fluffy long grain parboiled rice that cooks up perfectly every time. A Sunday-lunch essential.",
        "short_description": "Parboiled long grain rice, 2kg.",
        "price": "44.99",
        "stock": 90,
        "vendor": "spazacorner@sanoa.test",
        "category": ("Pantry Staples", "Rice, Pasta & Noodles"),
        "photo_id": "1586201375761-83865001e31c",
    },
    {
        "name": "Instant Noodles 5-Pack",
        "description": "Quick chicken-flavoured instant noodles, ready in three minutes. Five packs per bundle.",
        "short_description": "Chicken instant noodles, 5 x 73g.",
        "price": "24.99",
        "stock": 150,
        "vendor": "spazacorner@sanoa.test",
        "category": ("Pantry Staples", "Rice, Pasta & Noodles"),
        "photo_id": "1612929633738-8fe44f7ec841",
    },
    {
        "name": "Extra Virgin Olive Oil 500ml",
        "description": "Cold-pressed extra virgin olive oil from the Western Cape. Great for salads and cooking.",
        "short_description": "Cold-pressed olive oil, 500ml.",
        "price": "119.99",
        "compare_at_price": "139.99",
        "stock": 40,
        "vendor": "spazacorner@sanoa.test",
        "category": ("Pantry Staples", "Cooking Oils"),
        "photo_id": "1474979266404-7eaacbcd87c5",
    },
    {
        "name": "Tinned Soup Variety 6 x 400g",
        "description": "Six hearty tins — tomato, minestrone and creamy chicken. Winter warmers for the cupboard.",
        "short_description": "6 assorted tinned soups, 400g each.",
        "price": "89.99",
        "stock": 60,
        "vendor": "spazacorner@sanoa.test",
        "category": ("Pantry Staples", "Tinned Foods"),
        "photo_id": "1534483509719-3feaee7c30da",
    },
    {
        "name": "Chocolate Bar Variety Pack (10)",
        "description": "Ten assorted milk and dark chocolate bars — for lunchboxes, padkos or sharing.",
        "short_description": "10 assorted chocolate bars.",
        "price": "99.99",
        "compare_at_price": "119.99",
        "stock": 75,
        "vendor": "spazacorner@sanoa.test",
        "category": ("Snacks & Sweets", "Chocolates & Sweets"),
        "photo_id": "1621939514649-280e2ee25f60",
    },
    {
        "name": "Salted Potato Chips 125g",
        "description": "Thin and crispy potato chips with just the right amount of salt.",
        "short_description": "Lightly salted potato chips, 125g.",
        "price": "21.99",
        "stock": 140,
        "vendor": "spazacorner@sanoa.test",
        "category": ("Snacks & Sweets", "Chips & Crisps"),
        "photo_id": "1599490659213-e2b9527bd087",
    },
    {
        "name": "Party Snack Bundle (8 Bags)",
        "description": "Eight assorted bags of chips and corn snacks — sorted for parties and match day.",
        "short_description": "8 assorted snack bags.",
        "price": "119.00",
        "compare_at_price": "139.00",
        "stock": 45,
        "vendor": "spazacorner@sanoa.test",
        "category": ("Snacks & Sweets", "Chips & Crisps"),
        "photo_id": "1566478989037-eec170784d0b",
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
    help = "Seed grocery vendors and 25 sample grocery products with Unsplash images."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete previously seeded grocery products and vendors before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            self._clear()

        categories = self._get_categories()
        vendors = self._create_vendors()
        self._create_products(vendors, categories)

        self.stdout.write(self.style.SUCCESS("\nGrocery seeding complete!"))

    # -- helpers ----------------------------------------------------------

    def _clear(self):
        emails = [v["email"] for v in VENDORS]
        product_names = [p["name"] for p in PRODUCTS]
        deleted_p = Product.objects.filter(
            name__in=product_names, vendor__user__email__in=emails,
        ).delete()[0]
        deleted_v = User.objects.filter(email__in=emails).delete()[0]
        self.stdout.write(self.style.WARNING(
            f"Cleared {deleted_p} products and {deleted_v} vendor users."
        ))

    def _get_categories(self):
        categories = {}
        for p in PRODUCTS:
            key = p["category"]
            if key not in categories:
                categories[key] = get_taxonomy_category(category_slug(*key))
        self.stdout.write(f"Using {len(categories)} grocery subcategories.")
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
                user.set_password(VENDOR_PASSWORD)
                user.save()
                self.stdout.write(f"Vendor + created: {v['store_name']} ({user.email})")
            else:
                self.stdout.write(f"Vendor = exists: {v['store_name']} ({user.email})")

            profile, p_created = IndividualVendorProfile.objects.get_or_create(
                user=user,
                defaults={
                    "vendor_type": v["vendor_type"],
                    "business_category": "retail",
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
                profile.id_document.save("id_doc.txt", ContentFile(b"placeholder"), save=False)
                profile.proof_of_address.save("address.txt", ContentFile(b"placeholder"), save=False)
                profile.save()

            # Unified VendorProfile (auto-created by the User post_save signal
            # as a blank skeleton) — fill it so the storefront can list it.
            unified, _ = VendorProfile.objects.get_or_create(
                user=user,
                defaults={"profile_type": "individual", "name": v["store_name"]},
            )
            desired = {
                "profile_type": "individual",
                "business_category": "retail",
                "vendor_type": v["vendor_type"],
                "name": v["store_name"],
                "trading_name": v["store_name"],
                "description": v["store_description"],
                "city": v["trading_city"],
                "province": v["trading_province"],
                "latitude": v["latitude"],
                "longitude": v["longitude"],
                "verification_status": "verified",
                "owner_vetting_passed": True,
                "business_vetting_passed": True,
                "store_active": True,
                "opening_hours": OPENING_HOURS,
            }
            dirty = []
            for field, value in desired.items():
                if getattr(unified, field) != value:
                    setattr(unified, field, value)
                    dirty.append(field)
            if dirty:
                unified.save(update_fields=dirty)

            vendors[v["email"]] = unified
        return vendors

    def _create_products(self, vendors, categories):
        created_count = images_saved = images_failed = 0
        for p in PRODUCTS:
            vendor_profile = vendors[p["vendor"]]
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
                    "stock": p["stock"],
                    "status": "active",
                    "is_featured": bool(p.get("compare_at_price")),
                    "requires_shipping": True,
                    "track_inventory": True,
                },
            )
            if created:
                created_count += 1
            elif product.category_id != category.id:
                product.category = category
                product.save(update_fields=["category"])
                self.stdout.write(f"  ~ {product.name} moved to {category.name}")

            if product.images.exists():
                self.stdout.write(f"  = {product.name} (already seeded)")
                continue

            self.stdout.write(f"  + {product.name} — downloading image...")
            try:
                img_bytes = download_image(p["photo_id"])
            except Exception as exc:
                images_failed += 1
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
            images_saved += 1
            self.stdout.write(self.style.SUCCESS(f"    image saved: {filename}"))

        self.stdout.write(
            f"Products created: {created_count}. Images saved: {images_saved}, "
            f"failed: {images_failed}."
        )
