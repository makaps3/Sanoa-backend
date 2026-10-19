import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from accounts.models import User
from core.test_verification_flow import client_for

pytestmark = pytest.mark.django_db


def test_identity_document_is_private_even_before_approval(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    owner = User.objects.create_user(username='docowner', email='owner@example.com', user_type='vendor')
    stranger = User.objects.create_user(username='stranger', email='stranger@example.com')
    vendor = owner.vendor_profile
    vendor.id_document.save('identity.pdf', SimpleUploadedFile('identity.pdf', b'%PDF-1.4 test'), save=True)
    url = vendor.id_document.url
    assert url.startswith('/api/accounts/documents/')
    assert APIClient().get(url).status_code == 401
    assert client_for(stranger).get(url).status_code == 404
    result = client_for(owner).get(url)
    assert result.status_code == 200
    assert result['Cache-Control'] == 'private, no-store'
    result.close()
    assert APIClient().get('/media/' + vendor.id_document.name).status_code == 404
    assert APIClient().get('/media/public/../' + vendor.id_document.name).status_code == 404


def test_inventory_is_not_public():
    owner = User.objects.create_user(username='stockowner', email='stock@example.com', user_type='vendor')
    path = f'/api/inventory/vendor/{owner.vendor_profile.pk}/purchase-orders/'
    assert APIClient().get(path).status_code == 401
