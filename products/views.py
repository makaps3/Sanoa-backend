"""
Views for products app
"""
from rest_framework import viewsets, permissions, filters, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Category, Brand, Product, ProductReview, Wishlist, ProductLike,
    VendorReview, Banner, BannerImage, ProductVariant,
    ProductAddonGroup, ProductAddon, VendorCategory,
)
from .serializers import (
    CategorySerializer, FeaturedCategorySerializer, BrandSerializer,
    ProductListSerializer, ProductDetailSerializer, ProductCreateUpdateSerializer,
    ProductImageSerializer,
    ProductReviewSerializer, WishlistSerializer,
    ProductLikeSerializer, VendorReviewSerializer,
    TopChildCategorySerializer,
    BannerListSerializer, BannerCreateUpdateSerializer, BannerImageSerializer,
    ProductVariantSerializer,
    ProductAddonGroupSerializer, ProductAddonGroupWriteSerializer,
    ProductAddonSerializer,
    VendorCategorySerializer, VendorCategoryCreateSerializer,
)
from core.permissions import IsVendorOrAdmin, IsPlatformAdmin
from core.filters import ProductFilter
from core.pagination import StandardPagination


def _resolve_vendor(request, vendor_uuid):
    """
    Look up VendorProfile by UUID and verify ownership.
    Returns (vendor_profile, None) on success or (None, error Response) on failure.
    """
    from business.models import VendorProfile
    try:
        vp = VendorProfile.objects.get(id=vendor_uuid)
    except VendorProfile.DoesNotExist:
        return None, Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)
    if not request.user.is_staff:
        user_vp = getattr(request.user, 'vendor_profile', None)
        if user_vp != vp:
            return None, Response({'error': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
    return vp, None


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for product categories"""
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None
    lookup_field = 'slug'
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'sort_order', 'created_at']

    ALLOWED_BUSINESS_CATEGORIES = {'retail', 'restaurant'}

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsVendorOrAdmin()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        """
        Optionally filter by storefront mode via ?business_category=retail
        or ?business_category=restaurant. Categories tagged 'both' are
        always included so shared/general categories show up in either UI.

        Categories are annotated with `active_product_count` (active
        products linked to the category) and returned highest-first so
        the busiest categories surface at the top of the grid. Ties
        fall back to alphabetical (`name`) so the ordering is stable
        across requests.
        """
        queryset = Category.objects.filter(is_active=True)
        bc = self.request.query_params.get('business_category')
        if bc in self.ALLOWED_BUSINESS_CATEGORIES:
            queryset = queryset.filter(business_category__in=[bc, 'both'])
        return queryset.annotate(
            active_product_count=Count(
                'products', filter=Q(products__status='active'),
            ),
        ).order_by('-active_product_count', 'name')

    def list(self, request, *args, **kwargs):
        # Keep `filter_queryset` so SearchFilter (`?search=...`) still
        # works. DRF's OrderingFilter only clobbers the queryset order
        # when the client explicitly sends `?ordering=...`; otherwise
        # our count-based default from get_queryset is preserved.
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({'count': queryset.count(), 'results': serializer.data})

    @action(detail=False, methods=['get'], url_path='featured', permission_classes=[permissions.AllowAny])
    def featured(self, request):
        """Return featured categories with their nested children."""
        queryset = self.get_queryset().filter(is_featured=True).prefetch_related('children')
        serializer = FeaturedCategorySerializer(queryset, many=True)
        return Response({'count': queryset.count(), 'results': serializer.data})


class ProductVariantViewSet(viewsets.ModelViewSet):
    """
    Manage variants of a product (size / colour / etc.).

    Variants are scoped to a product. The vendor that owns the product is
    the only non-admin allowed to mutate them. Anonymous reads are allowed
    so customers can see the variant list when browsing.
    """
    serializer_class = ProductVariantSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        qs = ProductVariant.objects.select_related('product', 'product__vendor')
        product_id = self.request.query_params.get('product')
        if product_id:
            qs = qs.filter(product_id=product_id)
        if self.action in ['list', 'retrieve']:
            return qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsVendorOrAdmin()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        product = serializer.validated_data['product']
        vp = getattr(self.request.user, 'vendor_profile', None)
        if not self.request.user.is_staff and product.vendor != vp:
            raise permissions.exceptions.PermissionDenied(
                "You can only create variants for your own products."
            )
        serializer.save()

    def perform_update(self, serializer):
        instance = serializer.instance
        vp = getattr(self.request.user, 'vendor_profile', None)
        if not self.request.user.is_staff and instance.product.vendor != vp:
            raise permissions.exceptions.PermissionDenied(
                "You can only update variants on your own products."
            )
        serializer.save()

    def perform_destroy(self, instance):
        vp = getattr(self.request.user, 'vendor_profile', None)
        if not self.request.user.is_staff and instance.product.vendor != vp:
            raise permissions.exceptions.PermissionDenied(
                "You can only delete variants on your own products."
            )
        instance.delete()


class ProductAddonGroupViewSet(viewsets.ModelViewSet):
    """
    Manage add-on groups for products.

    An add-on group defines a category of options (e.g. "Choose your sauce",
    "Size", "Extra toppings") with selection rules (required/optional,
    min/max selections).

    Works for ALL product types:
    - Food: "Choose sauce" (required, single), "Extra toppings" (optional, multi)
    - Fast food: "Meal size" (required, single), "Add a drink" (optional, single)
    - Groceries: "Pack size" (required, single), "Ripeness" (optional, single)
    - Normal products: no groups needed (empty list)
    """
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProductAddonGroupWriteSerializer
        return ProductAddonGroupSerializer

    def get_queryset(self):
        qs = ProductAddonGroup.objects.select_related(
            'product', 'product__vendor',
        ).prefetch_related('addons')
        product_id = self.request.query_params.get('product')
        if product_id:
            qs = qs.filter(product_id=product_id)
        if self.action in ['list', 'retrieve']:
            return qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsVendorOrAdmin()]
        return [permissions.AllowAny()]

    def _check_ownership(self, product):
        vp = getattr(self.request.user, 'vendor_profile', None)
        if not self.request.user.is_staff and product.vendor != vp:
            raise permissions.exceptions.PermissionDenied(
                "You can only manage add-on groups on your own products."
            )

    def perform_create(self, serializer):
        self._check_ownership(serializer.validated_data['product'])
        serializer.save()

    def perform_update(self, serializer):
        self._check_ownership(serializer.instance.product)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_ownership(instance.product)
        instance.delete()


class ProductAddonViewSet(viewsets.ModelViewSet):
    """
    Manage individual add-on options within a group.

    Each add-on belongs to a ProductAddonGroup. Examples:
    - Group "Sauce" → addons: "BBQ", "Mayo", "Chili"
    - Group "Size" → addons: "S", "M", "L +R20", "XL +R40"
    """
    serializer_class = ProductAddonSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        qs = ProductAddon.objects.select_related(
            'group', 'group__product', 'group__product__vendor',
        )
        group_id = self.request.query_params.get('group')
        if group_id:
            qs = qs.filter(group_id=group_id)
        product_id = self.request.query_params.get('product')
        if product_id:
            qs = qs.filter(group__product_id=product_id)
        if self.action in ['list', 'retrieve']:
            return qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsVendorOrAdmin()]
        return [permissions.AllowAny()]

    def _check_ownership(self, group):
        product = group.product
        vp = getattr(self.request.user, 'vendor_profile', None)
        if not self.request.user.is_staff and product.vendor != vp:
            raise permissions.exceptions.PermissionDenied(
                "You can only manage add-ons on your own products."
            )

    def perform_create(self, serializer):
        self._check_ownership(serializer.validated_data['group'])
        serializer.save()

    def perform_update(self, serializer):
        self._check_ownership(serializer.instance.group)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_ownership(instance.group)
        instance.delete()


class BrandViewSet(viewsets.ModelViewSet):
    """ViewSet for product brands"""
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    search_fields = ['name', 'description']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsVendorOrAdmin()]
        return [permissions.AllowAny()]


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for products"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'short_description', 'sku']
    ordering_fields = ['price', 'created_at', 'sales_count', 'views_count', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = Product.objects.select_related('category', 'brand', 'vendor')
        if self.action == 'list':
            # Public list only shows active products
            if not self.request.user.is_staff:
                queryset = queryset.filter(status='active')
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return ProductCreateUpdateSerializer
        return ProductDetailSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsVendorOrAdmin()]
        return [permissions.AllowAny()]

    def _get_vendor(self):
        vendor_uuid = self.request.data.get('vendor_uuid')
        if vendor_uuid:
            vp, err = _resolve_vendor(self.request, vendor_uuid)
            if err:
                raise permissions.exceptions.PermissionDenied(
                    err.data.get('error', 'Access denied.')
                )
            return vp
        vp = getattr(self.request.user, 'vendor_profile', None)
        if vp is None:
            raise permissions.exceptions.PermissionDenied(
                "Provide vendor_uuid or ensure your account has a vendor profile."
            )
        return vp

    def _validate_category_for_vendor(self, category, vp):
        """Raise PermissionDenied if the vendor hasn't selected or created this category."""
        if not VendorCategory.objects.filter(vendor=vp, category=category).exists():
            name = getattr(category, 'name', 'that category')
            raise permissions.exceptions.PermissionDenied(
                f'"{name}" isn\'t one of your store categories yet. '
                'Add it under Categories in your dashboard, then try again.'
            )

    def _require_verified(self, vp):
        """Only verified stores may list products. Raises PermissionDenied
        with a customer-safe, actionable message otherwise (admins bypass)."""
        if self.request.user.is_staff:
            return
        status_value = getattr(vp, 'verification_status', 'pending')
        if status_value == 'verified':
            return
        friendly = {
            'pending': "Your store isn't verified yet. Complete your vetting "
                       "application — verify the owner, upload your business "
                       "documents and add your bank account — to start "
                       "listing products.",
            'under_review': "Your verification is under review. You'll be able "
                            "to add products once an admin approves your store.",
            'owner_verified': "Your business documents and bank details still "
                              "need to be verified before you can add products. "
                              "Finish your vetting application.",
            'rejected': "Your verification was declined. Please review the "
                        "notes on your vetting application, re-upload the "
                        "flagged documents and resubmit before adding products.",
            'suspended': "Your store is suspended, so products can't be added. "
                         "Please contact support.",
        }.get(status_value,
              "Your store must be verified before you can add products.")
        raise permissions.exceptions.PermissionDenied(friendly)

    def perform_create(self, serializer):
        """
        Create a product + nested variants/add-on groups in a single
        transaction. The serializer already de-dupes children by ``name`` so
        retries from the client (network blip, double-tap) don't introduce
        duplicates.
        """
        from django.db import transaction

        vp = self._get_vendor()
        self._require_verified(vp)
        category = serializer.validated_data.get('category')
        if category:
            self._validate_category_for_vendor(category, vp)

        # Block restaurants' add-on groups for retail-only vendors so the
        # UI's "hide for retail" rule is enforced server-side too.
        if (
            serializer.validated_data.get('addon_groups')
            and getattr(vp, 'business_category', '') == 'retail'
        ):
            raise permissions.exceptions.PermissionDenied(
                "Add-on groups are only available for restaurant-mode vendors."
            )

        with transaction.atomic():
            from business.models import VendorProfile
            from tiers.entitlements import product_limit
            VendorProfile.objects.select_for_update().get(pk=vp.pk)
            limit = product_limit(vp)
            if limit and Product.objects.filter(vendor=vp).count() >= limit:
                from rest_framework.exceptions import ValidationError
                raise ValidationError('Your current plan product limit has been reached. Subscribe to restore a higher limit.')
            product = serializer.save(vendor=vp)
            # QR code is auto-generated in Product.save(), but call again
            # defensively in case the hook missed (e.g. fixtures).
            if not product.qr_code:
                product.generate_qr_code()
                product.save(update_fields=['qr_code'])

    def perform_update(self, serializer):
        from django.db import transaction

        vp = getattr(self.request.user, 'vendor_profile', None)
        if not self.request.user.is_staff:
            if vp is None:
                raise permissions.exceptions.PermissionDenied("No vendor profile found.")
            category = serializer.validated_data.get('category')
            if category:
                self._validate_category_for_vendor(category, vp)
            if (
                serializer.validated_data.get('addon_groups')
                and getattr(vp, 'business_category', '') == 'retail'
            ):
                raise permissions.exceptions.PermissionDenied(
                    "Add-on groups are only available for restaurant-mode vendors."
                )
        with transaction.atomic():
            serializer.save()

    @action(detail=True, methods=['get'], url_path='variants',
            permission_classes=[permissions.AllowAny])
    def variants(self, request, pk=None):
        """GET /api/products/products/<uuid>/variants/"""
        product = self.get_object()
        from .models import ProductVariant
        qs = ProductVariant.objects.filter(
            product=product, is_active=True
        ).order_by('name')
        serializer = ProductVariantSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'], url_path='images',
            permission_classes=[permissions.IsAuthenticatedOrReadOnly])
    def images(self, request, pk=None):
        """
        GET  /api/products/products/<uuid>/images/  — list product images
        POST /api/products/products/<uuid>/images/  — upload a new image (vendor/admin only)
        """
        product = self.get_object()
        from .models import ProductImage

        if request.method == 'GET':
            qs = product.images.all().order_by('sort_order')
            serializer = ProductImageSerializer(qs, many=True, context={'request': request})
            return Response(serializer.data)

        # POST — only the owning vendor or admin may upload
        if not request.user.is_staff:
            vp = getattr(request.user, 'vendor_profile', None)
            if product.vendor != vp:
                return Response(
                    {'error': 'You can only upload images for your own products.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        serializer = ProductImageSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def increment_views(self, request, pk=None):
        """Increment product view count"""
        product = self.get_object()
        product.views_count += 1
        product.save(update_fields=['views_count'])
        return Response({'views_count': product.views_count})

    @action(detail=False, methods=['get', 'post'], url_path='scan-qr', permission_classes=[permissions.AllowAny])
    def scan_qr(self, request):
        """Look up a product by its QR code identifier and return full details."""
        import json as _json

        code = request.data.get('code') or request.query_params.get('code')
        if not code:
            return Response(
                {'error': '"code" is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # QR code encodes a JSON object — Flutter may send the raw string
        # (JSON with double quotes or Python repr with single quotes) or the
        # already-parsed dict. Unwrap whichever form arrives.
        if isinstance(code, str):
            import ast as _ast
            try:
                code = _json.loads(code)
            except (_json.JSONDecodeError, ValueError):
                try:
                    code = _ast.literal_eval(code)
                except (ValueError, SyntaxError):
                    pass

        qs = Product.objects.select_related('category', 'brand', 'vendor')

        if isinstance(code, dict):
            product_id = code.get('product_id')
            qr_id = code.get('id')
            if product_id:
                product = get_object_or_404(qs, id=product_id)
            elif qr_id:
                product = get_object_or_404(qs, qr_code_identifier=qr_id)
            else:
                return Response({'error': 'Invalid QR code payload.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            product = get_object_or_404(qs, qr_code_identifier=code)

        serializer = ProductDetailSerializer(product, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='recommended', permission_classes=[permissions.IsAuthenticated])
    def recommended(self, request):
        """Get ML-powered product recommendations for the current user."""
        from core.recommendations import ProductRecommendationEngine

        engine = ProductRecommendationEngine()
        limit = int(request.query_params.get('limit', 20))
        recommended_ids = engine.recommend_for_user(request.user, limit=limit)

        products = Product.objects.filter(id__in=recommended_ids).select_related(
            'category', 'brand', 'vendor'
        )
        # Preserve the recommendation order
        product_map = {p.id: p for p in products}
        ordered = [product_map[pid] for pid in recommended_ids if pid in product_map]

        serializer = ProductListSerializer(ordered, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='similar', permission_classes=[permissions.AllowAny])
    def similar(self, request, pk=None):
        """Get products similar to a given product using ML content-based filtering."""
        from core.recommendations import ProductRecommendationEngine

        engine = ProductRecommendationEngine()
        limit = int(request.query_params.get('limit', 10))
        similar_ids = engine.get_similar_products(pk, limit=limit)

        products = Product.objects.filter(id__in=similar_ids).select_related(
            'category', 'brand', 'vendor'
        )
        product_map = {p.id: p for p in products}
        ordered = [product_map[pid] for pid in similar_ids if pid in product_map]

        serializer = ProductListSerializer(ordered, many=True, context={'request': request})
        return Response(serializer.data)


class VendorCategoryViewSet(viewsets.ViewSet):
    """
    Vendor category management.

    Vendors select from system categories or create their own.
    Products can only be linked to categories in this vendor's selection.

    GET    /api/products/vendor/<vendor_uuid>/categories/           — list selected categories
    POST   /api/products/vendor/<vendor_uuid>/categories/           — create a custom category
    POST   /api/products/vendor/<vendor_uuid>/categories/select/    — select a system category
    DELETE /api/products/vendor/<vendor_uuid>/categories/<pk>/      — deselect / delete custom
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, vendor_uuid):
        vp, err = _resolve_vendor(request, vendor_uuid)
        if err:
            return err
        vc_qs = (
            VendorCategory.objects
            .filter(vendor=vp)
            .select_related('category', 'category__parent')
            .order_by('category__name')
        )
        serializer = VendorCategorySerializer(vc_qs, many=True)
        return Response(serializer.data)

    def create(self, request, vendor_uuid):
        """Create a brand-new custom category and auto-select it for this vendor."""
        vp, err = _resolve_vendor(request, vendor_uuid)
        if err:
            return err
        serializer = VendorCategoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data['name']
        # Prevent duplicate custom category name for this vendor
        if Category.objects.filter(name=name, vendor=vp, is_system=False).exists():
            return Response(
                {'error': f'You already have a custom category named "{name}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        category = serializer.save(vendor=vp, is_system=False, is_active=True)
        vc = VendorCategory.objects.create(vendor=vp, category=category)
        return Response(VendorCategorySerializer(vc).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='select')
    def select(self, request, vendor_uuid):
        """Select an existing system category for this vendor."""
        vp, err = _resolve_vendor(request, vendor_uuid)
        if err:
            return err
        category_id = request.data.get('category_id')
        if not category_id:
            return Response(
                {'error': 'category_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            category = Category.objects.get(id=category_id, is_active=True, is_system=True)
        except Category.DoesNotExist:
            return Response(
                {'error': 'System category not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        vc, created = VendorCategory.objects.get_or_create(vendor=vp, category=category)
        return Response(
            VendorCategorySerializer(vc).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def destroy(self, request, vendor_uuid, pk=None):
        """
        Deselect a category.
        - System category: removes the VendorCategory link only.
        - Custom category: also deletes the Category itself if no products use it.
        """
        vp, err = _resolve_vendor(request, vendor_uuid)
        if err:
            return err
        try:
            vc = VendorCategory.objects.select_related('category').get(
                vendor=vp, pk=pk
            )
        except VendorCategory.DoesNotExist:
            return Response(
                {'error': 'Category not in your selection.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if Product.objects.filter(vendor=vp, category=vc.category).exists():
            return Response(
                {'error': 'Cannot remove a category that still has products linked to it.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        is_custom = not vc.category.is_system
        cat = vc.category
        vc.delete()
        if is_custom:
            cat.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorProductListView(generics.ListAPIView):
    """GET /api/products/vendor/<vendor_uuid>/products/"""
    serializer_class = ProductListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        vp, _ = _resolve_vendor(self.request, self.kwargs['vendor_uuid'])
        if vp is None:
            return Product.objects.none()
        return (
            Product.objects
            .filter(vendor=vp)
            .select_related('category', 'brand', 'vendor')
            .order_by('-created_at')
        )

    def list(self, request, *args, **kwargs):
        _, err = _resolve_vendor(request, self.kwargs['vendor_uuid'])
        if err:
            return err
        return super().list(request, *args, **kwargs)


class BannerViewSet(viewsets.ModelViewSet):
    """ViewSet for promotional banners linked to categories."""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        from django.utils import timezone
        queryset = Banner.objects.select_related('category')
        if self.action == 'list':
            queryset = queryset.filter(is_active=True)
            now = timezone.now()
            queryset = queryset.filter(
                Q(start_date__isnull=True) | Q(start_date__lte=now),
                Q(end_date__isnull=True) | Q(end_date__gte=now),
            )
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        return queryset

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return BannerCreateUpdateSerializer
        return BannerListSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsVendorOrAdmin()]
        return [permissions.AllowAny()]

    @action(detail=False, methods=['get'], url_path='by-parent-category', permission_classes=[permissions.AllowAny])
    def by_parent_category(self, request):
        """
        Get active banners for a parent category and all its children.
        Query params: parent_category_id (required)
        """
        from django.utils import timezone

        parent_category_id = request.query_params.get('parent_category_id')
        if not parent_category_id:
            return Response(
                {'error': 'parent_category_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent_category = get_object_or_404(Category, id=parent_category_id, is_active=True)
        child_ids = list(
            parent_category.children.filter(is_active=True).values_list('id', flat=True)
        )
        all_category_ids = [parent_category.id] + child_ids

        now = timezone.now()
        banners = Banner.objects.select_related('category').filter(
            is_active=True,
            category_id__in=all_category_ids,
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=now),
            Q(end_date__isnull=True) | Q(end_date__gte=now),
        )

        serializer = BannerListSerializer(banners, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'], url_path='images')
    def images(self, request, pk=None):
        """
        GET: list all images for a banner.
        POST: add an image to a banner. Body: image (file), alt_text (optional), is_primary (optional).
        """
        banner = self.get_object()

        if request.method == 'GET':
            serializer = BannerImageSerializer(banner.images.all(), many=True, context={'request': request})
            return Response(serializer.data)

        serializer = BannerImageSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(banner=banner)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path='images/(?P<image_id>[^/.]+)')
    def delete_image(self, request, pk=None, image_id=None):
        """Delete a specific image from a banner."""
        banner = self.get_object()
        image = get_object_or_404(BannerImage, id=image_id, banner=banner)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for product reviews"""
    serializer_class = ProductReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = ProductReview.objects.select_related('product', 'user')
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_approved=True)
        return queryset

    def perform_create(self, serializer):
        # Auto-flag verified purchase when the reviewer has at least one
        # completed retail or restaurant order containing this product.
        # Saves the client from having to send the flag itself and makes
        # the badge tamper-proof.
        user = self.request.user
        product = serializer.validated_data['product']
        is_verified = self._user_purchased_product(user, product)
        serializer.save(user=user, is_verified_purchase=is_verified)

    @staticmethod
    def _user_purchased_product(user, product):
        # Retail
        from orders.models import OrderItem
        if OrderItem.objects.filter(
            order__user=user,
            order__status__in=['delivered', 'completed'],
            product=product,
        ).exists():
            return True
        # Restaurant
        try:
            from restaurant.models import RestaurantOrderItem
            if RestaurantOrderItem.objects.filter(
                order__user=user,
                order__status__in=['delivered', 'completed'],
                product=product,
            ).exists():
                return True
        except Exception:
            # If restaurant app is unavailable, fall through silently.
            pass
        return False

    @action(detail=False, methods=['get'], url_path='vendor/(?P<vendor_uuid>[^/.]+)',
            permission_classes=[permissions.AllowAny])
    def vendor_reviews(self, request, vendor_uuid=None):
        """
        GET /api/products/reviews/vendor/<vendor_uuid>/
        All approved product reviews for every product owned by this vendor.
        Supports ?rating=4 and ?product=<uuid> filters.
        """
        from django.db.models import Avg, Count
        from business.models import VendorProfile
        try:
            vp = VendorProfile.objects.get(id=vendor_uuid)
        except VendorProfile.DoesNotExist:
            return Response({'error': 'Vendor not found.'}, status=status.HTTP_404_NOT_FOUND)

        qs = ProductReview.objects.filter(
            product__vendor=vp, is_approved=True
        ).select_related('product', 'user').order_by('-created_at')

        rating_filter = request.query_params.get('rating')
        if rating_filter:
            qs = qs.filter(rating=rating_filter)

        product_filter = request.query_params.get('product')
        if product_filter:
            qs = qs.filter(product_id=product_filter)

        stats = qs.aggregate(average_rating=Avg('rating'), total=Count('id'))

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['average_rating'] = round(stats['average_rating'] or 0, 2)
            response.data['total_reviews'] = stats['total'] or 0
            return response

        serializer = self.get_serializer(qs, many=True)
        return Response({
            'average_rating': round(stats['average_rating'] or 0, 2),
            'total_reviews': stats['total'] or 0,
            'results': serializer.data,
        })


class WishlistViewSet(viewsets.ModelViewSet):
    """ViewSet for user wishlists"""
    serializer_class = WishlistSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'product'

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related('product')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='check/(?P<product_id>[^/.]+)')
    def check(self, request, product_id=None):
        """Return whether a product UUID is in the authenticated user's wishlist."""
        in_wishlist = self.get_queryset().filter(product=product_id).exists()
        return Response({'in_wishlist': in_wishlist, 'product': product_id})


class ProductLikeViewSet(viewsets.GenericViewSet):
    """
    Like/unlike products and list liked products.
    Likes are public social signals (unlike wishlists which are private).
    """
    serializer_class = ProductLikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProductLike.objects.filter(
            user=self.request.user
        ).select_related('product__category', 'product__brand')

    @action(detail=False, methods=['get'], url_path='my-likes')
    def my_likes(self, request):
        """List all products the current user has liked."""
        queryset = self.get_queryset()
        serializer = ProductLikeSerializer(queryset, many=True)
        return Response(serializer.data)

    @staticmethod
    def _like_payload(product_id, *, is_liked):
        """Canonical response body used by like / unlike / toggle / count.

        Emits both `like_count` and `likes_count` so the client model
        parsers — which historically use one or the other — both pick
        up the value without a separate migration.
        """
        total = ProductLike.objects.filter(product_id=product_id).count()
        return {
            'product_id': str(product_id),
            'like_count': total,
            'likes_count': total,
            'is_liked': is_liked,
        }

    @action(detail=False, methods=['post'])
    def like(self, request):
        """Like a product. Body: {"product": "<uuid>"}"""
        serializer = ProductLikeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data['product']
        _, created = ProductLike.objects.get_or_create(
            user=request.user, product=product,
        )
        status_code = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        return Response(
            self._like_payload(product.id, is_liked=True),
            status=status_code,
        )

    @action(detail=False, methods=['post'])
    def unlike(self, request):
        """Unlike a product. Body: {"product_id": "<uuid>"}"""
        product_id = request.data.get('product_id') or request.data.get('product')
        if not product_id:
            return Response(
                {'error': 'product_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ProductLike.objects.filter(
            user=request.user, product_id=product_id,
        ).delete()
        return Response(self._like_payload(product_id, is_liked=False))

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Flip the like state for a product.

        Body: {"product": "<uuid>"} or {"product_id": "<uuid>"}.

        Returns the canonical like payload (with both `like_count` and
        `likes_count` for parser compatibility) and a fresh `is_liked`
        flag. The frontend's single-button like control uses this so
        the count can never drift between request types.
        """
        product_id = request.data.get('product') or request.data.get('product_id')
        if not product_id:
            return Response(
                {'error': 'product is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = Product.objects.only('id').get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        existing = ProductLike.objects.filter(
            user=request.user, product=product,
        ).first()
        if existing:
            existing.delete()
            is_liked = False
            status_code = status.HTTP_200_OK
        else:
            ProductLike.objects.create(user=request.user, product=product)
            is_liked = True
            status_code = status.HTTP_201_CREATED

        return Response(
            self._like_payload(product.id, is_liked=is_liked),
            status=status_code,
        )

    @action(detail=False, methods=['get'], url_path='count/(?P<product_id>[^/.]+)',
            permission_classes=[permissions.AllowAny])
    def count(self, request, product_id=None):
        """Get like count for a product and whether current user liked it."""
        is_liked = ProductLike.objects.filter(
            user=request.user, product_id=product_id,
        ).exists() if request.user.is_authenticated else False
        return Response(self._like_payload(product_id, is_liked=is_liked))


class CategoryProductsView(APIView):
    """
    Returns product lists for a given category:
    - new_products: latest products
    - popular_products: ranked by reviews, likes, views
    - top_children_categories: child categories with most products
    - best_selling_products: ranked by sales_count

    Query params:
        parent_category_id (required): ID of the parent category
        category_name (optional): filter by category name
        child_category_id (optional): narrow down to a specific child category
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        parent_category_id = request.query_params.get('parent_category_id')
        if not parent_category_id:
            return Response(
                {'error': 'parent_category_id is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent_category = get_object_or_404(Category, id=parent_category_id, is_active=True)

        child_category_id = request.query_params.get('child_category_id')
        category_name = request.query_params.get('category_name')

        # Base product queryset: active products in parent or any of its children
        child_ids = list(
            parent_category.children.filter(is_active=True).values_list('id', flat=True)
        )
        all_category_ids = [parent_category.id] + child_ids

        products = Product.objects.filter(
            status='active',
            category_id__in=all_category_ids,
        ).select_related('category', 'brand', 'vendor')

        # Optional filters
        if category_name:
            products = products.filter(category__name__icontains=category_name)

        if child_category_id:
            products = products.filter(category_id=child_category_id)

        # 1. New products - latest by created_at
        new_products = products.order_by('-created_at')[:20]

        # 2. Popular products - scored by reviews + likes + views
        popular_products = products.annotate(
            review_total=Count('reviews', filter=Q(reviews__is_approved=True)),
            likes_total=Count('likes'),
        ).order_by('-review_total', '-likes_total', '-views_count')[:20]

        # 3. Top children categories (always relative to parent, not filtered by child_category_id)
        top_children = (
            parent_category.children
            .filter(is_active=True)
            .annotate(products_count=Count('products', filter=Q(products__status='active')))
            .order_by('-products_count')[:10]
        )

        # 4. Best selling products
        best_selling = products.order_by('-sales_count')[:20]

        # 5. Featured products
        featured_products = products.filter(is_featured=True).order_by('-created_at')[:20]

        context = {'request': request}
        return Response({
            'parent_category': {
                'id': parent_category.id,
                'name': parent_category.name,
                'slug': parent_category.slug,
            },
            'new_products': ProductListSerializer(new_products, many=True, context=context).data,
            'popular_products': ProductListSerializer(popular_products, many=True, context=context).data,
            'top_children_categories': TopChildCategorySerializer(top_children, many=True, context=context).data,
            'best_selling_products': ProductListSerializer(best_selling, many=True, context=context).data,
            'featured_products': ProductListSerializer(featured_products, many=True, context=context).data,
        })


class VendorReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for vendor/store reviews.
    Customers rate and review vendors on service, delivery, and professionalism.
    """
    serializer_class = VendorReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = VendorReview.objects.select_related('user', 'vendor')
        vendor_id = self.request.query_params.get('vendor')
        if vendor_id:
            queryset = queryset.filter(vendor_id=vendor_id)
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_approved=True)
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=['get'], url_path='vendor-summary/(?P<vendor_id>[^/.]+)')
    def vendor_summary(self, request, vendor_id=None):
        """Get review summary for a vendor: average rating, total, breakdown."""
        from django.db.models import Avg, Count
        reviews = VendorReview.objects.filter(vendor_id=vendor_id, is_approved=True)
        stats = reviews.aggregate(
            average_rating=Avg('rating'),
            total_reviews=Count('id'),
        )
        breakdown = {}
        for i in range(1, 6):
            breakdown[f'{i}_star'] = reviews.filter(rating=i).count()
        return Response({
            'vendor_id': vendor_id,
            'average_rating': round(stats['average_rating'] or 0, 2),
            'total_reviews': stats['total_reviews'],
            'breakdown': breakdown,
        })

    @staticmethod
    def _acting_vendor_profile(user):
        """The VendorProfile the user manages — owner or employee — else None."""
        vp = getattr(user, 'vendor_profile', None)
        if vp is not None:
            return vp
        emp = getattr(user, 'vendor_employment', None)
        return getattr(emp, 'vendor', None) if emp is not None else None

    def _paginated(self, queryset):
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=['post'], url_path='reply',
            permission_classes=[permissions.IsAuthenticated])
    def reply(self, request, pk=None):
        """Vendor posts (or updates) a public reply to a review on their store."""
        from django.utils import timezone
        review = get_object_or_404(VendorReview, pk=pk)
        vp = self._acting_vendor_profile(request.user)
        if vp is None or review.vendor_id != vp.id:
            return Response(
                {'error': 'You can only reply to reviews on your own store.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        text = (request.data.get('reply')
                or request.data.get('vendor_reply') or '').strip()
        if not text:
            return Response({'error': 'Reply text is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        review.vendor_reply = text[:2000]
        review.vendor_replied_at = timezone.now()
        review.save(update_fields=[
            'vendor_reply', 'vendor_replied_at', 'updated_at',
        ])
        return Response(self.get_serializer(review).data)

    @action(detail=False, methods=['get'], url_path='my-vendor-reviews',
            permission_classes=[permissions.IsAuthenticated])
    def my_vendor_reviews(self, request):
        """All reviews on the requesting vendor's store (owner/employee)."""
        vp = self._acting_vendor_profile(request.user)
        if vp is None:
            return Response({'error': 'No vendor profile on this account.'},
                            status=status.HTTP_403_FORBIDDEN)
        qs = (VendorReview.objects.filter(vendor=vp)
              .select_related('user', 'vendor').order_by('-created_at'))
        return self._paginated(qs)

    @action(detail=False, methods=['get'], url_path='admin-all',
            permission_classes=[IsPlatformAdmin])
    def admin_all(self, request):
        """Every vendor review across the platform (platform admins)."""
        qs = (VendorReview.objects
              .select_related('user', 'vendor').order_by('-created_at'))
        vendor_id = request.query_params.get('vendor')
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        rating = request.query_params.get('rating')
        if rating:
            qs = qs.filter(rating=rating)
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(comment__icontains=search)
                | Q(title__icontains=search)
                | Q(user__email__icontains=search)
                | Q(vendor__name__icontains=search)
                | Q(vendor__trading_name__icontains=search)
            )
        return self._paginated(qs)


class AdminProductListView(generics.ListAPIView):
    """
    GET /api/products/admin/all/
    Returns all products across every vendor. Platform admins only.
    Supports filtering (?is_active=, ?vendor=, ?category=) and search (?search=).
    """
    serializer_class = ProductListSerializer
    permission_classes = [IsPlatformAdmin]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['name', 'price', 'created_at', 'stock']
    ordering = ['-created_at']

    def get_queryset(self):
        return (
            Product.objects
            .select_related('category', 'brand', 'vendor__user')
            .prefetch_related('images')
            .all()
        )
