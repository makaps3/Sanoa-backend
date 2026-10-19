"""
JWT WebSocket authentication middleware.

Django Channels' built-in AuthMiddlewareStack only understands session
cookies.  Flutter (and other mobile clients) authenticate via JWT Bearer
tokens, not cookies, so WebSocket connections are rejected as anonymous
by the default stack.

This middleware:
  1. Reads the token from the `Authorization: Bearer <token>` header
     (if the WebSocket client can set HTTP headers — some can).
  2. Falls back to the `?token=<token>` query-string parameter (the
     recommended approach for Flutter/mobile since browser-style headers
     are not always settable during the WS handshake).
  3. Validates the token with `rest_framework_simplejwt`.
  4. Sets `scope['user']` to the authenticated User, or AnonymousUser
     when the token is missing/invalid/expired.

Usage in asgi.py:
    from core.ws_auth import JWTAuthMiddlewareStack
    websocket_app = JWTAuthMiddlewareStack(URLRouter([...]))
"""
from urllib.parse import parse_qs
from types import SimpleNamespace

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticate WebSocket connections using JWT Bearer tokens."""

    async def __call__(self, scope, receive, send):
        scope['user'] = await self._authenticate(scope)
        if not await self._has_access(scope['user']):
            await send({'type': 'websocket.close', 'code': 4403})
            return
        closed = False

        async def allowed():
            nonlocal closed
            if closed:
                return False
            if not await self._has_access(scope['user']):
                closed = True
                await send({'type': 'websocket.close', 'code': 4403})
                return False
            return True

        async def checked_receive():
            message = await receive()
            if message['type'] == 'websocket.receive' and not await allowed():
                return {'type': 'websocket.disconnect', 'code': 4403}
            return message

        async def checked_send(message):
            if message['type'] in ('websocket.accept', 'websocket.send') and not await allowed():
                return
            await send(message)

        return await super().__call__(scope, checked_receive, checked_send)

    @database_sync_to_async
    def _has_access(self, user):
        from django.contrib.auth import get_user_model
        from rest_framework.exceptions import PermissionDenied
        from core.verification_access import enforce_verification
        if not user.is_authenticated:
            return False
        current = get_user_model().objects.filter(pk=user.pk).first()
        if current is None:
            return False
        try:
            enforce_verification(current, SimpleNamespace(parser_context={}, method='POST'))
        except PermissionDenied:
            return False
        return True

    # ── Internal ────────────────────────────────────────────────────

    def _extract_token(self, scope) -> str | None:
        """
        Try Authorization header first, then ?token= query param.
        Returns the raw token string, or None.
        """
        # 1. Authorization: Bearer <token>
        headers = dict(scope.get('headers', []))
        auth = headers.get(b'authorization', b'').decode('utf-8', errors='replace')
        if auth.lower().startswith('bearer '):
            return auth[7:].strip()

        # 2. ?token=<token>
        qs = scope.get('query_string', b'').decode('utf-8', errors='replace')
        params = parse_qs(qs)
        tokens = params.get('token', [])
        if tokens:
            return tokens[0].strip()

        return None

    @database_sync_to_async
    def _authenticate(self, scope):
        """Validate the token and return the User (or AnonymousUser)."""
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()

        raw_token = self._extract_token(scope)
        if not raw_token:
            return AnonymousUser()

        try:
            token = AccessToken(raw_token)
            user_id = token.get('user_id')
            if user_id is None:
                return AnonymousUser()
            return User.objects.select_related().get(pk=user_id)
        except (TokenError, InvalidToken, User.DoesNotExist, Exception):
            return AnonymousUser()


def JWTAuthMiddlewareStack(inner):
    """
    Convenience wrapper — drop-in replacement for AuthMiddlewareStack.

    Usage:
        websocket_app = JWTAuthMiddlewareStack(URLRouter([...]))
    """
    return JWTAuthMiddleware(inner)
