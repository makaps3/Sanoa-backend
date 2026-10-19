import pytest
from asgiref.sync import async_to_sync
from accounts.models import User
from core.ws_auth import JWTAuthMiddleware

pytestmark = pytest.mark.django_db


def test_websocket_rechecks_database_approval():
    user = User.objects.create_user(username='socketvendor', email='socket@example.com',
                                   user_type='vendor', is_verified=True)
    middleware = JWTAuthMiddleware(None)
    allowed = async_to_sync(middleware._has_access)
    assert not allowed(user)
    profile = user.vendor_profile
    profile.verification_status = 'verified'
    profile.store_active = True
    profile.save()
    assert allowed(user)
    User.objects.filter(pk=user.pk).update(is_suspended=True)
    assert not allowed(user)
