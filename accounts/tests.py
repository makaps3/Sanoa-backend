"""
Tests for accounts app
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

User = get_user_model()


# ── Model Tests ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestUserModel:
    def test_create_customer(self, customer_user):
        assert customer_user.email == 'customer@test.com'
        assert customer_user.user_type == 'customer'
        assert str(customer_user) == 'customer@test.com (customer)'

    def test_create_vendor(self, vendor_user):
        assert vendor_user.user_type == 'vendor'

    def test_create_admin(self, admin_user):
        assert admin_user.is_staff
        assert admin_user.is_superuser

    def test_email_is_username_field(self):
        assert User.USERNAME_FIELD == 'email'

    def test_signal_creates_customer_profile(self, customer_user):
        assert hasattr(customer_user, 'customer_profile')
        assert customer_user.customer_profile is not None

    def test_signal_creates_vendor_profile(self, vendor_user):
        assert hasattr(vendor_user, 'vendor_profile')
        assert vendor_user.vendor_profile is not None


@pytest.mark.django_db
class TestShippingAddressModel:
    def test_create_address(self, customer_user):
        from orders.models import ShippingAddress
        address = ShippingAddress.objects.create(
            user=customer_user,
            address_type='shipping',
            full_name='Test User',
            phone_number='+1234567890',
            street_address='123 Main St',
            city='New York',
            state_province='NY',
            postal_code='10001',
            country='US',
            is_default=True,
        )
        assert str(address) == 'Test User - New York, NY'
        assert address.is_default

    def test_only_one_default_address(self, customer_user):
        from orders.models import ShippingAddress
        addr1 = ShippingAddress.objects.create(
            user=customer_user, address_type='shipping',
            full_name='Addr 1', phone_number='+1', street_address='1 St',
            city='City', state_province='ST', postal_code='111', country='US',
            is_default=True,
        )
        addr2 = ShippingAddress.objects.create(
            user=customer_user, address_type='shipping',
            full_name='Addr 2', phone_number='+2', street_address='2 St',
            city='City', state_province='ST', postal_code='222', country='US',
            is_default=True,
        )
        addr1.refresh_from_db()
        assert not addr1.is_default
        assert addr2.is_default


# ── API Tests ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestUserRegistration:
    def test_register_customer(self, api_client):
        data = {
            'email': 'new@test.com',
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'strongpass123',
            'password_confirm': 'strongpass123',
            'user_type': 'customer',
        }
        response = api_client.post('/api/accounts/register/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(email='new@test.com').exists()

    def test_register_mismatched_passwords(self, api_client):
        data = {
            'email': 'new2@test.com',
            'username': 'newuser2',
            'password': 'strongpass123',
            'password_confirm': 'differentpass',
            'user_type': 'customer',
        }
        response = api_client.post('/api/accounts/register/', data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_duplicate_email(self, api_client, customer_user):
        data = {
            'email': customer_user.email,
            'username': 'duplicate',
            'password': 'strongpass123',
            'password_confirm': 'strongpass123',
            'user_type': 'customer',
        }
        response = api_client.post('/api/accounts/register/', data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestUserProfile:
    def test_get_own_profile(self, auth_client, customer_user):
        response = auth_client.get('/api/accounts/me/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == customer_user.email

    def test_unauthenticated_cannot_access_profile(self, api_client):
        response = api_client.get('/api/accounts/me/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_update_profile(self, auth_client):
        response = auth_client.patch(
            '/api/accounts/me/',
            {'first_name': 'Updated'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['first_name'] == 'Updated'


@pytest.mark.django_db
class TestShippingAddressAPI:
    def test_create_address(self, auth_client):
        data = {
            'address_type': 'shipping',
            'full_name': 'Test User',
            'phone_number': '+1234567890',
            'street_address': '123 API St',
            'city': 'Test City',
            'state_province': 'TS',
            'postal_code': '12345',
            'country': 'US',
        }
        response = auth_client.post('/api/orders/shipping-addresses/', data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_list_own_addresses(self, auth_client, customer_user):
        from orders.models import ShippingAddress
        ShippingAddress.objects.create(
            user=customer_user, address_type='shipping', full_name='Test',
            phone_number='+1', street_address='1 St', city='City',
            state_province='ST', postal_code='111', country='US',
        )
        response = auth_client.get('/api/orders/shipping-addresses/')
        assert response.status_code == status.HTTP_200_OK
        # ShippingAddressViewSet has no pagination → returns a list directly.
        results = response.data
        if isinstance(results, dict):
            results = results.get('results', results)
        assert len(results) == 1


@pytest.mark.django_db
class TestAdminUserManagement:
    def test_admin_can_list_users(self, admin_client):
        response = admin_client.get('/api/accounts/users/')
        assert response.status_code == status.HTTP_200_OK

    def test_customer_cannot_list_users(self, auth_client):
        response = auth_client.get('/api/accounts/users/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
