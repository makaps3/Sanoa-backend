"""
Generate and assign placeholder product images using Pillow.
Creates colourful branded placeholders for every product that lacks images.
"""
import io
import textwrap

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from PIL import Image, ImageDraw, ImageFont

from products.models import Product, ProductImage

# Colour palette keyed by root category slug (see seed_categories taxonomy)
CATEGORY_COLOURS = {
    # Groceries
    'fresh-produce': ('#27AE60', '#E8F8F5'),
    'meat-poultry-fish': ('#C0392B', '#FDEDEC'),
    'dairy-eggs': ('#2980B9', '#D6EAF8'),
    'bakery': ('#CA6F1E', '#FDEBD0'),
    'pantry-staples': ('#D35400', '#FBEEE6'),
    'breakfast-cereals': ('#F39C12', '#FEF9E7'),
    'snacks-sweets': ('#8E44AD', '#F4ECF7'),
    'beverages': ('#16A085', '#E8F6F3'),
    'frozen-foods': ('#5DADE2', '#EBF5FB'),
    # Fast food
    'burgers': ('#E67E22', '#FDEBD0'),
    'pizza': ('#E74C3C', '#FDEDEC'),
    'chicken-wings': ('#F1C40F', '#FEF9E7'),
    'kota-bunny-chow': ('#A04000', '#F6DDCC'),
    'wraps-subs-tacos': ('#229954', '#EAFAF1'),
    'grills-braai': ('#7B241C', '#F2D7D5'),
    'sides-snacks': ('#D4AC0D', '#FCF3CF'),
    'desserts-shakes': ('#E91E63', '#FCE4EC'),
    'drinks': ('#3498DB', '#D4E6F1'),
}


def get_colours_for_product(product):
    """Pick a colour pair based on the product's root category."""
    cat = product.category
    root = cat.parent if cat.parent else cat
    slug = root.slug.lower()
    for prefix, colours in CATEGORY_COLOURS.items():
        if prefix in slug:
            return colours
    return ('#34495E', '#ECF0F1')


def generate_placeholder(product, size=(800, 800)):
    """Create a placeholder image with product name and category."""
    bg_colour, text_bg = get_colours_for_product(product)
    img = Image.new('RGB', size, bg_colour)
    draw = ImageDraw.Draw(img)

    # Try to get a reasonable font; fall back to default
    try:
        font_large = ImageFont.truetype("arial.ttf", 36)
        font_small = ImageFont.truetype("arial.ttf", 22)
    except (OSError, IOError):
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        except (OSError, IOError):
            font_large = ImageFont.load_default()
            font_small = font_large

    # Draw a centred rounded-ish rectangle as text background
    margin = 60
    rect = [margin, size[1] // 2 - 100, size[0] - margin, size[1] // 2 + 100]
    draw.rounded_rectangle(rect, radius=20, fill=text_bg)

    # Wrap product name
    wrapper = textwrap.TextWrapper(width=22)
    lines = wrapper.wrap(product.name)
    name_text = '\n'.join(lines[:3])

    # Category label
    cat_label = product.category.name

    # Draw product name
    bbox = draw.multiline_textbbox((0, 0), name_text, font=font_large)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size[0] - tw) // 2
    y = size[1] // 2 - th // 2 - 15
    draw.multiline_text((x, y), name_text, fill='#2C3E50', font=font_large, align='center')

    # Draw category below
    bbox2 = draw.textbbox((0, 0), cat_label, font=font_small)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((size[0] - tw2) // 2, rect[3] + 15), cat_label, fill='white', font=font_small)

    # Small "SANOA" watermark at bottom
    try:
        font_wm = ImageFont.truetype("arial.ttf", 16)
    except (OSError, IOError):
        font_wm = font_small
    draw.text((size[0] // 2 - 25, size[1] - 40), 'SANOA', fill='#FFFFFF80', font=font_wm)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Generate and assign placeholder images to all products without images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing product images before generating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            count = ProductImage.objects.count()
            ProductImage.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {count} existing product images.'))

        products = Product.objects.select_related('category', 'category__parent').all()

        if not products.exists():
            self.stdout.write(self.style.WARNING('No products found.'))
            return

        created = 0
        skipped = 0

        for product in products:
            if product.images.exists():
                self.stdout.write(f'  {product.name} already has images, skipping')
                skipped += 1
                continue

            self.stdout.write(f'  Generating image for: {product.name}...')

            image_data = generate_placeholder(product)
            filename = f'{slugify(product.name)}_1.jpg'

            product_image = ProductImage(
                product=product,
                alt_text=f'{product.name} - product image',
                is_primary=True,
                sort_order=0,
            )
            product_image.image.save(filename, ContentFile(image_data), save=True)
            created += 1

            self.stdout.write(self.style.SUCCESS(f'    + {filename}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Generated {created} images. Skipped {skipped}.'
        ))
