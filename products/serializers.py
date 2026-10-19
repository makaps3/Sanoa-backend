"""
Serializers for products app
"""
from rest_framework import serializers
from .models import (
    Category, Brand, Product, ProductImage, ProductVariant,
    ProductAddonGroup, ProductAddon,
    ProductReview, Wishlist, ProductLike, VendorReview, Banner, BannerImage,
    VendorCategory,
)
from core.utils import generate_slug


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""

    full_path = serializers.CharField(source='get_full_path', read_only=True)
    children_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent',
            'image', 'business_category', 'is_system',
            'is_active', 'is_featured', 'sort_order', 'meta_title',
            'meta_description', 'full_path', 'children_count',
            'products_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'slug', 'is_system']

    def get_children_count(self, obj):
        return obj.children.count()

    def get_products_count(self, obj):
        return obj.products.count()


class VendorCategoryCreateSerializer(serializers.ModelSerializer):
    """Used when a vendor creates a brand-new custom category."""

    class Meta:
        model = Category
        fields = [
            'name', 'description', 'parent', 'image',
            'business_category', 'meta_title', 'meta_description',
        ]

    def validate_parent(self, parent):
        if parent and not parent.is_system:
            raise serializers.ValidationError(
                "Custom categories can only be nested under system categories."
            )
        return parent


class VendorCategorySerializer(serializers.ModelSerializer):
    """Represents a vendor's category selection (system or custom)."""

    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True, is_system=True),
        source='category',
        write_only=True,
    )

    class Meta:
        model = VendorCategory
        fields = ['id', 'category', 'category_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class FeaturedCategorySerializer(serializers.ModelSerializer):
    """Serializer for featured categories with nested children."""

    children = CategorySerializer(many=True, read_only=True)
    children_count = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description',
            'image', 'business_category',
            'is_active', 'is_featured', 'sort_order',
            'children_count', 'products_count', 'children',
        ]
        read_only_fields = ['id', 'slug']

    def get_children_count(self, obj):
        return obj.children.count()

    def get_products_count(self, obj):
        return obj.products.count()


