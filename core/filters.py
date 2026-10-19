"""
Custom filter classes for the API
"""
from django_filters import rest_framework as filters
from products.models import Product
from orders.models import Order


class ProductFilter(filters.FilterSet):
    """Filter for Product model"""
    
    price_min = filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = filters.CharFilter(field_name='category__slug', lookup_expr='iexact')
    brand = filters.CharFilter(field_name='brand__slug', lookup_expr='iexact')
    
    class Meta:
        model = Product
        fields = ['status', 'is_featured', 'category', 'brand']


class OrderFilter(filters.FilterSet):
    """Filter for Order model"""
    
    created_date_from = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='gte'
    )
    created_date_to = filters.DateTimeFilter(
        field_name='created_at',
        lookup_expr='lte'
    )
    amount_min = filters.NumberFilter(field_name='total_amount', lookup_expr='gte')
    amount_max = filters.NumberFilter(field_name='total_amount', lookup_expr='lte')
    
    class Meta:
        model = Order
        fields = ['status', 'payment_status']
