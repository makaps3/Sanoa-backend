"""
Seed the Sanoa system category taxonomy.

Sanoa now serves exactly two storefront modes:
  * Groceries  (business_category='retail')     — 9 parents, each with children
  * Fast Food  (business_category='restaurant') — 9 top-level categories

Usage:
    python manage.py seed_categories            # create / sync the taxonomy
    python manage.py seed_categories --prune    # also migrate legacy data and
                                                # delete every other system category
    python manage.py seed_categories --clear    # wipe ALL categories first

--prune does, in order:
  1. Promote the legacy 'Restaurant & Fast Food' children to top-level fast
     food categories (keeping their rows, so products / links are preserved).
  2. Seed / sync the taxonomy below.
  3. Re-home products from the legacy 'Food & Groceries' and
     'Restaurant & Fast Food' trees into the matching new categories.
  4. Delete every system category (vendor=None) that is not part of the
     taxonomy. Products in those categories are deleted via CASCADE.
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from products.models import Category, Product, VendorCategory


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------
# Groceries: { "Parent": ("description", is_featured, { "Child": "description" }) }
GROCERY_CATEGORIES = {
    "Fresh Produce": (
        "Farm-fresh fruit, veggies and herbs from local growers and markets across Mzansi.",
        True,
        {
            "Fruit": "Apples, bananas, citrus, mangoes, berries and seasonal fruit.",
            "Vegetables": "Potatoes, onions, tomatoes, butternut, spinach, cabbage and more.",
            "Herbs & Salad Greens": "Fresh coriander, parsley, basil, lettuce, rocket and salad mixes.",
        },
    ),
    "Meat, Poultry & Fish": (
        "Quality cuts for the braai and the pot — beef, chicken, lamb, wors and fresh fish.",
        True,
        {
            "Beef": "Steaks, mince, stewing beef, brisket and roasts.",
            "Chicken": "Whole birds, braai packs, fillets, drumsticks and wings.",
            "Pork & Lamb": "Chops, ribs, lamb shanks, pork belly and roasts.",
            "Boerewors & Sausages": "Traditional boerewors, chakalaka wors, russians and viennas.",
            "Fish & Seafood": "Hake, snoek, salmon, prawns, calamari and tinned pilchards.",
        },
    ),
    "Dairy & Eggs": (
        "Fresh milk, amasi, cheese, yoghurt, butter and free-range eggs.",
        True,
        {
            "Milk & Maas": "Full cream, low fat, long-life milk and amasi (maas).",
            "Cheese": "Cheddar, gouda, mozzarella, feta and cheese slices.",
            "Yoghurt": "Plain, flavoured, double-cream and drinking yoghurt.",
            "Butter & Margarine": "Salted and unsalted butter, margarine and spreads.",
            "Eggs": "Large and extra-large free-range and barn eggs.",
        },
    ),
    "Bakery": (
        "Freshly baked bread, rolls, rusks and treats — from the corner bakery to your door.",
        True,
        {
            "Bread & Rolls": "White, brown, wholewheat and seed loaves, vetkoek and bread rolls.",
            "Rusks & Biscuits": "Buttermilk rusks, Marie biscuits, cookies and crackers.",
            "Cakes & Pastries": "Koeksisters, milk tarts, muffins, cakes and croissants.",
        },
    ),
    "Pantry Staples": (
        "The everyday basics — mielie meal, rice, oil, spices and tins to keep the cupboard full.",
        True,
        {
            "Maize Meal & Grains": "Super maize meal, samp, mabele, soya mince and dried beans.",
            "Rice, Pasta & Noodles": "White and brown rice, spaghetti, macaroni and instant noodles.",
            "Cooking Oils": "Sunflower oil, olive oil, canola and cooking sprays.",
            "Spices, Sauces & Condiments": "Braai spice, curry powder, chutney, tomato sauce, chakalaka and mayo.",
            "Tinned Foods": "Baked beans, pilchards, tinned veg, soups and ready-to-eat tins.",
            "Baking Essentials": "Cake flour, sugar, baking powder, yeast and custard powder.",
        },
    ),
    "Breakfast & Cereals": (
        "Start the day right with cereals, oats, porridge and something sweet for your toast.",
        False,
        {
            "Cereals": "Corn flakes, muesli, bran flakes and kids' cereals.",
            "Oats & Porridge": "Rolled oats, instant oats, maltabella and mabele porridge.",
            "Spreads, Jams & Honey": "Peanut butter, apricot jam, honey and savoury spreads.",
        },
    ),
    "Snacks & Sweets": (
        "Chips, biltong, chocolates and nuts for padkos, lunchboxes and movie nights.",
        False,
        {
            "Chips & Crisps": "Potato chips, corn snacks, puffs and tortilla chips.",
            "Biltong & Droëwors": "Beef and game biltong, chilli bites and droëwors.",
            "Chocolates & Sweets": "Chocolate slabs, bars, sweets and gums.",
            "Nuts & Dried Fruit": "Peanuts, cashews, trail mix, dried mango and raisins.",
        },
    ),
    "Beverages": (
        "Cold drinks, juices, water, rooibos and coffee for every household.",
        False,
        {
            "Soft Drinks": "Fizzy drinks, cordials, energy drinks and mixers.",
            "Juices": "Fruit juices, nectars and 100% pressed juice.",
            "Water": "Still, sparkling and flavoured water.",
            "Tea & Coffee": "Rooibos, black tea, instant and ground coffee.",
        },
    ),
    "Frozen Foods": (
        "Frozen veg, ready meals and ice cream — convenience straight from the freezer.",
        False,
        {
            "Frozen Vegetables": "Mixed veg, peas, corn, stir-fry mixes and oven chips.",
            "Frozen Meals": "Pies, ready meals, pizzas, crumbed fish and nuggets.",
            "Ice Cream": "Tubs, cones, lollies and frozen desserts.",
        },
    ),
}

# Fast food: { "Name": ("description", is_featured) } — top-level, no children.
FAST_FOOD_CATEGORIES = {
    "Burgers": ("Flame-grilled beef, chicken and veggie burgers stacked with fresh toppings.", True),
    "Pizza": ("Wood-fired and oven-baked pizzas with classic and gourmet toppings.", True),
    "Chicken & Wings": ("Fried and flame-grilled chicken, wings, strips and family buckets.", True),
    "Kota & Bunny Chow": ("Kasi kotas loaded with chips, polony and russians, plus Durban bunny chows.", False),
    "Wraps, Subs & Tacos": ("Wraps, subs, sandwiches, tacos and burritos made fresh.", False),
    "Grills & Braai": ("Shisa nyama, ribs, chops, boerewors rolls and grilled platters.", False),
    "Sides & Snacks": ("Slap chips, onion rings, nachos, samoosas and other sides.", False),
    "Desserts & Shakes": ("Milkshakes, donuts, ice cream, waffles and sweet treats.", False),
    "Drinks": ("Cold drinks, juices, iced tea, coffee and smoothies.", False),
}

# Legacy 'Restaurant & Fast Food' child slug -> new top-level fast food name.
LEGACY_FAST_FOOD_PARENT_SLUG = "restaurant-fast-food"
LEGACY_FAST_FOOD_MAP = {
    "restaurant-fast-food-burgers": "Burgers",
    "restaurant-fast-food-pizza": "Pizza",
    "restaurant-fast-food-chicken-wings": "Chicken & Wings",
    "restaurant-fast-food-sides-snacks": "Sides & Snacks",
    "restaurant-fast-food-wraps-subs-tacos": "Wraps, Subs & Tacos",
    "restaurant-fast-food-beverages-desserts": "Desserts & Shakes",
}

LEGACY_GROCERY_PARENT_SLUG = "food-groceries"

# Keyword rules used to re-home legacy products. First match wins.
# Values are taxonomy slugs (see category_slug()).
FAST_FOOD_KEYWORDS = [
    (r"kota|bunny", "kota-bunny-chow"),
    (r"burger", "burgers"),
    (r"pizza", "pizza"),
    (r"wrap|sub\b|taco|burrito|sandwich", "wraps-subs-tacos"),
    (r"braai|grill|ribs?\b|chops?\b|wors|shisa", "grills-braai"),
    (r"chicken|wing", "chicken-wings"),
    (r"fries|chips|nacho|onion ring|samoosa", "sides-snacks"),
    (r"shake|donut|doughnut|ice cream|dessert|waffle|cake", "desserts-shakes"),
    (r"drink|\bsoda\b|\bcola\b|juice|coffee|\btea\b|smoothie|water", "drinks"),
]
FAST_FOOD_FALLBACK = "sides-snacks"

GROCERY_KEYWORDS = [
    (r"biltong|dro[eë]wors", "snacks-sweets-biltong-droewors"),
    (r"rooibos|\btea\b|coffee", "beverages-tea-coffee"),
    (r"juice", "beverages-juices"),
    (r"\bwater\b", "beverages-water"),
    (r"\bcola\b|\bsoda\b|soft drink|cordial", "beverages-soft-drinks"),
    (r"cookie|biscuit|rusk|cracker", "bakery-rusks-biscuits"),
    (r"cake|pastr|muffin|koeksister|tart", "bakery-cakes-pastries"),
    (r"bread|\brolls?\b|loaf|sourdough|vetkoek", "bakery-bread-rolls"),
    (r"chip|crisp", "snacks-sweets-chips-crisps"),
    (r"\bjam\b|honey|peanut butter|spread", "breakfast-cereals-spreads-jams-honey"),
    (r"chocolate|\bsweets?\b|candy", "snacks-sweets-chocolates-sweets"),
    (r"\bnuts?\b|cashew|peanuts|raisin|dried", "snacks-sweets-nuts-dried-fruit"),
    (r"milk|maas|amasi", "dairy-eggs-milk-maas"),
    (r"cheese", "dairy-eggs-cheese"),
    (r"yog", "dairy-eggs-yoghurt"),
    (r"butter|margarine", "dairy-eggs-butter-margarine"),
    (r"\beggs?\b", "dairy-eggs-eggs"),
    (r"boerewors|sausage|vienna|russian", "meat-poultry-fish-boerewors-sausages"),
    (r"chicken", "meat-poultry-fish-chicken"),
    (r"beef|steak|mince", "meat-poultry-fish-beef"),
    (r"fish|hake|snoek|prawn|seafood", "meat-poultry-fish-fish-seafood"),
    (r"rice|pasta|noodle|spaghetti|macaroni", "pantry-staples-rice-pasta-noodles"),
    (r"\boil\b", "pantry-staples-cooking-oils"),
    (r"maize|mielie|samp|soya|bean|lentil", "pantry-staples-maize-meal-grains"),
    (r"spice|sauce|chutney|chakalaka|salt|mayo", "pantry-staples-spices-sauces-condiments"),
    (r"flour|sugar|yeast|baking", "pantry-staples-baking-essentials"),
    (r"cereal|flakes|muesli", "breakfast-cereals-cereals"),
    (r"oats|porridge", "breakfast-cereals-oats-porridge"),
    (r"ice cream", "frozen-foods-ice-cream"),
    (r"fruit|apple|banana|orange|mango", "fresh-produce-fruit"),
    (r"veg|potato|tomato|onion|spinach|cabbage", "fresh-produce-vegetables"),
]
# Legacy grocery child slug -> default target when no keyword matches.
LEGACY_GROCERY_DEFAULTS = {
    "food-groceries-fresh-produce": "fresh-produce-vegetables",
    "food-groceries-meat-fish-seafood": "meat-poultry-fish-beef",
    "food-groceries-dairy-bakery-eggs": "dairy-eggs-milk-maas",
    "food-groceries-pantry-staples-grains": "pantry-staples-maize-meal-grains",
    "food-groceries-snacks-sweets-beverages": "snacks-sweets-chocolates-sweets",
    "food-groceries-frozen-canned-foods": "frozen-foods-frozen-meals",
    "food-groceries-traditional-organic-foods": "pantry-staples-maize-meal-grains",
}
GROCERY_FALLBACK = "pantry-staples-maize-meal-grains"


def category_slug(parent_name, child_name=None):
    """Slug used for taxonomy rows: 'parent' or 'parent-child'."""
    if child_name is None:
        return slugify(parent_name)
    return slugify(f"{parent_name}-{child_name}")


def taxonomy_entries():
    """
    Yield dicts describing every taxonomy row, parents before children:
    {slug, name, description, parent_slug, business_category, is_featured, sort_order}
    """
    for p_order, (parent, (desc, featured, children)) in enumerate(
        GROCERY_CATEGORIES.items(), start=1
    ):
        yield {
            "slug": category_slug(parent), "name": parent, "description": desc,
            "parent_slug": None, "business_category": "retail",
            "is_featured": featured, "sort_order": p_order,
        }
        for c_order, (child, c_desc) in enumerate(children.items(), start=1):
            yield {
                "slug": category_slug(parent, child), "name": child,
                "description": c_desc, "parent_slug": category_slug(parent),
                "business_category": "retail", "is_featured": False,
                "sort_order": c_order,
            }
    for order, (name, (desc, featured)) in enumerate(
        FAST_FOOD_CATEGORIES.items(), start=1
    ):
        yield {
            "slug": category_slug(name), "name": name, "description": desc,
            "parent_slug": None, "business_category": "restaurant",
            "is_featured": featured, "sort_order": order,
        }


def taxonomy_slugs():
    return {e["slug"] for e in taxonomy_entries()}


def seed_taxonomy(log=None):
    """
    Create / sync every taxonomy row. Idempotent (keyed by slug).
    Returns (categories_by_slug, created_count, updated_count).
    """
    log = log or (lambda msg: None)
    slugs = taxonomy_slugs()
    by_slug = {}
    created = updated = 0

    for entry in taxonomy_entries():
        parent = by_slug[entry["parent_slug"]] if entry["parent_slug"] else None
        desired = {
            "name": entry["name"],
            "parent": parent,
            "business_category": entry["business_category"],
            "is_featured": entry["is_featured"],
            "sort_order": entry["sort_order"],
            "is_system": True,
            "vendor": None,
            "is_active": True,
        }

        # A legacy system category may already hold this name (system names
        # are unique). Rename it out of the way; --prune deletes it later.
        clash = (
            Category.objects.filter(is_system=True, name=entry["name"])
            .exclude(slug=entry["slug"])
            .first()
        )
        if clash and clash.slug not in slugs:
            clash.name = f"{clash.name} (legacy {clash.pk})"
            clash.save(update_fields=["name"])
            log(f"    ! renamed clashing legacy category -> {clash.name}")

        cat = Category.objects.filter(slug=entry["slug"]).first()
        indent = "    " if parent else "  "
        if cat is None:
            cat = Category.objects.create(
                slug=entry["slug"], description=entry["description"], **desired
            )
            created += 1
            log(f"{indent}+ {cat.name}")
        else:
            desired["description"] = entry["description"]
            dirty = []
            for field, value in desired.items():
                if getattr(cat, field) != value:
                    setattr(cat, field, value)
                    dirty.append(field)
            if dirty:
                cat.save()
                updated += 1
                log(f"{indent}~ {cat.name} (synced {', '.join(dirty)})")
        by_slug[entry["slug"]] = cat

    return by_slug, created, updated


def get_taxonomy_category(slug):
    """Fetch a taxonomy category by slug, seeding the taxonomy if missing."""
    cat = Category.objects.filter(slug=slug).first()
    if cat is None:
        by_slug, _, _ = seed_taxonomy()
        cat = by_slug[slug]
    return cat


def _match(rules, text, default):
    text = text.lower()
    for pattern, slug in rules:
        if re.search(pattern, text):
            return slug
    return default


class Command(BaseCommand):
    help = (
        "Seed the Sanoa groceries + fast food category taxonomy. "
        "Use --prune to migrate legacy data and delete all other system categories."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete ALL existing categories (and their products) before seeding.",
        )
        parser.add_argument(
            "--prune", action="store_true",
            help=(
                "Migrate legacy fast food / grocery products into the new taxonomy, "
                "then delete every system category not in it (products cascade)."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            count = Category.objects.count()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing categories."))

        if options["prune"]:
            self._promote_legacy_fast_food()

        self.stdout.write("Seeding taxonomy...")
        by_slug, created, updated = seed_taxonomy(self.stdout.write)
        self.stdout.write(self.style.SUCCESS(
            f"Taxonomy: {created} created, {updated} synced, "
            f"{len(by_slug)} total ({len(GROCERY_CATEGORIES)} grocery parents, "
            f"{len(FAST_FOOD_CATEGORIES)} fast food)."
        ))

        if options["prune"]:
            self._rehome_legacy_products(by_slug)
            self._prune()

    # -- prune helpers ---------------------------------------------------

    def _promote_legacy_fast_food(self):
        """Turn legacy 'Restaurant & Fast Food' children into top-level rows."""
        promoted = merged = 0
        for old_slug, new_name in LEGACY_FAST_FOOD_MAP.items():
            old = Category.objects.filter(slug=old_slug).first()
            if old is None:
                continue
            new_slug = category_slug(new_name)
            existing = Category.objects.filter(slug=new_slug).first()
            if existing:
                moved = Product.objects.filter(category=old).update(category=existing)
                old.delete()
                merged += 1
                self.stdout.write(f"  merged {old_slug} -> {new_slug} ({moved} products)")
                continue
            old.parent = None
            old.slug = new_slug
            old.name = new_name
            old.business_category = "restaurant"
            old.is_system = True
            old.vendor = None
            old.save()
            promoted += 1
            self.stdout.write(f"  promoted {old_slug} -> {new_slug}")
        self.stdout.write(self.style.SUCCESS(
            f"Fast food migration: {promoted} promoted, {merged} merged."
        ))

    def _rehome_legacy_products(self, by_slug):
        """Move products out of the legacy grocery / fast food trees."""
        moved = 0

        ff_root = Category.objects.filter(slug=LEGACY_FAST_FOOD_PARENT_SLUG).first()
        if ff_root:
            ff_cats = [ff_root, *ff_root.children.all()]
            for product in Product.objects.filter(category__in=ff_cats):
                target = by_slug[_match(FAST_FOOD_KEYWORDS, product.name, FAST_FOOD_FALLBACK)]
                product.category = target
                product.save(update_fields=["category"])
                self._grant(product, target)
                moved += 1
                self.stdout.write(f"  re-homed '{product.name}' -> {target.name}")

        gr_root = Category.objects.filter(slug=LEGACY_GROCERY_PARENT_SLUG).first()
        if gr_root:
            gr_cats = [gr_root, *gr_root.children.all()]
            for product in Product.objects.filter(category__in=gr_cats).select_related("category"):
                default = LEGACY_GROCERY_DEFAULTS.get(product.category.slug, GROCERY_FALLBACK)
                target = by_slug[_match(GROCERY_KEYWORDS, product.name, default)]
                product.category = target
                product.save(update_fields=["category"])
                self._grant(product, target)
                moved += 1
                self.stdout.write(
                    f"  re-homed '{product.name}' -> {target.parent.name} > {target.name}"
                )

        self.stdout.write(self.style.SUCCESS(f"Re-homed {moved} legacy products."))

    @staticmethod
    def _grant(product, category):
        """Make sure the product's vendor has the new category selected."""
        if product.vendor_id:
            VendorCategory.objects.get_or_create(vendor_id=product.vendor_id, category=category)

    def _prune(self):
        keep = taxonomy_slugs()
        stale = Category.objects.filter(vendor__isnull=True).exclude(slug__in=keep)
        stale_ids = list(stale.values_list("id", flat=True))
        # Children of stale rows cascade too — count them for the report.
        all_ids = set(stale_ids)
        frontier = stale_ids
        while frontier:
            frontier = list(
                Category.objects.filter(parent_id__in=frontier)
                .exclude(id__in=all_ids).values_list("id", flat=True)
            )
            all_ids.update(frontier)

        doomed_products = Product.objects.filter(category_id__in=all_ids)
        product_count = doomed_products.count()
        for p in doomed_products.select_related("category"):
            self.stdout.write(f"  - product '{p.name}' ({p.category.name})")

        # Delete roots only; children & products cascade.
        roots = Category.objects.filter(id__in=all_ids).exclude(parent_id__in=all_ids)
        roots.delete()
        self.stdout.write(self.style.WARNING(
            f"Pruned {len(all_ids)} legacy categories and {product_count} products."
        ))
