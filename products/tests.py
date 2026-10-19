"""
Tests for products app
"""
import pytest
from decimal import Decimal
from rest_framework import status
from products.models import Category, Brand, Product, ProductReview, Wishlist


# ── Model Tests ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCategoryModel:
    def test_create_category(self, category):
        assert category.name == 'Electronics'
        assert category.slug == 'electronics'
        assert str(category) == 'Electronics'

    def test_category_full_path(self, category):
        child = Category.objects.create(name='Phones', parent=category)
        assert child.get_full_path == 'Electronics > Phones'

    def test_auto_slug_generation(self):
        cat = Category.objects.create(name='Home & Garden')
        assert cat.slug == 'home-garden'


@pytest.mark.django_db
class TestBrandModel:
    def test_create_brand(self, brand):
        assert brand.name == 'TestBrand'
        assert brand.slug == 'testbrand'

    def test_auto_slug(self):
        b = Brand.objects.create(name='My Brand')
        assert b.slug == 'my-brand'


@pytest.mark.django_db
class TestProductModel:
    def test_create_product(self, product):
        assert product.name == 'Test Product'
        assert product.price == Decimal('99.99')
        assert product.sku.startswith('SKU-')

    def test_discount_percentage(self, product):
        expected = round(((Decimal('149.99') - Decimal('99.99')) / Decimal('149.99')) * 100, 2)
        assert product.discount_percentage == expected

    def test_is_on_sale(self, product):
        assert product.is_on_sale is True

    def test_not_on_sale_without_compare_price(self, vendor_user, category):
        p = Product.objects.create(
            name='No Sale', description='test',
            vendor=vendor_user.vendor_profile,
            category=category, price=Decimal('50.00'),
        )
        assert p.is_on_sale is False
        assert p.discount_percentage == 0

    def test_average_rating_no_reviews(self, product):
        assert product.average_rating == 0

    def test_average_rating_with_reviews(self, product, customer_user):
        ProductReview.objects.create(
            product=product, user=customer_user, rating=4, is_approved=True
        )
        assert product.average_rating == 4.0

    def test_review_count(self, product, customer_user):
        ProductReview.objects.create(
            product=product, user=customer_user, rating=5, is_approved=True
        )
        assert product.review_count == 1


# ── API Tests ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCategoryAPI:
    def test_list_categories_public(self, api_client, category):
        response = api_client.get('/api/products/categories/')
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_category_by_slug(self, api_client, category):
        response = api_client.get(f'/api/products/categories/{category.slug}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Electronics'

    def test_create_category_requires_auth(self, api_client):
        response = api_client.post('/api/products/categories/', {'name': 'New'}, format='json')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestProductAPI:
    def test_list_products_public(self, api_client, product):
        response = api_client.get('/api/products/products/')
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_product(self, api_client, product):
        response = api_client.get(f'/api/products/products/{product.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Test Product'

    def test_create_product_as_vendor(self, vendor_client, vendor_user, category, brand):
        vendor_user.is_verified = True
        vendor_user.save(update_fields=['is_verified'])
        profile = vendor_user.vendor_profile
        profile.verification_status = 'verified'
        profile.store_active = True
        profile.save()
        from products.models import VendorCategory
        VendorCategory.objects.create(vendor=profile, category=category)
        data = {
            'name': 'New Product',
            'description': 'Description',
            'category': category.id,
            'brand': brand.id,
            'price': '49.99',
            'status': 'active',
        }
        response = vendor_client.post('/api/products/products/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED, response.data

    def test_create_product_as_customer_forbidden(self, auth_client, category):
        data = {
            'name': 'Forbidden Product', 'description': 'test',
            'category': category.id, 'price': '10.00',
        }
        response = auth_client.post('/api/products/products/', data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_draft_products_hidden_from_public(self, api_client, vendor_user, category):
        Product.objects.create(
            name='Draft Product', description='draft',
            vendor=vendor_user.vendor_profile,
            category=category, price=Decimal('10.00'), status='draft',
        )
        response = api_client.get('/api/products/products/')
        names = [p['name'] for p in response.data['results']]
        assert 'Draft Product' not in names


@pytest.mark.django_db
class TestProductReviewAPI:
    def test_create_review(self, auth_client, product):
        data = {'product': str(product.id), 'rating': 5, 'comment': 'Great!'}
        response = auth_client.post('/api/products/reviews/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_reviews_public(self, api_client, product, customer_user):
        ProductReview.objects.create(
            product=product, user=customer_user, rating=4, is_approved=True
        )
        response = api_client.get(f'/api/products/reviews/?product={product.id}')
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestWishlistAPI:
    def test_add_to_wishlist(self, auth_client, product):
        data = {'product': str(product.id)}
        response = auth_client.post('/api/products/wishlist/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_wishlist(self, auth_client, product, customer_user):
        Wishlist.objects.create(user=customer_user, product=product)
        response = auth_client.get('/api/products/wishlist/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_wishlist_requires_auth(self, api_client):
        response = api_client.get('/api/products/wishlist/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
