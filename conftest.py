"""
Shared test fixtures for the Sanoa project
"""
import os
import pytest
from django.contrib.auth import get_user_model
from decimal import Decimal

os.environ.setdefault('ENVIRONMENT', 'testing')

User = get_user_model()


@pytest.fixture
def api_client():
    """Return an unauthenticated DRF test client"""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def customer_user(db):
    """Create a customer user"""
    user = User.objects.create_user(
        email='customer@test.com',
        username='customer1',
        password='testpass123',
        first_name='Test',
        last_name='Customer',
        user_type='customer',
    )
    return user


@pytest.fixture
def vendor_user(db):
    """Create a vendor user"""
    user = User.objects.create_user(
        email='vendor@test.com',
        username='vendor1',
        password='testpass123',
        first_name='Test',
        last_name='Vendor',
        user_type='vendor',
    )
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin/staff user"""
    user = User.objects.create_superuser(
        email='admin@test.com',
        username='admin1',
        password='testpass123',
        first_name='Test',
        last_name='Admin',
        user_type='admin',
    )
    return user


@pytest.fixture
def auth_client(api_client, customer_user):
    """Return an authenticated DRF test client (as customer)"""
    api_client.force_authenticate(user=customer_user)
    return api_client


@pytest.fixture
def vendor_client(api_client, vendor_user):
    """Return an authenticated DRF test client (as vendor)"""
    api_client.force_authenticate(user=vendor_user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """Return an authenticated DRF test client (as admin)"""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def category(db):
    """Create a test category"""
    from products.models import Category
    return Category.objects.create(
        name='Electronics',
        description='Electronic devices',
    )


@pytest.fixture
def brand(db):
    """Create a test brand"""
    from products.models import Brand
    return Brand.objects.create(
        name='TestBrand',
        description='A test brand',
    )


@pytest.fixture
def product(db, vendor_user, category, brand):
    """Create a test product"""
    from products.models import Product
    from business.models import VendorProfile
    # The post_save signal on User auto-creates a unified VendorProfile
    # for vendor users, so we just look it up here.
    vendor_profile, _ = VendorProfile.objects.get_or_create(
        user=vendor_user,
        defaults={'profile_type': 'individual', 'name': 'Test Vendor'},
    )
    return Product.objects.create(
        name='Test Product',
        description='A test product description',
        vendor=vendor_profile,
        category=category,
        brand=brand,
        price=Decimal('99.99'),
        compare_at_price=Decimal('149.99'),
        status='active',
    )


@pytest.fixture
def order(db, customer_user):
    """Create a test order"""
    from orders.models import Order
    return Order.objects.create(
        user=customer_user,
        customer_email=customer_user.email,
        customer_phone='+1234567890',
        billing_full_name='Test Customer',
        billing_street_address='123 Test St',
        billing_city='Test City',
        billing_state_province='TS',
        billing_postal_code='12345',
        billing_country='US',
        shipping_full_name='Test Customer',
        shipping_street_address='123 Test St',
        shipping_city='Test City',
        shipping_state_province='TS',
        shipping_postal_code='12345',
        shipping_country='US',
        subtotal=Decimal('99.99'),
        total_amount=Decimal('99.99'),
    )


@pytest.fixture
def warehouse(db):
    """Create a test warehouse"""
    from inventory.models import Warehouse
    return Warehouse.objects.create(
        name='Main Warehouse',
        code='WH-001',
        street_address='456 Warehouse St',
        city='Warehouse City',
        state_province='WS',
        postal_code='67890',
        country='US',
        is_default=True,
    )
