import io
import json
import uuid

from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.files.base import ContentFile
from django.utils.text import slugify
from PIL import Image
import qrcode

User = get_user_model()


class Category(models.Model):
    """Product category model with hierarchical structure.

    System categories (is_system=True, vendor=None) are pre-loaded by admins
    and available for any vendor to select.
    Custom categories (is_system=False, vendor=<VendorProfile>) are created by
    a specific vendor and belong only to that vendor.
    """

    BUSINESS_CATEGORY_CHOICES = [
        ('retail', 'Groceries'),
        ('restaurant', 'Fast Food'),
        ('both', 'Both'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    business_category = models.CharField(
        max_length=20, choices=BUSINESS_CATEGORY_CHOICES, default='retail',
        help_text=(
            "Which storefront mode this category belongs to. 'retail' shows "
            "in the Groceries experience, 'restaurant' shows in the "
            "Fast Food experience, 'both' shows in either."
        ),
    )

    # Ownership — null means this is a system/admin category
    vendor = models.ForeignKey(
        'business.VendorProfile',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='custom_categories',
    )
    is_system = models.BooleanField(
        default=True,
        help_text="True for admin-managed categories available to all vendors.",
    )

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    # SEO fields
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['sort_order', 'name']
        constraints = [
            # System categories: name unique globally among system categories
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(is_system=True),
                name='unique_system_category_name',
            ),
            # Custom categories: name unique per vendor
            models.UniqueConstraint(
                fields=['name', 'vendor'],
                condition=models.Q(is_system=False),
                name='unique_vendor_category_name',
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            # Vendor custom categories get a vendor-scoped slug to avoid collisions
            if self.vendor_id:
                self.slug = f"{base}-{str(self.vendor_id)[:8]}"
            else:
                self.slug = base
        super().save(*args, **kwargs)

    @property
    def get_full_path(self):
        """Get the full category path"""
        path = []
        category = self
        while category:
            path.append(category.name)
            category = category.parent
        return ' > '.join(reversed(path))


class VendorCategory(models.Model):
    """
    Tracks which categories a vendor has access to — either selected from
    system categories or created as custom categories.
    A vendor can only link products to categories present in this table.
    """
    vendor = models.ForeignKey(
        'business.VendorProfile',
        on_delete=models.CASCADE,
        related_name='vendor_categories',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='vendor_selections',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['vendor', 'category']
        ordering = ['-created_at']
        verbose_name = 'Vendor Category'
        verbose_name_plural = 'Vendor Categories'

    def __str__(self):
        return f"{self.vendor} — {self.category.name}"


class Brand(models.Model):
    """Brand model for products"""
    
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='brands/', null=True, blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Brand'
        verbose_name_plural = 'Brands'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    """Main product model"""
    
    PRODUCT_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('out_of_stock', 'Out of Stock'),
        ('discontinued', 'Discontinued'),
    ]
    
    # Basic info
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=300)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    
    # Relationships
    vendor = models.ForeignKey(
        'business.VendorProfile',
        on_delete=models.CASCADE,
        related_name='products',
        help_text="The vendor profile (store) that owns this product.",
    )
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Original price for showing discounts"
    )
    cost_per_item = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Cost to vendor (for profit calculations)"
    )
    
    # Inventory
    sku = models.CharField(max_length=100, unique=True, blank=True)
    barcode = models.CharField(max_length=100, blank=True)

    # QR Code (auto-generated on creation)
    qr_code = models.ImageField(upload_to='qrcodes/products/', null=True, blank=True)
    qr_code_identifier = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    stock = models.PositiveIntegerField(default=0, help_text="Available stock quantity")
    track_inventory = models.BooleanField(default=True)
    continue_selling_when_out_of_stock = models.BooleanField(default=False)
    
    # Physical properties
    weight = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Weight in grams"
    )
    length = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Length in cm"
    )
    width = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Width in cm"
    )
    height = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Height in cm"
    )
    
    # Status and visibility
    status = models.CharField(max_length=20, choices=PRODUCT_STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    is_eligible_to_negotiate_price = models.BooleanField(
        default=False,
        help_text="Whether the vendor allows buyers to negotiate the price of this product"
    )
    is_digital = models.BooleanField(default=False)
    requires_shipping = models.BooleanField(default=True)
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    # Specifications (key-value product metadata, e.g. {"Material": "Cotton", "Color": "Red"})
    specifications = models.JSONField(
        default=dict, blank=True,
        help_text="Product specifications as key-value pairs"
    )

    # Statistics
    views_count = models.PositiveIntegerField(default=0)
    sales_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['vendor', 'status']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.sku:
            self.sku = f"SKU-{uuid.uuid4().hex[:8].upper()}"
        if not self.barcode:
            self.barcode = f"BAR-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
        # Auto-generate QR code if not already set
        if not self.qr_code:
            self.generate_qr_code()
            super().save(update_fields=['qr_code'])
    
    @property
    def is_on_sale(self):
        return bool(self.compare_at_price and self.compare_at_price > self.price)
    
    @property
    def discount_percentage(self):
        if self.is_on_sale:
            return round(((self.compare_at_price - self.price) / self.compare_at_price) * 100, 2)
        return 0
    
    @property
    def average_rating(self):
        reviews = self.reviews.filter(is_approved=True)
        if reviews:
            return reviews.aggregate(models.Avg('rating'))['rating__avg']
        return 0
    
    @property
    def review_count(self):
        return self.reviews.filter(is_approved=True).count()

    @property
    def likes_count(self):
        return self.likes.count()

    def generate_qr_code(self):
        """Generate a QR code containing product identifier and key details."""
        qr_data = {
            'type': 'product',
            'id': str(self.qr_code_identifier),
            'product_id': str(self.id),
            'name': self.name,
            'sku': self.sku,
            'price': str(self.price),
        }
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        filename = f'product_{self.qr_code_identifier}.png'
        self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)


