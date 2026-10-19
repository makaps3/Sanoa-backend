"""
ML-powered recommendation engine for Sanoa.

Uses collaborative filtering and content-based filtering to recommend:
1. Stores/vendors based on user interest categories and proximity
2. Products based on user behaviour (views, purchases, wishlist, ratings)
"""
import math
import logging
from decimal import Decimal
from collections import defaultdict

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

from django.db.models import Q, Count, Avg, F, Value, FloatField
from django.db.models.functions import Coalesce

logger = logging.getLogger('sanoa')


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance in km between two GPS coordinates using the Haversine formula.
    """
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


class StoreDiscoveryEngine:
    """
    Discovers and ranks stores/vendors for a customer based on:
    - Category overlap with user interests
    - Distance from user location
    - Store ratings and performance
    """

    NEARBY_RADIUS_KM = 100

    def discover_stores(self, user, latitude=None, longitude=None, business_category=None):
        """
        Return stores split into 'nearby' and 'recommended' based on distance
        and matching the user's interest categories.

        If `business_category` is provided ('retail' or 'restaurant') the
        result is filtered to vendors operating in that storefront mode.
        This is what the frontend toggle uses to switch between the
        Shopping and Restaurants experiences.
        """
        from accounts.models import CustomerProfile
        from business.models import IndividualVendorProfile, BusinessVendorProfile

        # Get user interests
        profile = getattr(user, 'customer_profile', None)
        interest_ids = []
        if profile:
            interest_ids = list(profile.interest_categories.values_list('id', flat=True))
            if latitude is None and profile.latitude:
                latitude = profile.latitude
            if longitude is None and profile.longitude:
                longitude = profile.longitude

        # Gather all active, verified vendors. select_related the unified
        # VendorProfile so we can return its UUID (used by the storefront
        # detail endpoints) without an extra query per vendor.
        individual_vendors = IndividualVendorProfile.objects.filter(
            store_active=True, verification_status='verified'
        ).select_related('user__vendor_profile').prefetch_related('categories')

        business_vendors = BusinessVendorProfile.objects.filter(
            store_active=True, verification_status='verified'
        ).select_related('user__vendor_profile').prefetch_related('categories')

        if business_category:
            individual_vendors = individual_vendors.filter(business_category=business_category)
            business_vendors = business_vendors.filter(business_category=business_category)

        stores = []

        def _vendor_profile_uuid(v):
            """Unified VendorProfile UUID for this vendor — what the
            /api/products/restaurants|retail/<uuid>/ endpoints expect."""
            vp = getattr(getattr(v, 'user', None), 'vendor_profile', None)
            return str(vp.id) if vp is not None else None

        for vendor in individual_vendors:
            vendor_cat_ids = set(vendor.categories.values_list('id', flat=True))
            category_score = len(vendor_cat_ids & set(interest_ids)) if interest_ids else 0
            distance = None
            if latitude and longitude and vendor.latitude and vendor.longitude:
                distance = haversine_distance(latitude, longitude, vendor.latitude, vendor.longitude)

            stores.append({
                'vendor_type': 'individual',
                'business_category': vendor.business_category,
                'is_open_now': vendor.is_open_now,
                'id': vendor.pk,
                'vendor_uuid': _vendor_profile_uuid(vendor),
                'name': vendor.store_name,
                'description': vendor.store_description,
                'logo': vendor.store_logo.url if vendor.store_logo else None,
                'category': vendor.get_vendor_type_display(),
                'categories': list(vendor.categories.values_list('name', flat=True)),
                'average_rating': float(vendor.average_rating),
                'total_reviews': vendor.total_reviews,
                'total_sales': float(vendor.total_sales),
                'latitude': float(vendor.latitude) if vendor.latitude else None,
                'longitude': float(vendor.longitude) if vendor.longitude else None,
                'distance_km': round(distance, 2) if distance is not None else None,
                'category_match_score': category_score,
                'qr_code': vendor.qr_code.url if vendor.qr_code else None,
            })

        for vendor in business_vendors:
            vendor_cat_ids = set(vendor.categories.values_list('id', flat=True))
            category_score = len(vendor_cat_ids & set(interest_ids)) if interest_ids else 0
            distance = None
            if latitude and longitude and vendor.latitude and vendor.longitude:
                distance = haversine_distance(latitude, longitude, vendor.latitude, vendor.longitude)

            stores.append({
                'vendor_type': 'business',
                'business_category': vendor.business_category,
                'is_open_now': vendor.is_open_now,
                'id': vendor.pk,
                'vendor_uuid': _vendor_profile_uuid(vendor),
                'name': vendor.business_name,
                'description': vendor.business_description,
                'logo': vendor.business_logo.url if vendor.business_logo else None,
                'category': vendor.get_business_type_display(),
                'categories': list(vendor.categories.values_list('name', flat=True)),
                'average_rating': float(vendor.average_rating),
                'total_reviews': vendor.total_reviews,
                'total_sales': float(vendor.total_sales),
                'latitude': float(vendor.latitude) if vendor.latitude else None,
                'longitude': float(vendor.longitude) if vendor.longitude else None,
                'distance_km': round(distance, 2) if distance is not None else None,
                'category_match_score': category_score,
                'qr_code': vendor.qr_code.url if vendor.qr_code else None,
            })

        # Split into nearby and recommended
        nearby = []
        recommended = []

        for store in stores:
            if store['distance_km'] is not None and store['distance_km'] <= self.NEARBY_RADIUS_KM:
                nearby.append(store)
            else:
                recommended.append(store)

        # Sort nearby by distance first, then by category match score
        nearby.sort(key=lambda s: (s['distance_km'] or 999999, -s['category_match_score']))

        # Sort recommended by category match score, then rating, then distance
        recommended.sort(key=lambda s: (
            -s['category_match_score'],
            -s['average_rating'],
            s['distance_km'] if s['distance_km'] is not None else 999999,
        ))

        return {
            'nearby': nearby,
            'recommended': recommended,
        }


class ProductRecommendationEngine:
    """
    ML recommendation engine using:
    1. Content-based filtering (category, brand, price similarity)
    2. Collaborative filtering (user-product interaction matrix)

    Builds a user-item interaction matrix from:
    - Product views (weight: 1)
    - Wishlist adds (weight: 2)
    - Purchases (weight: 3)
    - Reviews/ratings (weight: actual rating)
    """

    VIEW_WEIGHT = 1.0
    WISHLIST_WEIGHT = 2.0
    PURCHASE_WEIGHT = 3.0

    def get_interaction_matrix(self):
        """Build a sparse user-product interaction matrix."""
        from django.contrib.auth import get_user_model
        from products.models import Product, Wishlist, ProductReview
        from orders.models import OrderItem

        User = get_user_model()
        users = User.objects.filter(is_active=True, user_type='customer')
        products = Product.objects.filter(status='active')

        if not users.exists() or not products.exists():
            return None, [], []

        user_list = list(users.values_list('id', flat=True))
        product_list = list(products.values_list('id', flat=True))
        user_idx = {uid: i for i, uid in enumerate(user_list)}
        product_idx = {pid: i for i, pid in enumerate(product_list)}

        matrix = np.zeros((len(user_list), len(product_list)), dtype=np.float32)

        # Wishlist interactions
        for wl in Wishlist.objects.filter(user_id__in=user_list, product_id__in=product_list):
            u = user_idx.get(wl.user_id)
            p = product_idx.get(wl.product_id)
            if u is not None and p is not None:
                matrix[u][p] += self.WISHLIST_WEIGHT

        # Purchase interactions
        for item in OrderItem.objects.filter(
            order__user_id__in=user_list, product_id__in=product_list
        ).values('order__user_id', 'product_id'):
            u = user_idx.get(item['order__user_id'])
            p = product_idx.get(item['product_id'])
            if u is not None and p is not None:
                matrix[u][p] += self.PURCHASE_WEIGHT

        # Review interactions
        for review in ProductReview.objects.filter(
            user_id__in=user_list, product_id__in=product_list, is_approved=True
        ).values('user_id', 'product_id', 'rating'):
            u = user_idx.get(review['user_id'])
            p = product_idx.get(review['product_id'])
            if u is not None and p is not None:
                matrix[u][p] += float(review['rating'])

        return matrix, user_list, product_list

    def get_content_features(self, product_list):
        """Build content feature vectors for products (category, brand, price)."""
        from products.models import Product

        products = Product.objects.filter(id__in=product_list).select_related('category', 'brand')
        product_map = {p.id: p for p in products}

        # Collect all category and brand IDs
        category_ids = sorted(set(p.category_id for p in products if p.category_id))
        brand_ids = sorted(set(p.brand_id for p in products if p.brand_id))
        cat_idx = {cid: i for i, cid in enumerate(category_ids)}
        brand_idx = {bid: i + len(category_ids) for i, bid in enumerate(brand_ids)}

        feature_dim = len(category_ids) + len(brand_ids) + 1  # +1 for normalized price
        feature_matrix = np.zeros((len(product_list), feature_dim), dtype=np.float32)

        prices = [float(product_map[pid].price) for pid in product_list if pid in product_map]
        max_price = max(prices) if prices else 1.0

        for i, pid in enumerate(product_list):
            product = product_map.get(pid)
            if not product:
                continue
            if product.category_id and product.category_id in cat_idx:
                feature_matrix[i][cat_idx[product.category_id]] = 1.0
            if product.brand_id and product.brand_id in brand_idx:
                feature_matrix[i][brand_idx[product.brand_id]] = 1.0
            feature_matrix[i][-1] = float(product.price) / max_price

        return feature_matrix

    def recommend_for_user(self, user, limit=20):
        """
        Generate product recommendations for a user using hybrid approach:
        collaborative filtering + content-based filtering.
        """
        from products.models import Product

        result = self.get_interaction_matrix()
        if result is None:
            # Fallback: return popular products
            return list(
                Product.objects.filter(status='active')
                .order_by('-sales_count', '-views_count')[:limit]
                .values_list('id', flat=True)
            )

        matrix, user_list, product_list = result
        user_idx = {uid: i for i, uid in enumerate(user_list)}

        u_idx = user_idx.get(user.id)
        if u_idx is None:
            # New user — use interest categories for content-based recs
            return self._recommend_by_interests(user, limit)

        # --- Collaborative filtering ---
        user_similarities = cosine_similarity(matrix[u_idx:u_idx + 1], matrix)[0]
        # Get top 20 similar users (excluding self)
        similar_indices = np.argsort(user_similarities)[::-1][1:21]

        collab_scores = np.zeros(len(product_list))
        for sim_idx in similar_indices:
            sim_score = user_similarities[sim_idx]
            if sim_score <= 0:
                continue
            collab_scores += sim_score * matrix[sim_idx]

        # Zero out products user already interacted with
        user_interactions = matrix[u_idx]
        collab_scores[user_interactions > 0] = 0

        # --- Content-based filtering ---
        content_features = self.get_content_features(product_list)
        # Get user's product feature preference (weighted average of interacted products)
        if user_interactions.sum() > 0:
            user_profile = (user_interactions.reshape(-1, 1) * content_features).sum(axis=0)
            user_profile = user_profile / user_interactions.sum()
            content_scores = cosine_similarity(
                user_profile.reshape(1, -1), content_features
            )[0]
            content_scores[user_interactions > 0] = 0
        else:
            content_scores = np.zeros(len(product_list))

        # --- Hybrid: combine scores ---
        # Normalize both score arrays to 0-1 range
        if collab_scores.max() > 0:
            collab_scores = collab_scores / collab_scores.max()
        if content_scores.max() > 0:
            content_scores = content_scores / content_scores.max()

        hybrid_scores = 0.6 * collab_scores + 0.4 * content_scores

        # Get top-N product IDs
        top_indices = np.argsort(hybrid_scores)[::-1][:limit]
        recommended_ids = [product_list[i] for i in top_indices if hybrid_scores[i] > 0]

        # If not enough recommendations, pad with popular products
        if len(recommended_ids) < limit:
            existing = set(recommended_ids)
            popular = Product.objects.filter(status='active').exclude(
                id__in=existing
            ).order_by('-sales_count', '-views_count')[:limit - len(recommended_ids)]
            recommended_ids.extend(popular.values_list('id', flat=True))

        return recommended_ids[:limit]

    def _recommend_by_interests(self, user, limit):
        """Recommend products based on user's interest categories (cold start)."""
        from products.models import Product

        profile = getattr(user, 'customer_profile', None)
        if not profile:
            return list(
                Product.objects.filter(status='active')
                .order_by('-sales_count', '-views_count')[:limit]
                .values_list('id', flat=True)
            )

        interest_ids = list(profile.interest_categories.values_list('id', flat=True))
        if not interest_ids:
            return list(
                Product.objects.filter(status='active')
                .order_by('-sales_count', '-views_count')[:limit]
                .values_list('id', flat=True)
            )

        return list(
            Product.objects.filter(
                status='active', category_id__in=interest_ids
            ).order_by('-sales_count', '-views_count')[:limit]
            .values_list('id', flat=True)
        )

    def get_similar_products(self, product_id, limit=10):
        """Find products similar to a given product using content features."""
        import uuid
        from products.models import Product

        # `product_id` arrives as a string from the URL, but Product.id is a
        # UUIDField so `values_list('id')` yields UUID objects — a string
        # never matches, which is why this used to always return []. Coerce.
        try:
            if not isinstance(product_id, uuid.UUID):
                product_id = uuid.UUID(str(product_id))
        except (ValueError, TypeError, AttributeError):
            return []

        products = list(
            Product.objects.filter(status='active').values_list('id', flat=True)
        )
        if product_id not in products:
            return []

        similar = []
        try:
            features = self.get_content_features(products)
            idx = products.index(product_id)
            similarities = cosine_similarity(features[idx:idx + 1], features)[0]
            similarities[idx] = 0  # exclude self
            top_indices = np.argsort(similarities)[::-1][:limit]
            similar = [products[i] for i in top_indices if similarities[i] > 0]
        except Exception:
            logger.exception('content-similarity failed for %s', product_id)

        # Fallback / top-up: same category + business_category, so the
        # endpoint never comes back empty for a real product.
        if len(similar) < limit:
            src = (
                Product.objects
                .filter(id=product_id)
                .values('category_id', 'category__business_category')
                .first()
            )
            if src:
                seen = set(similar) | {product_id}
                qs = Product.objects.filter(status='active')
                if src.get('category_id'):
                    qs = qs.filter(category_id=src['category_id'])
                elif src.get('category__business_category'):
                    qs = qs.filter(
                        category__business_category=src['category__business_category'])
                for pid in (qs.exclude(id__in=seen)
                            .order_by('-sales_count', '-views_count')
                            .values_list('id', flat=True)[:limit * 2]):
                    similar.append(pid)
                    seen.add(pid)
                    if len(similar) >= limit:
                        break

        return similar[:limit]

    def recommend_from_order_history(self, user, business_category=None, limit=12):
        """Recommend products based on what the customer USUALLY ORDERS.

        Looks at the products the user has actually ordered (retail via
        OrderItem, restaurant via RestaurantOrderItem), ranks the categories
        and vendors they buy from most, and surfaces OTHER active products in
        those categories/stores they haven't ordered — ordered by popularity.
        Scoped to the requested storefront (`retail` / `restaurant`). Falls
        back to popular products in that storefront for new / anonymous users
        so it never returns empty.
        """
        from products.models import Product

        bc = (business_category or '').lower()
        cats = [bc, 'both'] if bc in ('retail', 'restaurant') else None

        def _base():
            qs = Product.objects.filter(status='active')
            if cats:
                qs = qs.filter(category__business_category__in=cats)
            return qs

        popular_ids = lambda seen=frozenset(): list(  # noqa: E731
            _base().exclude(id__in=seen)
            .order_by('-sales_count', '-views_count')
            .values_list('id', flat=True)[:limit * 2]
        )

        if user is None or not getattr(user, 'is_authenticated', False):
            return popular_ids()[:limit]

        ordered_ids = self._ordered_product_ids(user, bc)
        if not ordered_ids:
            return popular_ids()[:limit]

        ordered_meta = list(
            Product.objects.filter(id__in=ordered_ids)
            .values_list('category_id', 'vendor_id')
        )
        cat_freq = defaultdict(int)
        vendor_ids = set()
        for cid, vid in ordered_meta:
            if cid:
                cat_freq[cid] += 1
            if vid:
                vendor_ids.add(vid)
        top_cats = [c for c, _ in sorted(
            cat_freq.items(), key=lambda kv: kv[1], reverse=True)]

        recs, seen = [], set(ordered_ids)

        def _pull(queryset):
            for pid in queryset.exclude(id__in=seen).order_by(
                    '-sales_count', '-views_count').values_list(
                    'id', flat=True)[:limit * 2]:
                if pid not in seen:
                    recs.append(pid)
                    seen.add(pid)
                if len(recs) >= limit:
                    return True
            return False

        # 1. Same categories the user orders from.
        if top_cats and _pull(_base().filter(category_id__in=top_cats)):
            return recs[:limit]
        # 2. Same vendors they buy from.
        if vendor_ids and _pull(_base().filter(vendor_id__in=vendor_ids)):
            return recs[:limit]
        # 3. Popular in this storefront.
        _pull(_base())
        return recs[:limit]

    def _ordered_product_ids(self, user, business_category):
        """UUIDs of products this user has ordered in the given storefront."""
        try:
            if business_category == 'restaurant':
                from restaurant.models import RestaurantOrderItem
                ids = RestaurantOrderItem.objects.filter(
                    order__user=user).values_list('product_id', flat=True)
            else:
                from orders.models import OrderItem
                ids = OrderItem.objects.filter(
                    order__user=user).values_list('product_id', flat=True)
            return {i for i in ids if i is not None}
        except Exception:
            logger.exception('order-history lookup failed')
            return set()
