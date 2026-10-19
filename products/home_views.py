"""Customer home-screen feeds.

One endpoint with two response shapes — retail vs restaurant — so the
flutter shell can render two completely different home experiences
without making N round-trips for each section.

GET /api/products/home/?business_category=retail
GET /api/products/home/?business_category=restaurant

Each call returns a single payload with every section the home tab needs:
banners, categories, featured/trending/new products, top vendors, and a
mode-specific summary block (store count for retail, dish + restaurant
counts and avg delivery time for restaurant).

Keeping it in a separate module so we don't bloat products/views.py.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from django.db.models import Avg, Count, Q
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from business.models import VendorProfile
from .models import Banner, Category, Product
from .serializers import (
    BannerListSerializer,
    CategorySerializer,
    ProductListSerializer,
)


# ── Constants ────────────────────────────────────────────────────────────

_RETAIL = 'retail'
_RESTAURANT = 'restaurant'

# Top-N caps per section so the payload stays compact.
_BANNER_LIMIT = 6
_CATEGORY_LIMIT = 10
_FEATURED_LIMIT = 10
_TRENDING_LIMIT = 10
_NEW_LIMIT = 10
_VENDOR_LIMIT = 8


# ── Public entry point ───────────────────────────────────────────────────


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def category_showcase(request: Request, category_id) -> Response:
    """Curated showcase for a single category.

    GET /api/products/categories/<int:category_id>/showcase/?business_category=retail|restaurant

    Returns five marketable sections — each with a customer-friendly
    description, a featured "top pick" product (the strongest member by
    that section's ranking signal), and the full ordered list of every
    eligible product in the section. Same product can appear in more
    than one section (that's the point — a great dish is featured AND
    top-rated AND popular).

    Sections:
      • featured       — products with `is_featured=True`, freshest first
      • most_ordered   — by sales_count
      • new_arrivals   — by created_at desc
      • top_rated      — by average review rating (then review_count)
      • most_viewed    — by views_count
    """
    business_category = (
        request.query_params.get('business_category') or _RETAIL
    ).lower()
    if business_category not in (_RETAIL, _RESTAURANT):
        business_category = _RETAIL
    is_restaurant = business_category == _RESTAURANT

    try:
        category = Category.objects.get(id=category_id, is_active=True)
    except (Category.DoesNotExist, ValueError):
        return Response({'detail': 'Category not found.'}, status=404)

    base = (
        Product.objects
        .filter(status='active', category=category)
        .select_related('vendor', 'category', 'brand')
        .prefetch_related('images')
    )

    featured  = list(base.filter(is_featured=True).order_by('-updated_at')[:20])
    ordered   = list(base.order_by('-sales_count', '-views_count')[:20])
    new_arr   = list(base.order_by('-created_at')[:20])
    rated     = list(
        base.annotate(
            review_rating_avg=Avg('reviews__rating'),
            review_total=Count('reviews'),
        )
        .order_by('-review_rating_avg', '-review_total', '-updated_at')[:20]
    )
    viewed    = list(base.order_by('-views_count', '-sales_count')[:20])

    # Pick a featured product to spotlight in the hero. Falls back to any
    # of the section's products so the spotlight never goes empty when
    # the category has nothing flagged `is_featured`.
    def _pick_top(items):
        return items[0] if items else None

    ctx = {'request': request}
    sections = {
        'featured': _section(
            description=_copy_featured(category.name, is_restaurant),
            top=_pick_top(featured),
            products=featured,
            ctx=ctx,
        ),
        'most_ordered': _section(
            description=_copy_most_ordered(category.name, is_restaurant),
            top=_pick_top(ordered),
            products=ordered,
            ctx=ctx,
        ),
        'new_arrivals': _section(
            description=_copy_new_arrivals(category.name, is_restaurant),
            top=_pick_top(new_arr),
            products=new_arr,
            ctx=ctx,
        ),
        'top_rated': _section(
            description=_copy_top_rated(category.name, is_restaurant),
            top=_pick_top(rated),
            products=rated,
            ctx=ctx,
        ),
        'most_viewed': _section(
            description=_copy_most_viewed(category.name, is_restaurant),
            top=_pick_top(viewed),
            products=viewed,
            ctx=ctx,
        ),
    }

    return Response({
        'category': {
            'id':                str(category.id),
            'name':              category.name,
            'description':       (getattr(category, 'description', '') or '').strip(),
            'image':             _abs_url(category.image) if getattr(category, 'image', None) else None,
            'business_category': category.business_category,
        },
        'mode':     business_category,
        'sections': sections,
    })


def _section(*, description, top, products, ctx) -> dict:
    return {
        'description': description,
        'top':         ProductListSerializer(top, context=ctx).data if top else None,
        'products':    ProductListSerializer(products, many=True, context=ctx).data,
        'count':       len(products),
    }


# ── Customer-facing section copy ─────────────────────────────────────────
#
# Short, marketable taglines used as the description for each section.
# Restaurant variants lean into food-delivery language ("dishes",
# "tonight"); retail variants lean into shopping language ("picks",
# "this week").

def _copy_featured(name: str, is_restaurant: bool) -> str:
    return (
        f"The very best of {name} — chef-curated dishes you have to try."
        if is_restaurant
        else f"The very best of {name} — editor-picked just for you."
    )


def _copy_most_ordered(name: str, is_restaurant: bool) -> str:
    return (
        f"What everyone's ordering in {name} tonight — fan favourites you'll love."
        if is_restaurant
        else f"This week's bestsellers in {name} — what everyone's buying."
    )


def _copy_new_arrivals(name: str, is_restaurant: bool) -> str:
    return (
        f"New on the {name} menu — fresh dishes worth a try."
        if is_restaurant
        else f"Just landed in {name} — be the first to discover them."
    )


def _copy_top_rated(name: str, is_restaurant: bool) -> str:
    return (
        f"Highest-rated {name} dishes — loved by hundreds of diners."
        if is_restaurant
        else f"Top-rated in {name} — reviewed and recommended by real customers."
    )


def _copy_most_viewed(name: str, is_restaurant: bool) -> str:
    return (
        f"Trending in {name} — the dishes everyone's eyeing right now."
        if is_restaurant
        else f"Hot in {name} — the products catching everyone's eye."
    )


def _vendor_storefront_payload(request, vendor_uuid, *, kind):
    """Shared body for the single-vendor public storefront endpoint.

    `kind` is purely cosmetic — it picks the 404 copy and the
    restaurant-flavoured response keys (`dish_count`,
    `avg_delivery_minutes`). The query/serialization is identical for
    retail and restaurant vendors so the frontend can render either
    storefront from the same payload.
    """
    try:
        vendor = (
            VendorProfile.objects
            .annotate(item_count=Count(
                'products', filter=Q(products__status='active'),
            ))
            .get(id=vendor_uuid)
        )
    except VendorProfile.DoesNotExist:
        label = 'Restaurant' if kind == _RESTAURANT else 'Store'
        return Response({'detail': f'{label} not found.'}, status=404)

    products = (
        Product.objects
        .filter(status='active', vendor=vendor)
        .select_related('category', 'brand', 'vendor')
        .prefetch_related('images')
        .order_by('-is_featured', '-sales_count', '-updated_at')[:60]
    )

    ctx = {'request': request}
    logo = None
    try:
        if vendor.logo:
            logo = request.build_absolute_uri(vendor.logo.url) if request else vendor.logo.url
    except (ValueError, AttributeError):
        logo = None

    vendor_block = {
        'id':                str(vendor.id),
        'name':              vendor.trading_name or vendor.name or '',
        'description':       (getattr(vendor, 'description', '') or '').strip(),
        'logo':              logo,
        'business_category': vendor.business_category,
        'average_rating':    str(vendor.average_rating or '0.00'),
        # Always expose `product_count` so a single frontend model can
        # rely on it regardless of vendor kind; keep `dish_count` for
        # restaurant clients that already read it.
        'product_count':     vendor.item_count,
    }
    if kind == _RESTAURANT:
        vendor_block['dish_count'] = vendor.item_count
        vendor_block['avg_delivery_minutes'] = 30

    return Response({
        'vendor': vendor_block,
        'products': ProductListSerializer(products, many=True, context=ctx).data,
    })


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def restaurant_detail(request: Request, vendor_uuid) -> Response:
    """Public single-restaurant page payload.

    GET /api/products/restaurants/<vendor_uuid>/
    """
    return _vendor_storefront_payload(request, vendor_uuid, kind=_RESTAURANT)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def retail_detail(request: Request, vendor_uuid) -> Response:
    """Public single-retail-store page payload.

    GET /api/products/retail/<vendor_uuid>/

    Same shape as the restaurant detail endpoint so the frontend can
    reuse its storefront screen for retail vendors.
    """
    return _vendor_storefront_payload(request, vendor_uuid, kind=_RETAIL)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def customer_home(request: Request) -> Response:
    """Dispatcher — pick retail or restaurant payload from the query.

    Anonymous browsing is allowed; per-user fields (e.g. wishlist flags)
    fall through to the underlying serializers which handle missing auth.
    """
    business_category = (request.query_params.get('business_category') or _RETAIL).lower()
    if business_category not in (_RETAIL, _RESTAURANT):
        business_category = _RETAIL

    if business_category == _RESTAURANT:
        return Response(_build_restaurant_home(request))
    return Response(_build_retail_home(request))


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def recommended_products(request: Request) -> Response:
    """Smart recommendations from the customer's own order history.

    GET /api/products/recommended-for-you/?business_category=retail|restaurant

    Surfaces products in the categories and stores the customer usually
    orders from (retail via OrderItem, restaurant via RestaurantOrderItem),
    excluding what they've already bought. Falls back to popular products in
    that storefront for new / anonymous users, so it never returns empty.
    """
    business_category = (request.query_params.get('business_category') or _RETAIL).lower()
    if business_category not in (_RETAIL, _RESTAURANT):
        business_category = _RETAIL
    try:
        limit = min(int(request.query_params.get('limit', 12)), 30)
    except (TypeError, ValueError):
        limit = 12

    from core.recommendations import ProductRecommendationEngine
    engine = ProductRecommendationEngine()
    ids = engine.recommend_from_order_history(
        request.user, business_category=business_category, limit=limit,
    )

    products = (
        Product.objects.filter(id__in=ids)
        .select_related('vendor', 'category', 'brand')
        .prefetch_related('images')
    )
    pmap = {p.id: p for p in products}
    ordered = [pmap[i] for i in ids if i in pmap]

    ctx = {'request': request}
    return Response({
        'business_category': business_category,
        'products': ProductListSerializer(ordered, many=True, context=ctx).data,
    })


# ── Retail (e-commerce) ──────────────────────────────────────────────────


def _build_retail_home(request) -> dict:
    """Returns the retail home feed.

    Sections favour discovery: featured products, trending by sales,
    newest arrivals, and the highest-rated retail stores.
    """
    base_products = (
        Product.objects
        .filter(status='active', category__business_category=_RETAIL)
        .select_related('vendor', 'category', 'brand')
        .prefetch_related('images')
    )

    featured = base_products.filter(is_featured=True).order_by('-updated_at')[:_FEATURED_LIMIT]
    trending = base_products.order_by('-sales_count', '-views_count')[:_TRENDING_LIMIT]
    newest = base_products.order_by('-created_at')[:_NEW_LIMIT]

    banners = _active_banners(_RETAIL)
    categories = (
        Category.objects.filter(
            business_category=_RETAIL, is_active=True, parent__isnull=True,
        )
        .order_by('-is_featured', 'name')[:_CATEGORY_LIMIT]
    )

    top_stores = (
        VendorProfile.objects.filter(business_category=_RETAIL)
        .annotate(product_count=Count(
            'products', filter=Q(products__status='active'),
        ))
        .filter(product_count__gt=0)
        .order_by('-average_rating', '-product_count')[:_VENDOR_LIMIT]
    )

    summary = _retail_summary()

    ctx = {'request': request}
    return {
        'mode':              _RETAIL,
        'banners':           BannerListSerializer(banners, many=True, context=ctx).data,
        'categories':        CategorySerializer(categories, many=True, context=ctx).data,
        'featured_products': ProductListSerializer(featured, many=True, context=ctx).data,
        'trending_products': ProductListSerializer(trending, many=True, context=ctx).data,
        'new_arrivals':      ProductListSerializer(newest, many=True, context=ctx).data,
        'top_vendors':       [_vendor_card(v, request) for v in top_stores],
        'summary':           summary,
    }


def _retail_summary() -> dict:
    qs = VendorProfile.objects.filter(business_category=_RETAIL)
    return {
        'total_vendors':  qs.count(),
        'total_products': Product.objects.filter(
            status='active', category__business_category=_RETAIL,
        ).count(),
        'avg_rating':     _avg_rating(qs),
    }


# ── Restaurant (food delivery) ───────────────────────────────────────────


def _build_restaurant_home(request) -> dict:
    """Returns the restaurant home feed.

    Sections lean into food-delivery muscle memory: a personalised
    `recommended_for_you` derived from the user's past orders, popular
    items, newest dishes on the menu, restaurant cards, and a
    delivery-aware summary (avg minutes, restaurant count, dish count).
    """
    base_products = (
        Product.objects
        .filter(status='active', category__business_category=_RESTAURANT)
        .select_related('vendor', 'category', 'brand')
        .prefetch_related('images')
    )

    popular = base_products.order_by('-sales_count', '-views_count')[:_TRENDING_LIMIT]
    featured = base_products.filter(is_featured=True).order_by('-updated_at')[:_FEATURED_LIMIT]
    newest = base_products.order_by('-created_at')[:_NEW_LIMIT]
    recommended = _recommended_dishes(request, base_products)

    banners = _active_banners(_RESTAURANT)
    food_categories = _restaurant_category_cards()

    top_restaurants = (
        VendorProfile.objects.filter(business_category=_RESTAURANT)
        .annotate(dish_count=Count(
            'products', filter=Q(products__status='active'),
        ))
        .filter(dish_count__gt=0)
        .order_by('-average_rating', '-dish_count')[:_VENDOR_LIMIT]
    )

    ctx = {'request': request}
    return {
        'mode':                 _RESTAURANT,
        'banners':              BannerListSerializer(banners, many=True, context=ctx).data,
        'food_categories':      food_categories,
        'recommended_for_you':  ProductListSerializer(recommended, many=True, context=ctx).data,
        'popular_items':        ProductListSerializer(popular, many=True, context=ctx).data,
        'featured_dishes':      ProductListSerializer(featured, many=True, context=ctx).data,
        'new_on_menu':          ProductListSerializer(newest, many=True, context=ctx).data,
        'top_restaurants':      [_vendor_card(v, request, dishes=True) for v in top_restaurants],
        'summary':              _restaurant_summary(),
    }


def _recommended_dishes(request, base_products):
    """Personalised dish list.

    Signal hierarchy:
      1. Dishes from categories the user has actually ordered before
         (last 30 orders, ranked by frequency).
      2. Fallback to top-sellers when there's no order history (cold
         start / anonymous).

    Excludes the user's most recent product so they're not just shown
    what they already ate yesterday — keeps the list feeling fresh.
    """
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return base_products.order_by('-sales_count')[:_TRENDING_LIMIT]

    try:
        from restaurant.models import RestaurantOrderItem
    except ImportError:
        return base_products.order_by('-sales_count')[:_TRENDING_LIMIT]

    recent_items = (
        RestaurantOrderItem.objects
        .filter(order__user=user)
        .select_related('product__category')
        .order_by('-id')[:30]
    )
    category_ids = []
    last_product_ids = set()
    for item in recent_items:
        if item.product_id:
            last_product_ids.add(item.product_id)
        if item.product and item.product.category_id:
            category_ids.append(item.product.category_id)

    if not category_ids:
        return base_products.order_by('-sales_count')[:_TRENDING_LIMIT]

    # Rank categories by how often the user ordered from each.
    counts = {}
    for cid in category_ids:
        counts[cid] = counts.get(cid, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    top_category_ids = [cid for cid, _ in ranked[:3]]

    recs = (
        base_products
        .filter(category_id__in=top_category_ids)
        .exclude(id__in=list(last_product_ids)[:5])  # mild novelty
        .order_by('-sales_count', '-updated_at')[:_TRENDING_LIMIT]
    )
    recs_list = list(recs)
    if len(recs_list) < _TRENDING_LIMIT:
        # Top-up with general top-sellers so the row never looks thin.
        filler = (
            base_products
            .exclude(id__in=[p.id for p in recs_list])
            .order_by('-sales_count')[: _TRENDING_LIMIT - len(recs_list)]
        )
        recs_list.extend(filler)
    return recs_list


def _restaurant_category_cards():
    """Cuisine row enriched with dish counts so the chip can show
    "47 dishes" underneath the name — the user immediately sees there's
    something to tap into."""
    cats = (
        Category.objects.filter(
            business_category=_RESTAURANT, is_active=True, parent__isnull=True,
        )
        .annotate(dish_count=Count(
            'products', filter=Q(products__status='active'),
        ))
        .order_by('-is_featured', '-dish_count', 'name')[:_CATEGORY_LIMIT]
    )
    return [
        {
            'id':         c.id,
            'name':       c.name,
            'image':      _abs_url(c.image) if getattr(c, 'image', None) else None,
            'dish_count': c.dish_count,
            'is_featured': c.is_featured,
        }
        for c in cats
    ]


def _abs_url(image_field):
    try:
        return image_field.url
    except (ValueError, AttributeError):
        return None


def _restaurant_summary() -> dict:
    qs = VendorProfile.objects.filter(business_category=_RESTAURANT)
    total_dishes = Product.objects.filter(
        status='active', category__business_category=_RESTAURANT,
    ).count()
    # Flat estimate until the delivery service is wired into the home
    # feed; matches the "≈ 30 min" copy you see on most food apps.
    avg_delivery_minutes = 30
    return {
        'total_restaurants':    qs.count(),
        'total_dishes':         total_dishes,
        'avg_rating':           _avg_rating(qs),
        'avg_delivery_minutes': avg_delivery_minutes,
    }


# ── Shared helpers ───────────────────────────────────────────────────────


def _active_banners(business_category: str) -> Iterable[Banner]:
    """Banners filtered to the relevant business category when the model
    carries that field, falling back to "any active" otherwise."""
    qs = Banner.objects.filter(is_active=True)
    field_names = {f.name for f in Banner._meta.get_fields()}
    if 'business_category' in field_names:
        qs = qs.filter(
            Q(business_category=business_category) | Q(business_category='')
        )
    return qs.order_by('-created_at')[:_BANNER_LIMIT]


def _vendor_card(vendor: VendorProfile, request, *, dishes: bool = False) -> dict:
    """Compact public vendor payload for the home grid.

    `dishes=True` renames the count to `dish_count` (restaurant idiom);
    otherwise it's `product_count` (retail idiom). Either way the value
    is whatever the queryset annotated.
    """
    display_name = vendor.trading_name or vendor.name or ''
    logo = None
    try:
        if vendor.logo:
            logo = request.build_absolute_uri(vendor.logo.url) if request else vendor.logo.url
    except (ValueError, AttributeError):
        logo = None
    count = getattr(vendor, 'dish_count' if dishes else 'product_count', 0)
    return {
        'id':              str(vendor.id),
        'name':            display_name,
        'logo':            logo,
        'average_rating':  str(vendor.average_rating or '0.00'),
        ('dish_count' if dishes else 'product_count'): count,
        'business_category': vendor.business_category,
    }


def _avg_rating(qs) -> str:
    value = qs.aggregate(avg=Avg('average_rating'))['avg']
    if value is None:
        return '0.00'
    return str(Decimal(value).quantize(Decimal('0.01')))