class ProductImage(models.Model):
    """Product images model"""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['sort_order']
    
    def __str__(self):
        return f"{self.product.name} - Image {self.id}"
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            # Ensure only one primary image per product
            ProductImage.objects.filter(product=self.product, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)
        
        # Resize image
        if self.image:
            img = Image.open(self.image.path)
            if img.height > 800 or img.width > 800:
                output_size = (800, 800)
                img.thumbnail(output_size)
                img.save(self.image.path)


class ProductVariant(models.Model):
    """Product variants (size, color, etc.)"""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=200)  # e.g., "Red - Large"
    sku = models.CharField(max_length=100, unique=True, blank=True)
    
    # Pricing (can override parent product)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Physical properties (can override parent product)
    weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Inventory specific to variant
    inventory_quantity = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        unique_together = ['product', 'name']
    
    def __str__(self):
        return f"{self.product.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = f"{self.product.sku}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
    
    @property
    def effective_price(self):
        return self.price if self.price else self.product.price



class ProductAddonGroup(models.Model):
    """
    A named group of options/add-ons for a product.

    Examples:
    - "Choose your sauce" (required, single-select, min=1, max=1)
    - "Extra toppings" (optional, multi-select, min=0, max=5)
    - "Choose 2 sides" (required, multi-select, min=2, max=2)
    - "Size" (required, single-select) — for fashion/electronics
    - "Color" (required, single-select)
    - "Warranty" (optional, single-select, min=0, max=1)

    Works for any product type: food, fashion, electronics, etc.
    Normal products simply have zero groups.
    """

    GROUP_TYPE_CHOICES = [
        ('single', 'Single Select'),
        ('multiple', 'Multiple Select'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='addon_groups',
    )
    name = models.CharField(max_length=200, help_text="e.g. 'Choose your sauce', 'Size', 'Color'")
    group_type = models.CharField(
        max_length=10, choices=GROUP_TYPE_CHOICES, default='single',
        help_text="'single' = radio buttons, 'multiple' = checkboxes",
    )
    is_required = models.BooleanField(
        default=False,
        help_text='Customer must make a selection from this group before adding to cart.',
    )
    min_selection = models.PositiveIntegerField(
        default=0,
        help_text='Minimum number of options the customer must select (0 = optional).',
    )
    max_selection = models.PositiveIntegerField(
        default=1,
        help_text='Maximum number of options the customer can select.',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Add-on Group'
        verbose_name_plural = 'Product Add-on Groups'
        ordering = ['product', 'sort_order', 'name']

    def __str__(self):
        req = 'required' if self.is_required else 'optional'
        return f'{self.product.name} — {self.name} ({req}, {self.group_type})'


class ProductAddon(models.Model):
    """
    A single option within an add-on group.

    Examples:
    - Group "Choose your sauce" → addons: "BBQ", "Mayo", "Hot Sauce"
    - Group "Extra toppings" → addons: "Extra cheese +R5", "Bacon +R8"
    - Group "Size" → addons: "S", "M", "L", "XL"
    - Group "Storage" → addons: "64GB", "128GB +R500", "256GB +R1000"
    - Group "Warranty" → addons: "1 Year", "2 Year +R200"
    """

    group = models.ForeignKey(
        ProductAddonGroup, on_delete=models.CASCADE, related_name='addons',
    )
    name = models.CharField(max_length=200, help_text="e.g. 'Extra cheese', 'Large', 'Red'")
    price_delta = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Price adjustment. +5.00 adds R5, -2.00 subtracts R2, 0 = no change.',
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Pre-selected when the product page loads.',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Add-on'
        verbose_name_plural = 'Product Add-ons'
        ordering = ['group', 'sort_order', 'name']

    def __str__(self):
        sign = '+' if self.price_delta >= 0 else ''
        return f'{self.group.name} — {self.name} ({sign}{self.price_delta})'


class ProductReview(models.Model):
    """Product reviews and ratings"""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)
    
    # Moderation
    is_approved = models.BooleanField(default=True)
    is_verified_purchase = models.BooleanField(default=False)
    
    # Helpful votes
    helpful_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Product Review'
        verbose_name_plural = 'Product Reviews'
        unique_together = ['product', 'user']  # One review per user per product
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.product.name} - {self.rating} stars by {self.user.email}"


