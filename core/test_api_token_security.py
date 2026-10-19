"""Exercise token boundaries through DRF authentication and the real API."""
from datetime import timedelta

import pytest
from django.urls import path
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import APIToken, User
from accounts.views import APITokenViewSet
from core.authentication import APITokenAuthentication

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return User.objects.create_user(
        username='token-owner', email='tokens@example.com',
        user_type='customer', is_verified=True,
    )


def jwt_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return client


def issue(user, scope='full', **kwargs):
    raw, hashed, prefix = APIToken.generate_token()
    token = APIToken.objects.create(
        user=user, name='Integration', token_hash=hashed, prefix=prefix, scope=scope, **kwargs,
    )
    client = APIClient()
    client.credentials(HTTP_X_API_TOKEN=raw)
    return token, raw, client


def test_secret_is_returned_once_and_never_persisted(owner):
    client = jwt_client(owner)
    created = client.post('/api/accounts/tokens/', {'name': 'Warehouse'}, format='json')
    assert created.status_code == 201
    raw = created.data['token']
    token = APIToken.objects.get(pk=created.data['id'])
    assert token.token_hash == APIToken.hash_token(raw)
    assert 'token' not in {field.name for field in APIToken._meta.fields}
    assert created['Cache-Control'] == 'no-store'
    assert 'token' not in client.get(f'/api/accounts/tokens/{token.pk}/').data
    assert raw.encode() not in client.get('/api/accounts/tokens/').content
    client.credentials(HTTP_AUTHORIZATION=f'Token {raw}')
    assert client.get('/api/accounts/me/').status_code == 200


def test_read_token_cannot_write_or_mint_credentials(owner):
    token, raw, client = issue(owner, 'read')
    assert client.get('/api/accounts/me/').status_code == 200
    assert client.patch('/api/accounts/me/', {'first_name': 'Changed'}, format='json').status_code == 403
    assert client.post('/api/accounts/tokens/', {'name': 'Escalation', 'scope': 'full'}, format='json').status_code == 403
    assert client.post(f'/api/accounts/tokens/{token.pk}/revoke/').status_code == 403
    owner.refresh_from_db()
    assert owner.first_name == ''
    assert APIToken.objects.filter(user=owner).count() == 1


class ProbeSerializer(serializers.Serializer):
    ok = serializers.BooleanField()


class FeatureProbe(GenericAPIView):
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ProbeSerializer

    def post(self, request):
        return Response({'ok': True})


@pytest.mark.parametrize('scope', ['products', 'orders', 'inventory'])
def test_feature_scope_allows_only_its_resolved_app(owner, scope):
    _, raw, client = issue(owner, scope)
    factory = APIRequestFactory()
    for app in ['products', 'orders', 'inventory', 'accounts', 'platform_admin']:
        view = type('Probe', (FeatureProbe,), {'__module__': f'{app}.views'})
        # URL deliberately claims the permitted scope even for other views.
        result = view.as_view()(factory.post(f'/api/{scope}/', HTTP_X_API_TOKEN=raw))
        assert result.status_code == (200 if app == scope else 403)
    assert client.post('/api/accounts/tokens/', {'name': 'Escalation'}, format='json').status_code == 403


def test_scoped_token_still_respects_endpoint_permissions(owner):
    _, _, client = issue(owner, 'products')
    assert client.get('/api/products/categories/').status_code == 200
    assert client.post('/api/products/categories/', {'name': 'Unauthorized'}, format='json').status_code == 403


@pytest.mark.parametrize('state', ['revoked', 'expired', 'inactive_user', 'unknown_scope'])
def test_invalid_credentials_fail_closed(owner, state):
    token, _, client = issue(owner)
    if state == 'revoked':
        token.is_active = False
    elif state == 'expired':
        token.expires_at = timezone.now() - timedelta(seconds=1)
    elif state == 'inactive_user':
        owner.is_active = False
        owner.save(update_fields=['is_active'])
    else:
        token.scope = 'future_scope'
    token.save()
    assert client.get('/api/accounts/me/').status_code in (401, 403)


@pytest.mark.parametrize('header', [b'Token', b'Token a b', b'Token \xff', b'Token invalid'])
def test_malformed_token_headers_return_auth_errors(header):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=header)
    assert client.get('/api/accounts/me/').status_code == 401


def test_untrusted_forwarded_ip_does_not_break_or_spoof_usage(owner):
    token, _, client = issue(owner)
    assert client.get('/api/accounts/me/', HTTP_X_FORWARDED_FOR='invalid, 203.0.113.1').status_code == 200
    token.refresh_from_db()
    assert token.last_used_ip == '127.0.0.1'
    assert token.total_requests == 1


def test_token_ownership_and_revocation(owner):
    token, _, client = issue(owner)
    other = User.objects.create_user(username='other-token-owner', user_type='customer')
    assert jwt_client(other).delete(f'/api/accounts/tokens/{token.pk}/').status_code == 404
    assert client.get('/api/accounts/me/').status_code == 200
    assert jwt_client(owner).post(f'/api/accounts/tokens/{token.pk}/revoke/').status_code == 200
    assert client.get('/api/accounts/me/').status_code == 401


def test_past_expiry_is_rejected(owner):
    response = jwt_client(owner).post('/api/accounts/tokens/', {
        'name': 'Already expired', 'expires_at': (timezone.now() - timedelta(days=1)).isoformat(),
    }, format='json')
    assert response.status_code == 400
    assert not APIToken.objects.filter(user=owner).exists()


def test_openapi_documents_auth_alternatives_and_one_time_secret():
    schema = SchemaGenerator(patterns=[
        path('tokens/', APITokenViewSet.as_view({'get': 'list', 'post': 'create'})),
    ]).get_schema(public=True)
    validate_schema(schema)
    security = schema['paths']['/tokens/']['get']['security']
    assert {'jwtAuth': []} in security
    assert {'cookieAuth': []} in security
    assert {'apiTokenHeader': []} in security
    assert {'apiTokenAuthorization': []} in security
    schemes = schema['components']['securitySchemes']
    assert schemes['apiTokenHeader']['name'] == 'X-API-Token'
    assert schemes['jwtAuth']['scheme'] == 'bearer'
    components = schema['components']['schemas']
    assert 'token' not in components['APIToken']['properties']
    assert 'token' in components['APITokenCreated']['properties']
