"""
Utility functions used across the application
"""
from django.utils.text import slugify as django_slugify
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
import uuid


def generate_slug(text):
    """Generate a URL-friendly slug from text"""
    return django_slugify(text)


def generate_sku(prefix='SKU', length=8):
    """Generate a unique SKU"""
    return f"{prefix}-{uuid.uuid4().hex[:length].upper()}"


def resize_image(image_path, max_width, max_height):
    """
    Resize an image to specified dimensions
    
    Args:
        image_path: Path to image file
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
    """
    try:
        img = Image.open(image_path)
        if img.height > max_height or img.width > max_width:
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            img.save(image_path, quality=85, optimize=True)
    except Exception as e:
        print(f"Error resizing image: {e}")


def compress_image(image_field, max_width, max_height, quality=85):
    """
    Compress and resize an image file
    
    Args:
        image_field: Django ImageField instance
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        quality: JPEG quality (1-95)
    
    Returns:
        Processed image file
    """
    if not image_field:
        return None
    
    try:
        img = Image.open(image_field)
        
        # Convert RGBA to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Resize
        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        
        # Save to BytesIO
        thumb_io = BytesIO()
        img.save(thumb_io, format='JPEG', quality=quality, optimize=True)
        thumb_io.seek(0)
        
        # Create new contentfile
        return ContentFile(thumb_io.read(), name=image_field.name)
    except Exception as e:
        print(f"Error compressing image: {e}")
        return image_field


def calculate_discount_percentage(original_price, sale_price):
    """Calculate discount percentage"""
    if not original_price or original_price == 0:
        return 0
    return round(((original_price - sale_price) / original_price) * 100, 2)


def calculate_tax(amount, tax_rate):
    """Calculate tax amount"""
    return round(amount * (tax_rate / 100), 2)


def format_currency(amount, currency_symbol='R'):
    """Format amount as South African Rand (ZAR)"""
    return f"{currency_symbol}{amount:,.2f}"


def get_client_ip(request):
    """
    Get client IP address from request
    Handles X-Forwarded-For header for proxies
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def paginate_queryset(queryset, page, page_size):
    """
    Paginate a queryset
    
    Args:
        queryset: Django QuerySet
        page: Page number (1-indexed)
        page_size: Number of items per page
    
    Returns:
        Tuple of (items, total_count, total_pages)
    """
    total_count = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    
    items = queryset[start:end]
    total_pages = (total_count + page_size - 1) // page_size
    
    return items, total_count, total_pages
