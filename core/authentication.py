"""
Custom API token authentication backend.
Authenticates requests using the 'X-API-Token' header or 'Authorization: Token <key>' header.
"""
from rest_framework import authentication, exceptions
import ipaddress
import re

from rest_framework.permissions import SAFE_METHODS

from accounts.models import APIToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from .verification_access import enforce_verification


class VerifiedJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            enforce_verification(result[0], request)
        return result


class VerifiedSessionAuthentication(authentication.SessionAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            enforce_verification(result[0], request)
        return result


class APITokenAuthentication(authentication.BaseAuthentication):
    """
    Token-based authentication using the APIToken model.
    Clients include the token in the request header:
        X-API-Token: snoa_abc123...
    or:
        Authorization: Token snoa_abc123...
    """

    keyword = 'Token'
    header_name = 'HTTP_X_API_TOKEN'

    def authenticate(self, request):
        raw_token = self._get_token_from_request(request)
        if raw_token is None:
            return None  # Let other auth backends handle it

        token_hash = APIToken.hash_token(raw_token)

        try:
            token = APIToken.objects.select_related('user').get(token_hash=token_hash)
        except APIToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid API token.')

        if not token.is_active:
            raise exceptions.AuthenticationFailed('Token has been revoked.')

        if token.is_expired:
            raise exceptions.AuthenticationFailed('Token has expired.')

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('User account is inactive.')

        enforce_verification(token.user, request)
        self._enforce_scope(token, request)

        # Record usage
        ip = self._get_client_ip(request)
        token.record_usage(ip_address=ip)

        # Attach token and scope to request for permission checks
        request.auth_token = token
        request.token_scope = token.scope

        return (token.user, token)

    def authenticate_header(self, request):
        return self.keyword

    def _get_token_from_request(self, request):
        # Check X-API-Token header first
        token = request.META.get(self.header_name)
        if token is None:
            # Compare the scheme as bytes: malformed input must never raise a
            # UnicodeDecodeError and turn authentication into a server error.
            parts = authentication.get_authorization_header(request).split()
            if not parts or parts[0].lower() != self.keyword.lower().encode('ascii'):
                return None
            if len(parts) != 2:
                raise exceptions.AuthenticationFailed('Invalid API token header.')
            try:
                token = parts[1].decode('ascii')
            except UnicodeDecodeError:
                raise exceptions.AuthenticationFailed('Invalid API token header.')
        if not isinstance(token, str) or not re.fullmatch(r'snoa_[0-9a-f]{64}', token):
            raise exceptions.AuthenticationFailed('Invalid API token.')
        return token

    def _enforce_scope(self, token, request):
        if token.scope == 'full':
            return
        if token.scope == 'read' and request.method in SAFE_METHODS:
            return
        # Use the resolved view's owning app, not a client-controlled URL or
        # header. Feature tokens cannot mint credentials or edit account roles.
        view = (request.parser_context or {}).get('view')
        app = type(view).__module__.split('.')[0]
        if token.scope in {'products', 'orders', 'inventory'} and app == token.scope:
            return
        raise exceptions.PermissionDenied('This API token does not allow this operation.')

    def _get_client_ip(self, request):
        # Forwarded headers are untrusted unless normalized by infrastructure.
        # Keep the connection peer for audit instead of accepting spoofed input.
        try:
            return str(ipaddress.ip_address(request.META.get('REMOTE_ADDR')))
        except (ValueError, TypeError):
            return None
