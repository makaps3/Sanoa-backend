from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from business.admin_helpers import (
    VendorBusinessFilter as _BaseVendorBusinessFilter,
    vendor_profile_formfield,
    vendor_profile_label as _vendor_profile_label,
)
from .models import (
    Category, Brand, Product, ProductImage, ProductVariant,
    ProductAddonGroup, ProductAddon,
    ProductReview, Wishlist, ProductLike, VendorReview, Banner, BannerImage,
)


class ProductVendorFilter(_BaseVendorBusinessFilter):
    """Only show vendor profiles that actually have products."""
    products_relation = 'products'


class VendorReviewVendorFilter(_BaseVendorBusinessFilter):
    products_relation = 'reviews'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'is_featured', 'sort_order', 'created_at']
    list_filter = ['is_active', 'is_featured', 'parent', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('Basic Info', {
            'fields': ['name', 'slug', 'description', 'parent', 'image']
        }),
        ('Settings', {
            'fields': ['is_active', 'is_featured', 'sort_order']
        }),
        ('SEO', {
            'fields': ['meta_title', 'meta_description'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'website', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('Basic Info', {
            'fields': ['name', 'slug', 'description', 'logo', 'website']
        }),
        ('Settings', {
            'fields': ['is_active']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'sort_order']


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ['name', 'sku', 'price', 'inventory_quantity', 'is_active']
    readonly_fields = ['sku']



@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'vendor_display', 'category', 'brand', 'price', 'status',
        'is_featured', 'is_eligible_to_negotiate_price',
        'views_count', 'sales_count', 'created_at'
    ]
    list_filter = [
        'status', 'is_featured', 'is_eligible_to_negotiate_price',
        'is_digital', 'category', 'brand', ProductVendorFilter, 'created_at'
    ]
    search_fields = [
        'name', 'sku', 'description',
        'vendor__name', 'vendor__trading_name',
        'vendor__user__email',
    ]

    @admin.display(description='Vendor', ordering='vendor__name')
    def vendor_display(self, obj):
        return _vendor_profile_label(obj.vendor)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'vendor':
            return vendor_profile_formfield(formfield)
        return formfield
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = [
        'id', 'sku', 'qr_code', 'qr_code_identifier',
        'views_count', 'sales_count', 'average_rating',
        'review_count', 'created_at', 'updated_at'
    ]

    fieldsets = [
        ('Basic Info', {
            'fields': [
                'id', 'name', 'slug', 'description', 'short_description',
                'vendor', 'category', 'brand'
            ]
        }),
        ('Pricing', {
            'fields': ['price', 'compare_at_price', 'cost_per_item']
        }),
        ('Inventory', {
            'fields': [
                'sku', 'barcode', 'stock', 'track_inventory',
                'continue_selling_when_out_of_stock'
            ]
        }),
        ('QR Code', {
            'fields': ['qr_code', 'qr_code_identifier']
        }),
        ('Physical Properties', {
            'fields': ['weight', 'length', 'width', 'height'],
            'classes': ['collapse']
        }),
        ('Status & Visibility', {
            'fields': [
                'status', 'is_featured', 'is_eligible_to_negotiate_price',
                'is_digital', 'requires_shipping'
            ]
        }),
        ('Specifications', {
            'fields': ['specifications'],
            'classes': ['collapse']
        }),
        ('SEO', {
            'fields': ['meta_title', 'meta_description'],
            'classes': ['collapse']
        }),
        ('Statistics', {
            'fields': [
                'views_count', 'sales_count', 'average_rating', 'review_count'
            ],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    inlines = [ProductImageInline, ProductVariantInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'vendor', 'vendor__user', 'category', 'brand',
        )


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'is_primary', 'sort_order', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['product__name', 'alt_text']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'name', 'sku', 'effective_price', 
        'inventory_quantity', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['product__name', 'name', 'sku']
    readonly_fields = ['sku', 'created_at', 'updated_at']
    
    fieldsets = [
        ('Basic Info', {
            'fields': ['product', 'name', 'sku']
        }),
        ('Pricing', {
            'fields': ['price', 'compare_at_price']
        }),
        ('Physical Properties', {
            'fields': ['weight']
        }),
        ('Inventory', {
            'fields': ['inventory_quantity']
        }),
        ('Status', {
            'fields': ['is_active']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')


class ProductAddonInline(admin.TabularInline):
    model = ProductAddon
    extra = 1
    fields = ['name', 'price_delta', 'is_default', 'is_active', 'sort_order']


@admin.register(ProductAddonGroup)
class ProductAddonGroupAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'name', 'group_type', 'is_required',
        'min_selection', 'max_selection', 'addon_count', 'is_active',
    ]
    list_filter = ['group_type', 'is_required', 'is_active']
    search_fields = ['name', 'product__name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ProductAddonInline]

    fieldsets = [
        ('Group Info', {'fields': ['product', 'name', 'group_type']}),
        ('Selection Rules', {'fields': ['is_required', 'min_selection', 'max_selection']}),
        ('Settings', {'fields': ['is_active', 'sort_order']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    def addon_count(self, obj):
        return obj.addons.count()
    addon_count.short_description = 'Options'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product').prefetch_related('addons')


@admin.register(ProductAddon)
class ProductAddonAdmin(admin.ModelAdmin):
    list_display = [
        'group', 'name', 'price_delta', 'is_default', 'is_active', 'sort_order',
    ]
    list_filter = ['is_active', 'is_default']
    search_fields = ['name', 'group__name', 'group__product__name']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('group', 'group__product')


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'user', 'rating', 'is_approved', 
        'is_verified_purchase', 'helpful_count', 'created_at'
    ]
    list_filter = [
        'rating', 'is_approved', 'is_verified_purchase', 'created_at'
    ]
    search_fields = ['product__name', 'user__email', 'title', 'comment']
    readonly_fields = ['helpful_count', 'created_at', 'updated_at']
    
    fieldsets = [
        ('Review Info', {
            'fields': ['product', 'user', 'rating', 'title', 'comment']
        }),
        ('Status', {
            'fields': ['is_approved', 'is_verified_purchase', 'helpful_count']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'user')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'product__name']
    readonly_fields = ['created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')


@admin.register(ProductLike)
class ProductLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'product__name']
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')


@admin.register(VendorReview)
class VendorReviewAdmin(admin.ModelAdmin):
    list_display = [
        'vendor_display', 'user', 'rating', 'is_approved',
        'is_verified_purchase', 'helpful_count', 'created_at',
    ]
    list_filter = [VendorReviewVendorFilter, 'rating', 'is_approved', 'is_verified_purchase', 'created_at']
    search_fields = [
        'vendor__name', 'vendor__trading_name',
        'user__email', 'title', 'comment',
    ]
    readonly_fields = ['helpful_count', 'vendor_replied_at', 'created_at', 'updated_at']

    fieldsets = [
        ('Review Info', {
            'fields': ['vendor', 'user', 'rating', 'title', 'comment'],
        }),
        ('Vendor Reply', {
            'fields': ['vendor_reply', 'vendor_replied_at'],
        }),
        ('Status', {
            'fields': ['is_approved', 'is_verified_purchase', 'helpful_count'],
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    @admin.display(description='Vendor', ordering='vendor__name')
    def vendor_display(self, obj):
        return _vendor_profile_label(obj.vendor)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'vendor':
            from business.admin_helpers import vendor_profile_formfield
            return vendor_profile_formfield(formfield)
        return formfield

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'vendor', 'vendor__user')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('vendor', 'user')


class BannerImageInline(admin.TabularInline):
    model = BannerImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'sort_order']


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'category',
        'is_active', 'sort_order', 'start_date', 'end_date', 'created_at',
    ]
    list_filter = ['is_active', 'start_date', 'end_date', 'created_at']
    search_fields = ['title', 'subtitle', 'category__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [BannerImageInline]

    fieldsets = [
        ('Basic Info', {
            'fields': ['id', 'title', 'subtitle'],
        }),
        ('Category', {
            'fields': ['category'],
        }),
        ('Settings', {
            'fields': ['is_active', 'sort_order', 'start_date', 'end_date'],
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')
