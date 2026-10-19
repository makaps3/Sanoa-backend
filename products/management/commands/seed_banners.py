"""
Generate sample grocery + fast food banners with images downloaded from Unsplash.
Each banner gets 2-3 images via the BannerImage model and is linked to a
top-level category from seed_categories (looked up by slug).
"""
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from products.models import Banner, BannerImage, Category


BANNER_DATA = [
    {
        'title': 'Fresh Produce Deals',
        'subtitle': 'Farm-fresh fruit and veg delivered to your door',
        'category_slug': 'fresh-produce',
        'images': [
            {'url': 'https://images.unsplash.com/photo-1542838132-92c53300491e?w=1200&h=400&fit=crop', 'alt': 'Fresh produce shelves', 'primary': True},
            {'url': 'https://images.unsplash.com/photo-1610832958506-aa56368176cf?w=1200&h=400&fit=crop', 'alt': 'Fresh fruit flatlay'},
            {'url': 'https://images.unsplash.com/photo-1488459716781-31db52582fe9?w=1200&h=400&fit=crop', 'alt': 'Vegetable market stall'},
        ],
    },
    {
        'title': 'Fresh From the Bakery',
        'subtitle': 'Loaves and rolls baked before sunrise',
        'category_slug': 'bakery',
        'images': [
            {'url': 'https://images.unsplash.com/photo-1509440159596-0249088772ff?w=1200&h=400&fit=crop', 'alt': 'Rustic bread loaves', 'primary': True},
            {'url': 'https://images.unsplash.com/photo-1608198093002-ad4e005484ec?w=1200&h=400&fit=crop', 'alt': 'Assorted bakery breads and rolls'},
        ],
    },
    {
        'title': 'Dairy & Eggs Daily',
        'subtitle': 'Fresh milk, amasi and free-range eggs',
        'category_slug': 'dairy-eggs',
        'images': [
            {'url': 'https://images.unsplash.com/photo-1550583724-b2692b85b150?w=1200&h=400&fit=crop', 'alt': 'Milk poured into a glass', 'primary': True},
            {'url': 'https://images.unsplash.com/photo-1576186726115-4d51596775d1?w=1200&h=400&fit=crop', 'alt': 'Glass milk bottle'},
            {'url': 'https://images.unsplash.com/photo-1606787366850-de6330128bfc?w=1200&h=400&fit=crop', 'alt': 'Eggs and fresh groceries'},
        ],
    },
    {
        'title': 'Stock Up the Pantry',
        'subtitle': 'Rice, oil, tins and everyday staples at spaza prices',
        'category_slug': 'pantry-staples',
        'images': [
            {'url': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=1200&h=400&fit=crop', 'alt': 'Raw rice grains', 'primary': True},
            {'url': 'https://images.unsplash.com/photo-1534483509719-3feaee7c30da?w=1200&h=400&fit=crop', 'alt': 'Tinned soups'},
            {'url': 'https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=1200&h=400&fit=crop', 'alt': 'Cooking oil bottle'},
        ],
    },
    {
        'title': 'Snack Attack',
        'subtitle': 'Chips, chocolates and treats for padkos and movie night',
        'category_slug': 'snacks-sweets',
        'images': [
            {'url': 'https://images.unsplash.com/photo-1599490659213-e2b9527bd087?w=1200&h=400&fit=crop', 'alt': 'Potato crisps', 'primary': True},
            {'url': 'https://images.unsplash.com/photo-1621939514649-280e2ee25f60?w=1200&h=400&fit=crop', 'alt': 'Chocolate bars'},
        ],
    },
    {
        'title': 'Burger Cravings',
        'subtitle': 'Flame-grilled burgers from local favourites',
        'category_slug': 'burgers',
        'images': [
            {'url': 'https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=1200&h=400&fit=crop', 'alt': 'Classic cheeseburger', 'primary': True},
            {'url': 'https://images.unsplash.com/photo-1572802419224-296b0aeee0d9?w=1200&h=400&fit=crop', 'alt': 'Double bacon burger'},
        ],
    },
    {
        'title': 'Pizza Night',
        'subtitle': 'Wood-fired pizzas delivered hot',
        'category_slug': 'pizza',
        'images': [
            {'url': 'https://images.unsplash.com/photo-1604382354936-07c5d9983bd3?w=1200&h=400&fit=crop', 'alt': 'Margherita pizza', 'primary': True},
            {'url': 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=1200&h=400&fit=crop', 'alt': 'Pepperoni pizza'},
        ],
    },
    {
        'title': 'Crispy Chicken & Wings',
        'subtitle': 'Buckets, wings and tenders for the whole family',
        'category_slug': 'chicken-wings',
        'images': [
            {'url': 'https://images.unsplash.com/photo-1626082927389-6cd097cdc6ec?w=1200&h=400&fit=crop', 'alt': 'Fried chicken bucket', 'primary': True},
            {'url': 'https://images.unsplash.com/photo-1608039829572-78524f79c4c7?w=1200&h=400&fit=crop', 'alt': 'Buffalo wings'},
        ],
    },
]


def download_image(url):
    """Download image from URL and return bytes."""
    req = urllib.request.Request(url, headers={'User-Agent': 'SanoaBannerSeeder/1.0'})
    response = urllib.request.urlopen(req, timeout=30)
    return response.read()


class Command(BaseCommand):
    help = 'Create sample grocery and fast food banners with Unsplash images linked to taxonomy categories'

    def handle(self, *args, **options):
        created_count = 0

        for i, data in enumerate(BANNER_DATA):
            category = Category.objects.filter(slug=data['category_slug'], is_active=True).first()
            if not category:
                self.stderr.write(self.style.WARNING(
                    f"  Category not found: {data['category_slug']} (run seed_categories) — skipping"
                ))
                continue

            if Banner.objects.filter(title=data['title']).exists():
                self.stdout.write(f"  Banner already exists: {data['title']} — skipping")
                continue

            banner = Banner.objects.create(
                title=data['title'],
                subtitle=data['subtitle'],
                category=category,
                is_active=True,
                sort_order=i,
            )

            for j, img_data in enumerate(data['images']):
                try:
                    self.stdout.write(f"  Downloading image {j + 1}/{len(data['images'])} for: {data['title']}...")
                    image_bytes = download_image(img_data['url'])
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"    Failed: {e}"))
                    continue

                slug = data['category_slug'][:30].replace('-', '_')
                filename = f"banner_{slug}_{j + 1}.jpg"
                banner_image = BannerImage(
                    banner=banner,
                    alt_text=img_data.get('alt', ''),
                    is_primary=img_data.get('primary', False),
                    sort_order=j,
                )
                banner_image.image.save(filename, ContentFile(image_bytes), save=False)
                banner_image.save()

            img_count = banner.images.count()
            self.stdout.write(self.style.SUCCESS(
                f"  Created banner: \"{data['title']}\" -> {category.name} ({img_count} images)"
            ))
            created_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nDone! Created {created_count} banners.'))
