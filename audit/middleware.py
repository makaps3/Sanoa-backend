"""
Audit middleware to automatically log all API requests and responses.
"""
import time
import logging
import threading

from django.utils.deprecation import MiddlewareMixin
from core.utils import get_client_ip

logger = logging.getLogger('sanoa.audit')

# Thread-local storage to make request info available to signals
_thread_locals = threading.local()


def get_current_request():
    """Get the current request from thread-local storage."""
    return getattr(_thread_locals, 'request', None)


def get_current_user():
    """Get the current user from the active request."""
    request = get_current_request()
    if request and hasattr(request, 'user') and request.user.is_authenticated:
        return request.user
    return None


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware that:
    1. Stores the current request in thread-local storage (for signals)
    2. Logs all API requests/responses to the AuditLog table
    """

    # Paths to skip (health checks, static files, docs)
    SKIP_PATHS = [
        '/static/',
        '/media/',
        '/api/schema/',
        '/api/docs/',
        '/api/redoc/',
        '/__debug__/',
        '/favicon.ico',
    ]

    # Only log mutating methods in detail; GET requests are high-volume
    ALWAYS_LOG_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']

    def process_request(self, request):
        # Store request in thread-local for signal handlers
        _thread_locals.request = request
        request._audit_start_time = time.time()
        return None

    def process_response(self, request, response):
        try:
            self._log_request(request, response)
        except Exception:
            logger.exception('Error writing audit log for request')
        finally:
            # Clean up thread-local
            _thread_locals.request = None
        return response

    def _should_skip(self, request):
        """Check if this request should be skipped."""
        path = request.path
        for skip in self.SKIP_PATHS:
            if path.startswith(skip):
                return True
        return False

    def _log_request(self, request, response):
        if self._should_skip(request):
            return

        # Only log mutating requests + failed GETs to keep volume manageable
        is_mutating = request.method in self.ALWAYS_LOG_METHODS
        is_error = response.status_code >= 400
        is_auth = request.path.startswith('/api/auth/')

        if not (is_mutating or is_error or is_auth):
            return

        # Import here to avoid circular imports at startup
        from audit.models import AuditLog

        duration_ms = None
        if hasattr(request, '_audit_start_time'):
            duration_ms = int((time.time() - request._audit_start_time) * 1000)

        user = None
        user_email = ''
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            user_email = request.user.email

        # Determine category from path
        category = self._categorize_path(request.path)

        # Determine action
        action = self._method_to_action(request.method)

        # Determine status
        if response.status_code < 300:
            status = 'success'
        elif response.status_code < 400:
            status = 'info'
        elif response.status_code < 500:
            status = 'warning'
        else:
            status = 'error'

        description = f"{request.method} {request.path} -> {response.status_code}"

        AuditLog.objects.create(
            user=user,
            user_email=user_email,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            category=category,
            action=action,
            status=status,
            description=description,
            request_method=request.method,
            request_path=request.path[:500],
            response_status_code=response.status_code,
            request_duration_ms=duration_ms,
        )

    def _categorize_path(self, path):
        """Map URL path to audit category."""
        mapping = {
            '/api/auth/': 'auth',
            '/api/accounts/': 'user',
            '/api/business/': 'vendor',
            '/api/products/': 'product',
            '/api/orders/': 'order',
            '/api/payments/': 'payment',
            '/api/inventory/': 'inventory',
            '/api/debit/': 'debit',
            '/api/subscriptions/': 'subscription',
            '/api/negotiations/': 'negotiation',
            '/api/otp/': 'otp',
            '/api/tiers/': 'tier',
            '/admin/': 'admin',
        }
        for prefix, category in mapping.items():
            if path.startswith(prefix):
                return category
        return 'api'

    def _method_to_action(self, method):
        """Map HTTP method to audit action."""
        return {
            'POST': 'create',
            'PUT': 'update',
            'PATCH': 'update',
            'DELETE': 'delete',
            'GET': 'read',
        }.get(method, 'api_request')
