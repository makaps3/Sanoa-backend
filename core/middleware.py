"""
Custom middleware for logging and error handling
"""
import logging
import json
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from core.utils import get_client_ip

logger = logging.getLogger('sanoa.middleware')


class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware to log all API requests"""
    
    def process_request(self, request):
        request.client_ip = get_client_ip(request)
        request.request_start_time = __import__('time').time()
        
        # Log the request
        logger.info(
            f"[{request.client_ip}] {request.method} {request.path}",
            extra={
                'ip': request.client_ip,
                'method': request.method,
                'path': request.path,
                'user': request.user.email if request.user.is_authenticated else 'anonymous'
            }
        )
        return None
    
    def process_response(self, request, response):
        # Log response time
        if hasattr(request, 'request_start_time'):
            duration = __import__('time').time() - request.request_start_time
            logger.info(
                f"[{request.client_ip}] {request.method} {request.path} - {response.status_code} ({duration:.2f}s)",
                extra={
                    'ip': request.client_ip,
                    'method': request.method,
                    'path': request.path,
                    'status': response.status_code,
                    'duration': duration
                }
            )
        return response


class APIExceptionMiddleware(MiddlewareMixin):
    """Middleware to handle API exceptions gracefully"""
    
    def process_exception(self, request, exception):
        # Log the exception
        logger.error(
            f"Exception in {request.method} {request.path}: {str(exception)}",
            exc_info=True,
            extra={
                'ip': getattr(request, 'client_ip', get_client_ip(request)),
                'method': request.method,
                'path': request.path,
                'exception': str(exception)
            }
        )
        
        # Don't handle exceptions here - let DRF handle them
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Middleware to add security headers"""
    
    def process_response(self, request, response):
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Don't expose server information
        if 'Server' in response:
            del response['Server']
        
        return response


class SuspendedUserMiddleware(MiddlewareMixin):
    """
    Block suspended users from accessing the platform.

    Suspended users (overdue credit payments) are blocked from ALL endpoints
    EXCEPT:
    - Payment / repayment endpoints (so they can pay off their debt)
    - Authentication endpoints (login, token refresh)
    - The debit/credit account & repayment endpoints
    - Admin panel
    """

    # URL prefixes that suspended users ARE allowed to access
    ALLOWED_PREFIXES = (
        '/api/payments/',
        '/api/debit/',
        '/api/auth/',
        '/api/accounts/login',
        '/api/accounts/token',
        '/admin/',
    )

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        if not getattr(request.user, 'is_suspended', False):
            return None

        # Admin/staff bypass
        if request.user.is_staff or request.user.is_superuser:
            return None

        # Check if the path is allowed for suspended users
        for prefix in self.ALLOWED_PREFIXES:
            if request.path.startswith(prefix):
                return None

        return JsonResponse(
            {
                'error': 'account_suspended',
                'message': (
                    'Your account has been suspended due to an overdue credit payment. '
                    'Please settle your outstanding balance to regain access.'
                ),
                'suspension_reason': request.user.suspension_reason or 'Overdue credit payment',
            },
            status=403,
        )


class NoCacheMiddleware(MiddlewareMixin):
    """Middleware to prevent caching of dynamic content"""

    def process_response(self, request, response):
        # Don't cache API responses
        if request.path.startswith('/api/'):
            if 'no-store' not in response.get('Cache-Control', ''):
                response['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response
