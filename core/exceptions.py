"""
Custom exceptions for the Sanoa application
"""
from rest_framework import status
from rest_framework.exceptions import APIException


class SanoaAPIException(APIException):
    """Base exception class for Sanoa API"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An error occurred."
    default_code = "error"


class ProductNotAvailableException(SanoaAPIException):
    """Raised when product is not available for purchase"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Product is not available."
    default_code = "product_not_available"


class InsufficientStockException(SanoaAPIException):
    """Raised when product stock is insufficient"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Insufficient stock available."
    default_code = "insufficient_stock"


class InvalidPaymentException(SanoaAPIException):
    """Raised when payment is invalid"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Payment is invalid."
    default_code = "invalid_payment"


class OrderException(SanoaAPIException):
    """Raised when order operation fails"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Order operation failed."
    default_code = "order_error"


class UnauthorizedVendorException(SanoaAPIException):
    """Raised when vendor is not authorized to perform action"""
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You are not authorized to perform this action."
    default_code = "unauthorized_vendor"


class InvalidStatusTransitionException(SanoaAPIException):
    """Raised when status transition is invalid"""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid status transition."
    default_code = "invalid_status_transition"
