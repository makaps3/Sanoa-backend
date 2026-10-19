"""
Tests for orders app
"""
import pytest
from decimal import Decimal
from rest_framework import status
from django.utils import timezone
from orders.models import ShoppingCart, CartItem, Order, OrderStatusHistory, Coupon


# ── Model Tests ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestOrderModel:
    def test_create_order(self, order):
        assert order.order_number.startswith('ORD-')
        assert order.status == 'pending'
        assert str(order) == f'Order {order.order_number}'

    def test_order_auto_number(self, customer_user):
        o1 = Order.objects.create(
            user=customer_user, customer_email='a@b.com',
            billing_full_name='T', billing_street_address='1',
            billing_city='C', billing_state_province='S',
            billing_postal_code='1', billing_country='US',
            shipping_full_name='T', shipping_street_address='1',
            shipping_city='C', shipping_state_province='S',
            shipping_postal_code='1', shipping_country='US',
        )
        o2 = Order.objects.create(
            user=customer_user, customer_email='a@b.com',
            billing_full_name='T', billing_street_address='1',
            billing_city='C', billing_state_province='S',
            billing_postal_code='1', billing_country='US',
            shipping_full_name='T', shipping_street_address='1',
            shipping_city='C', shipping_state_province='S',
            shipping_postal_code='1', shipping_country='US',
        )
        assert o1.order_number != o2.order_number

    def test_can_be_cancelled_pending(self, order):
        assert order.can_be_cancelled is True

    def test_cannot_cancel_shipped(self, order):
        order.status = 'shipped'
        order.save()
        assert order.can_be_cancelled is False

    def test_is_paid(self, order):
        assert order.is_paid is False
        order.payment_status = 'paid'
        assert order.is_paid is True


@pytest.mark.django_db
class TestCartModel:
    def test_cart_total_items(self, customer_user, vendor_user, product):
        cart = ShoppingCart.objects.create(user=customer_user, vendor=vendor_user.vendor_profile)
        CartItem.objects.create(cart=cart, product=product, quantity=3)
        assert cart.total_items == 3

    def test_cart_total_amount(self, customer_user, vendor_user, product):
        cart = ShoppingCart.objects.create(user=customer_user, vendor=vendor_user.vendor_profile)
        CartItem.objects.create(cart=cart, product=product, quantity=2)
        assert cart.total_amount == Decimal('199.98')

    def test_cart_clear(self, customer_user, vendor_user, product):
        cart = ShoppingCart.objects.create(user=customer_user, vendor=vendor_user.vendor_profile)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        cart.clear()
        assert cart.items.count() == 0


@pytest.mark.django_db
class TestCouponModel:
    def test_coupon_valid(self):
        coupon = Coupon.objects.create(
            code='TEST20', name='Test Coupon', coupon_type='percentage',
            value=Decimal('20.00'), start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
        )
        is_valid, msg = coupon.is_valid()
        assert is_valid is True

    def test_coupon_expired(self):
        coupon = Coupon.objects.create(
            code='EXPIRED', name='Expired', coupon_type='percentage',
            value=Decimal('10.00'),
            start_date=timezone.now() - timezone.timedelta(days=60),
            end_date=timezone.now() - timezone.timedelta(days=30),
        )
        is_valid, msg = coupon.is_valid()
        assert is_valid is False

    def test_coupon_calculate_discount_percentage(self):
        coupon = Coupon.objects.create(
            code='PCT10', name='10%', coupon_type='percentage',
            value=Decimal('10.00'), start_date=timezone.now(),
        )
        discount = coupon.calculate_discount(Decimal('100.00'))
        assert discount == Decimal('10.00')

    def test_coupon_calculate_discount_fixed(self):
        coupon = Coupon.objects.create(
            code='FIXED5', name='R5 off', coupon_type='fixed_amount',
            value=Decimal('5.00'), start_date=timezone.now(),
        )
        discount = coupon.calculate_discount(Decimal('100.00'))
        assert discount == Decimal('5.00')


# ── API Tests ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestShoppingCartAPI:
    def test_get_my_carts(self, auth_client):
        response = auth_client.get('/api/orders/cart/my-carts/')
        assert response.status_code == status.HTTP_200_OK

    def test_add_item_to_cart(self, auth_client, product):
        data = {'product': str(product.id), 'quantity': 2}
        response = auth_client.post('/api/orders/cart/add-item/', data, format='json')
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

    def test_clear_cart(self, auth_client, customer_user, vendor_user, product):
        cart = ShoppingCart.objects.create(user=customer_user, vendor=vendor_user.vendor_profile)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        response = auth_client.post(f'/api/orders/cart/{cart.id}/clear/')
        assert response.status_code == status.HTTP_200_OK

    def test_cart_requires_auth(self, api_client):
        response = api_client.get('/api/orders/cart/my-carts/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
class TestOrderAPI:
    def test_list_own_orders(self, auth_client, order):
        response = auth_client.get('/api/orders/orders/')
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_order(self, auth_client, order):
        response = auth_client.get(f'/api/orders/orders/{order.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['order_number'] == order.order_number

    def test_cancel_order(self, auth_client, order):
        response = auth_client.post(f'/api/orders/orders/{order.id}/cancel/')
        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.status == 'cancelled'

    def test_cancel_shipped_order_fails(self, auth_client, order):
        order.status = 'shipped'
        order.save()
        response = auth_client.post(f'/api/orders/orders/{order.id}/cancel/')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_admin_update_status(self, admin_client, order):
        response = admin_client.post(
            f'/api/orders/orders/{order.id}/update_status/',
            {'status': 'processing', 'comment': 'Processing now'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        order.refresh_from_db()
        assert order.status == 'processing'
        assert OrderStatusHistory.objects.filter(order=order, new_status='processing').exists()


@pytest.mark.django_db
class TestCouponAPI:
    def test_validate_valid_coupon(self, auth_client):
        Coupon.objects.create(
            code='SAVE10', name='Save 10%', coupon_type='percentage',
            value=Decimal('10.00'), start_date=timezone.now(),
        )
        response = auth_client.post(
            '/api/orders/coupons/validate/',
            {'code': 'SAVE10', 'order_amount': '100.00'},
            format='json'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['valid'] is True

    def test_validate_invalid_coupon(self, auth_client):
        response = auth_client.post(
            '/api/orders/coupons/validate/',
            {'code': 'NONEXISTENT'},
            format='json'
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