class Wishlist(models.Model):
    """User wishlist for products"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlists')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Wishlist'
        verbose_name_plural = 'Wishlists'
        unique_together = ['user', 'product']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.product.name}"


class ProductLike(models.Model):
    """
    Product likes — a public social signal showing interest in a product.
    Different from Wishlist (private/personal save-for-later).
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='product_likes'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='likes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Product Like'
        verbose_name_plural = 'Product Likes'
        unique_together = ['user', 'product']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} likes {self.product.name}"


class Banner(models.Model):
    """Promotional banners linked to categories."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=300)
    subtitle = models.CharField(max_length=500, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='banners',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return self.title


class BannerImage(models.Model):
    """Images for banners — each banner can have multiple images."""

    banner = models.ForeignKey(Banner, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='banners/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Banner Image'
        verbose_name_plural = 'Banner Images'
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.banner.title} - Image {self.id}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            BannerImage.objects.filter(banner=self.banner, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)


class VendorReview(models.Model):
    """
    Vendor/store reviews and ratings from customers.
    Separate from ProductReview — this rates the vendor's overall service,
    delivery, communication, and professionalism.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='vendor_reviews',
        limit_choices_to={'user_type': 'customer'},
    )
    vendor = models.ForeignKey(
        'business.VendorProfile', on_delete=models.CASCADE,
        related_name='reviews',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField(blank=True)

    # Moderation
    is_approved = models.BooleanField(default=True)
    is_verified_purchase = models.BooleanField(
        default=False,
        help_text="Auto-set if user has completed an order from this vendor"
    )

    # Helpful votes
    helpful_count = models.PositiveIntegerField(default=0)

    # Vendor's public reply to this review
    vendor_reply = models.TextField(blank=True)
    vendor_replied_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vendor Review'
        verbose_name_plural = 'Vendor Reviews'
        unique_together = ['user', 'vendor']
        ordering = ['-created_at']

    def __str__(self):
        vendor_label = self.vendor.trading_name or self.vendor.name or f"vendor {self.vendor_id}"
        return f"{vendor_label} - {self.rating} stars by {self.user.email}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._update_vendor_stats()

    def delete(self, *args, **kwargs):
        vendor = self.vendor
        super().delete(*args, **kwargs)
        self._update_vendor_stats(vendor=vendor)

    def _update_vendor_stats(self, vendor=None):
        """Recalculate average_rating + total_reviews and propagate it to
        EVERY profile model for this vendor — the unified VendorProfile AND
        the legacy Individual/Business profiles that power
        /api/business/discover-stores/ and the storefront listings — so the
        rating is identical everywhere it's shown.
        """
        from django.db.models import Avg
        vendor_profile = vendor or self.vendor
        approved = VendorReview.objects.filter(vendor=vendor_profile, is_approved=True)
        count = approved.count()
        avg = round(approved.aggregate(avg=Avg('rating'))['avg'] or 0, 2)

        from business.models import (
            VendorProfile, IndividualVendorProfile, BusinessVendorProfile,
        )
        # Unified profile (the review target).
        VendorProfile.objects.filter(pk=vendor_profile.pk).update(
            average_rating=avg, total_reviews=count,
        )
        # Legacy individual/business profiles share the same user — keep
        # their rating fields in lock-step so discover/listings match.
        user_id = vendor_profile.user_id
        if user_id is not None:
            IndividualVendorProfile.objects.filter(user_id=user_id).update(
                average_rating=avg, total_reviews=count,
            )
            BusinessVendorProfile.objects.filter(user_id=user_id).update(
                average_rating=avg, total_reviews=count,
            )