class BrandSerializer(serializers.ModelSerializer):
    """Serializer for Brand model"""
    
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Brand
        fields = [
            'id', 'name', 'slug', 'description', 'logo',
            'website', 'is_active', 'products_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'slug']
    
    def get_products_count(self, obj):
        return obj.products.count()


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for ProductImage model"""
    
    class Meta:
        model = ProductImage
        fields = [
            'id', 'image', 'alt_text', 'is_primary', 'sort_order', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ProductVariantSerializer(serializers.ModelSerializer):
    """Serializer for ProductVariant model"""

    effective_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'name', 'sku', 'price', 'compare_at_price',
            'weight', 'inventory_quantity', 'is_active',
            'effective_price', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'sku', 'created_at', 'updated_at']


class ProductAddonSerializer(serializers.ModelSerializer):
    """Serializer for a single add-on option within a group."""

    class Meta:
        model = ProductAddon
        fields = [
            'id', 'group', 'name', 'price_delta',
            'is_default', 'is_active', 'sort_order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductAddonGroupSerializer(serializers.ModelSerializer):
    """
    Serializer for add-on groups with nested addons.
    Used in the product detail response.
    """
    addons = ProductAddonSerializer(many=True, read_only=True)

    class Meta:
        model = ProductAddonGroup
        fields = [
            'id', 'product', 'name', 'group_type',
            'is_required', 'min_selection', 'max_selection',
            'is_active', 'sort_order', 'addons',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductAddonGroupWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating add-on groups (without nested addons)."""

    class Meta:
        model = ProductAddonGroup
        fields = [
            'id', 'product', 'name', 'group_type',
            'is_required', 'min_selection', 'max_selection',
            'is_active', 'sort_order',
        ]
        read_only_fields = ['id']



class ProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for ProductReview model"""

    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    # Flutter parser reads `customer_name` / `customer_avatar` — mirror
    # `user_name` so a single client model can render both shapes.
    customer_name = serializers.SerializerMethodField()
    customer_avatar = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ProductReview
        fields = [
            'id', 'product', 'product_name',
            'user_email', 'user_name',
            'customer_name', 'customer_avatar',
            'rating',
            'title', 'comment', 'is_approved', 'is_verified_purchase',
            'helpful_count', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'product_name',
            'is_approved', 'is_verified_purchase', 'helpful_count',
            'created_at', 'updated_at'
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

    def get_customer_name(self, obj):
        return self.get_user_name(obj)

    def get_customer_avatar(self, obj):
        request = self.context.get('request')
        avatar = getattr(obj.user, 'avatar', None)
        if not avatar:
            return None
        try:
            url = avatar.url
        except (ValueError, AttributeError):
            return None
        return request.build_absolute_uri(url) if request else url


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer for Product list view"""

    category_name = serializers.CharField(source='category.name', read_only=True)
    business_category = serializers.CharField(source='category.business_category', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    primary_image = serializers.SerializerMethodField()
    discount_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    average_rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, read_only=True
    )
    # Short alias clients can rely on regardless of the canonical field name.
    is_negotiable = serializers.BooleanField(
        source='is_eligible_to_negotiate_price', read_only=True,
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'short_description', 'category_name',
            'business_category', 'brand_name',
            'price', 'compare_at_price', 'discount_percentage',
            'is_featured', 'is_eligible_to_negotiate_price', 'is_negotiable',
            'primary_image', 'average_rating',
            'review_count', 'likes_count', 'sales_count', 'stock', 'status',
            'qr_code',
        ]
        read_only_fields = fields
    
    def get_primary_image(self, obj):
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        if image:
            return ProductImageSerializer(image, context=self.context).data
        return None


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Product model"""

    category_name = serializers.CharField(source='category.name', read_only=True)
    business_category = serializers.CharField(source='category.business_category', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)
    vendor_info = serializers.SerializerMethodField()
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    addon_groups = ProductAddonGroupSerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    discount_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )
    average_rating = serializers.DecimalField(
        max_digits=3, decimal_places=2, read_only=True
    )
    is_negotiable = serializers.BooleanField(
        source='is_eligible_to_negotiate_price', read_only=True,
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'short_description',
            'category', 'category_name', 'business_category', 'brand', 'brand_name',
            'vendor', 'vendor_info', 'price', 'compare_at_price',
            'cost_per_item', 'discount_percentage', 'sku', 'barcode',
            'qr_code', 'qr_code_identifier',
            'stock', 'track_inventory', 'continue_selling_when_out_of_stock',
            'weight', 'length', 'width', 'height', 'status',
            'is_featured', 'is_eligible_to_negotiate_price', 'is_negotiable',
            'is_digital', 'requires_shipping',
            'meta_title', 'meta_description', 'average_rating',
            'review_count', 'likes_count', 'views_count', 'sales_count',
            'images', 'variants', 'addon_groups', 'specifications', 'reviews',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'sku', 'qr_code', 'qr_code_identifier',
            'average_rating', 'review_count',
            'views_count', 'sales_count', 'created_at', 'updated_at'
        ]

    def get_vendor_info(self, obj):
        from business.utils import build_vendor_info
        # Product.vendor is now a VendorProfile; build_vendor_info expects
        # the underlying User so it can resolve the same profile chain.
        return build_vendor_info(obj.vendor.user, self.context.get('request'))


class _NestedAddonWriteSerializer(serializers.Serializer):
    """Inline add-on entry used when creating a product with nested groups."""

    name = serializers.CharField(max_length=200)
    price_delta = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    is_default = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)
    sort_order = serializers.IntegerField(required=False, default=0)


class _NestedAddonGroupWriteSerializer(serializers.Serializer):
    """Inline add-on group used when creating a product (restaurant-style)."""

    name = serializers.CharField(max_length=200)
    group_type = serializers.ChoiceField(
        choices=ProductAddonGroup.GROUP_TYPE_CHOICES, required=False, default='single',
    )
    is_required = serializers.BooleanField(required=False, default=False)
    min_selection = serializers.IntegerField(required=False, default=0, min_value=0)
    max_selection = serializers.IntegerField(required=False, default=1, min_value=1)
    is_active = serializers.BooleanField(required=False, default=True)
    sort_order = serializers.IntegerField(required=False, default=0)
    addons = _NestedAddonWriteSerializer(many=True, required=False, default=list)


class _NestedVariantWriteSerializer(serializers.Serializer):
    """Inline variant used when creating a product."""

    name = serializers.CharField(max_length=200)
    sku = serializers.CharField(max_length=100, required=False, allow_blank=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    compare_at_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
    )
    weight = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True,
    )
    inventory_quantity = serializers.IntegerField(required=False, default=0, min_value=0)
    is_active = serializers.BooleanField(required=False, default=True)


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Create / update a product, optionally with nested variants and add-on groups
    in one atomic request.

    Accepts a few client-side aliases so older payloads keep working:
      * ``stock_quantity`` → ``stock``
      * ``allow_backorder`` → ``continue_selling_when_out_of_stock``
      * ``is_negotiable``   → ``is_eligible_to_negotiate_price`` (short alias)

    Idempotency:
      * Variants are de-duplicated by ``name`` within the request.
      * Add-on groups are de-duplicated by ``name`` per product.
      * Add-ons are de-duplicated by ``name`` per group.
    """

    # ── Nested write fields ──────────────────────────────────────────
    variants = _NestedVariantWriteSerializer(many=True, required=False, write_only=True)
    addon_groups = _NestedAddonGroupWriteSerializer(many=True, required=False, write_only=True)

    # ── Backwards-compatible aliases ─────────────────────────────────
    stock_quantity = serializers.IntegerField(
        required=False, write_only=True, min_value=0,
        help_text='Alias for `stock`. Legacy clients send this name.',
    )
    allow_backorder = serializers.BooleanField(
        required=False, write_only=True,
        help_text='Alias for `continue_selling_when_out_of_stock`.',
    )
    is_negotiable = serializers.BooleanField(
        required=False, write_only=True,
        help_text='Short alias for `is_eligible_to_negotiate_price`.',
    )

    class Meta:
        model = Product
        fields = [
            'name', 'description', 'short_description', 'category',
            'brand', 'price', 'compare_at_price', 'cost_per_item',
            'sku', 'barcode', 'stock', 'track_inventory',
            'continue_selling_when_out_of_stock', 'weight',
            'length', 'width', 'height', 'status',
            'is_featured', 'is_eligible_to_negotiate_price',
            'is_digital', 'requires_shipping',
            'meta_title', 'meta_description', 'specifications',
            # nested writes
            'variants', 'addon_groups',
            # aliases (write-only)
            'stock_quantity', 'allow_backorder', 'is_negotiable',
        ]

    def to_internal_value(self, data):
        # Normalise the legacy aliases BEFORE field-level validation so the
        # canonical fields take precedence when both are present.
        if hasattr(data, 'copy'):
            data = data.copy()
        if 'stock_quantity' in data and 'stock' not in data:
            data['stock'] = data['stock_quantity']
        if 'allow_backorder' in data and 'continue_selling_when_out_of_stock' not in data:
            data['continue_selling_when_out_of_stock'] = data['allow_backorder']
        if 'is_negotiable' in data and 'is_eligible_to_negotiate_price' not in data:
            data['is_eligible_to_negotiate_price'] = data['is_negotiable']
        return super().to_internal_value(data)

    def validate(self, attrs):
        # Drop the alias-only fields so they don't reach the model.
        for key in ('stock_quantity', 'allow_backorder', 'is_negotiable'):
            attrs.pop(key, None)

        # Cross-check selection bounds on each nested group.
        for group in attrs.get('addon_groups', []) or []:
            mn = group.get('min_selection', 0)
            mx = group.get('max_selection', 1)
            if mn > mx:
                raise serializers.ValidationError({
                    'addon_groups': "min_selection cannot exceed max_selection.",
                })
            if group.get('is_required') and mn < 1:
                # If the group is flagged required, force a sane minimum.
                group['min_selection'] = max(mn, 1)
        return attrs

    # ── Atomic create / update with nested children ──────────────────

    def _dedup_by_key(self, items, key):
        seen = set()
        unique = []
        for item in items:
            k = (item.get(key) or '').strip().lower()
            if not k or k in seen:
                continue
            seen.add(k)
            unique.append(item)
        return unique

    def create(self, validated_data):
        from django.db import transaction

        variants = validated_data.pop('variants', None) or []
        addon_groups = validated_data.pop('addon_groups', None) or []

        with transaction.atomic():
            product = super().create(validated_data)
            self._sync_variants(product, variants, replace=False)
            self._sync_addon_groups(product, addon_groups, replace=False)
        return product

    def update(self, instance, validated_data):
        from django.db import transaction

        variants = validated_data.pop('variants', None)
        addon_groups = validated_data.pop('addon_groups', None)

        with transaction.atomic():
            product = super().update(instance, validated_data)
            # ``None`` = leave the existing children alone (PATCH semantics).
            # An empty list ([]) = caller intentionally cleared them.
            if variants is not None:
                self._sync_variants(product, variants, replace=True)
            if addon_groups is not None:
                self._sync_addon_groups(product, addon_groups, replace=True)
        return product

    def _sync_variants(self, product, variants, *, replace):
        if replace:
            product.variants.all().delete()
        for entry in self._dedup_by_key(variants, 'name'):
            ProductVariant.objects.create(
                product=product,
                name=entry['name'],
                sku=entry.get('sku') or '',
                price=entry.get('price'),
                compare_at_price=entry.get('compare_at_price'),
                weight=entry.get('weight'),
                inventory_quantity=entry.get('inventory_quantity') or 0,
                is_active=entry.get('is_active', True),
            )

    def _sync_addon_groups(self, product, groups, *, replace):
        if replace:
            product.addon_groups.all().delete()
        for entry in self._dedup_by_key(groups, 'name'):
            addons = entry.get('addons') or []
            group = ProductAddonGroup.objects.create(
                product=product,
                name=entry['name'],
                group_type=entry.get('group_type', 'single'),
                is_required=entry.get('is_required', False),
                min_selection=entry.get('min_selection', 0),
                max_selection=entry.get('max_selection', 1),
                is_active=entry.get('is_active', True),
                sort_order=entry.get('sort_order', 0),
            )
            for addon in self._dedup_by_key(addons, 'name'):
                ProductAddon.objects.create(
                    group=group,
                    name=addon['name'],
                    price_delta=addon.get('price_delta', 0),
                    is_default=addon.get('is_default', False),
                    is_active=addon.get('is_active', True),
                    sort_order=addon.get('sort_order', 0),
                )


class WishlistSerializer(serializers.ModelSerializer):
    """Serializer for Wishlist model"""

    product_id = serializers.UUIDField(source='product.id', read_only=True)
    product_data = ProductListSerializer(source='product', read_only=True)

    class Meta:
        model = Wishlist
        fields = ['product_id', 'product', 'product_data', 'created_at']
        read_only_fields = ['product_id', 'created_at']
        extra_kwargs = {'product': {'write_only': True}}


class ProductLikeSerializer(serializers.ModelSerializer):
    """Serializer for ProductLike model"""

    product_data = ProductListSerializer(source='product', read_only=True)

    class Meta:
        model = ProductLike
        fields = ['id', 'product', 'product_data', 'created_at']
        read_only_fields = ['id', 'created_at']


class TopChildCategorySerializer(serializers.ModelSerializer):
    """Lightweight serializer for top children categories."""

    products_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image', 'products_count']
        read_only_fields = fields


class VendorReviewSerializer(serializers.ModelSerializer):
    """Serializer for VendorReview model"""

    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    vendor_email = serializers.CharField(source='vendor.user.email', read_only=True)
    vendor_info = serializers.SerializerMethodField()

    class Meta:
        model = VendorReview
        fields = [
            'id', 'vendor', 'vendor_info', 'user_email', 'user_name', 'vendor_email',
            'rating', 'title', 'comment',
            'is_approved', 'is_verified_purchase', 'helpful_count',
            'vendor_reply', 'vendor_replied_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'is_approved', 'is_verified_purchase', 'helpful_count',
            'vendor_reply', 'vendor_replied_at',
            'created_at', 'updated_at',
        ]

    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

    def get_vendor_info(self, obj):
        # obj.vendor is a VendorProfile; build_vendor_info wants the User.
        from business.utils import build_vendor_info
        return build_vendor_info(obj.vendor.user, self.context.get('request'))

    def validate(self, data):
        user = self.context['request'].user
        vendor_profile = data.get('vendor')
        if vendor_profile and vendor_profile.user_id == user.id:
            raise serializers.ValidationError("You cannot review yourself.")
        return data


class BannerImageSerializer(serializers.ModelSerializer):
    """Serializer for BannerImage model"""

    class Meta:
        model = BannerImage
        fields = ['id', 'image', 'alt_text', 'is_primary', 'sort_order', 'created_at']
        read_only_fields = ['id', 'created_at']


class BannerListSerializer(serializers.ModelSerializer):
    """Serializer for Banner list view"""

    category_name = serializers.CharField(source='category.name', read_only=True)
    images = BannerImageSerializer(many=True, read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = [
            'id', 'title', 'subtitle',
            'category', 'category_name',
            'images', 'primary_image',
            'is_active', 'sort_order', 'start_date', 'end_date',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_primary_image(self, obj):
        image = obj.images.filter(is_primary=True).first() or obj.images.first()
        if image:
            return BannerImageSerializer(image, context=self.context).data
        return None


class BannerCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating banners"""

    class Meta:
        model = Banner
        fields = [
            'title', 'subtitle',
            'category', 'is_active', 'sort_order',
            'start_date', 'end_date',
        ]
