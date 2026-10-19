"""
Custom validators for models and serializers
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_positive_price(value):
    """Validate that price is positive"""
    if value <= 0:
        raise ValidationError(
            _('Price must be greater than 0.'),
            code='invalid_price'
        )


def validate_discount_price(compare_at_price, sale_price):
    """Validate that sale price is less than compare price"""
    if compare_at_price and sale_price:
        if sale_price >= compare_at_price:
            raise ValidationError(
                _('Sale price must be less than compare price.'),
                code='invalid_discount'
            )


def validate_rating(value):
    """Validate that rating is between 1 and 5"""
    if not 1 <= value <= 5:
        raise ValidationError(
            _('Rating must be between 1 and 5.'),
            code='invalid_rating'
        )


def validate_percentage(value):
    """Validate that value is between 0 and 100"""
    if not 0 <= value <= 100:
        raise ValidationError(
            _('Percentage must be between 0 and 100.'),
            code='invalid_percentage'
        )


def validate_quantity(value):
    """Validate that quantity is positive"""
    if value < 1:
        raise ValidationError(
            _('Quantity must be at least 1.'),
            code='invalid_quantity'
        )
