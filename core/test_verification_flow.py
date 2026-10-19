"""Security and end-to-end API regression tests using real JWT authentication."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from business.models import VendorProfile
from business.verification import vendor_vetting_checklist
from core.document_validation import validate_document
from platform_admin.models import AdminProfile
from rest_framework.exceptions import ValidationError

pytestmark = pytest.mark.django_db


def client_for(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')
    return client


@pytest.fixture
def vendor():
    user = User.objects.create_user(username='seller', email='seller@example.com',
                                    password='ComplexSeller#293', user_type='vendor', is_verified=True)
    return VendorProfile.objects.get(user=user)


@pytest.fixture
def reviewer():
    user = User.objects.create_user(username='reviewer', email='reviewer@example.com',
                                    password='ComplexReviewer#293', user_type='admin', is_verified=True)
    profile = AdminProfile.objects.create(user=user, role='super_admin', department='operations',
                                           work_email='reviewer@example.com')
    profile.seed_permissions()
    profile.save()
    return user


def complete(vendor):
    vendor.name = 'Test store'
    vendor.id_number = '9001015000087'
    vendor.id_document = 'documents/id.pdf'
    vendor.selfie_with_id = 'documents/selfie.jpg'
    vendor.proof_of_address = 'documents/address.pdf'
    vendor.proof_of_bank = 'documents/bank.pdf'
    vendor.save()


def test_account_cannot_self_promote_or_verify():
    user = User.objects.create_user(username='customer', email='customer@example.com', user_type='customer')
    result = client_for(user).patch('/api/accounts/me/', {
        'user_type': 'admin', 'is_verified': True, 'is_active': False,
        'first_name': 'Updated',
    }, format='json')
    assert result.status_code == 200
    user.refresh_from_db()
    assert user.user_type == 'customer' and not user.is_verified and user.is_active
    assert user.first_name == 'Updated'


def test_public_admin_registration_requires_invitation():
    result = APIClient().post('/api/accounts/register/', {
        'email': 'intruder@example.com', 'username': 'intruder', 'user_type': 'admin',
        'password': 'ComplexIntruder#293', 'password_confirm': 'ComplexIntruder#293',
    }, format='json')
    assert result.status_code == 400
    assert not User.objects.filter(email='intruder@example.com').exists()


def test_individual_cipc_is_optional_business_cipc_is_required(vendor):
    with patch('business.verification._vendor_bank_ready', return_value=True):
        complete(vendor)
        checklist = vendor_vetting_checklist(vendor)
        assert checklist['complete']
        cipc = [i for section in checklist['sections'] for i in section['items'] if i['code'] == 'cipc_document'][0]
        assert not cipc['required']
        vendor.profile_type = 'business'
        assert 'cipc_document' in {i['code'] for i in vendor_vetting_checklist(vendor)['missing']}


def test_business_profile_cannot_omit_cipc(vendor):
    result = client_for(vendor.user).patch(f'/api/business/profiles/vendor/{vendor.pk}/', {
        'profile_type': 'business', 'name': 'Business store',
    }, format='json')
    assert result.status_code == 400
    assert 'cipc_document' in result.data


def test_onboarding_remains_available_while_operations_are_locked(vendor):
    client = client_for(vendor.user)
    assert client.get('/api/business/profiles/vendor/me/').status_code == 200
    assert client.get('/api/platform-admin/vetting/me/vendor/').status_code == 200
    response = client.get(f'/api/inventory/vendor/{vendor.pk}/warehouses/')
    assert response.status_code == 403
    assert response.data['code'] == 'verification_required'


def test_approval_requires_complete_documents(vendor, reviewer):
    vendor.verification_status = 'under_review'
    vendor.save()
    response = client_for(reviewer).post(f'/api/platform-admin/vetting/vendors/{vendor.pk}/action/',
                                       {'action': 'approve'}, format='json')
    assert response.status_code == 400
    vendor.refresh_from_db()
    assert vendor.verification_status == 'under_review'


def test_approval_and_revocation_use_current_database_state(vendor, reviewer):
    complete(vendor)
    vendor.verification_status = 'under_review'
    vendor.save()
    client = client_for(vendor.user)
    with patch('business.verification._vendor_bank_ready', return_value=True):
        result = client_for(reviewer).post(f'/api/platform-admin/vetting/vendors/{vendor.pk}/action/',
                                           {'action': 'approve'}, format='json')
    assert result.status_code == 200
    vendor.refresh_from_db()
    assert vendor.can_trade and vendor.owner_vetting_passed
    assert client.get(f'/api/inventory/vendor/{vendor.pk}/warehouses/').status_code == 200
    result = client_for(reviewer).post(f'/api/platform-admin/vetting/vendors/{vendor.pk}/action/',
                                      {'action': 'suspend', 'reason': 'Review required'}, format='json')
    assert result.status_code == 200
    assert client.get(f'/api/inventory/vendor/{vendor.pk}/warehouses/').status_code == 403


def test_replacing_evidence_invalidates_approval(vendor, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    complete(vendor)
    vendor.verification_status = 'verified'
    vendor.store_active = True
    vendor.save()
    response = client_for(vendor.user).patch(f'/api/business/profiles/vendor/{vendor.pk}/',
                                            {'id_number': '9001015000088'}, format='json')
    assert response.status_code == 200
    vendor.refresh_from_db()
    assert vendor.verification_status == 'pending' and not vendor.store_active


def test_suspended_reviewer_cannot_approve(vendor, reviewer):
    AdminProfile.objects.filter(user=reviewer).update(status='suspended')
    result = client_for(reviewer).post(f'/api/platform-admin/vetting/vendors/{vendor.pk}/action/',
                                       {'action': 'approve'}, format='json')
    assert result.status_code == 403


def test_upload_rejects_disguised_files():
    for name, data in [('document.pdf', b'<script>bad</script>'), ('document.exe', b'abc'), ('document.png', b'abc')]:
        with pytest.raises(ValidationError):
            validate_document(SimpleUploadedFile(name, data))


def test_driver_with_expired_licence_is_not_verified():
    from delivery.models import DeliveryDriver
    user = User.objects.create_user(username='driver', email='driver@example.com', user_type='driver', is_verified=True)
    driver = DeliveryDriver(user=user, identity_verification_status='approved', terms_accepted=True,
                            license_expiry_date=timezone.localdate() - timedelta(days=1))
    assert not driver.is_verified


def test_driver_requires_both_review_stages():
    from delivery.models import DeliveryDriver
    user = User.objects.create_user(username='reviewdriver', email='reviewdriver@example.com', user_type='driver', is_verified=True)
    driver = DeliveryDriver(user=user, identity_verification_status='approved', terms_accepted=True,
                            license_expiry_date=timezone.localdate() + timedelta(days=30))
    assert not driver.is_verified
    assert driver.verification_status == 'under_review'
    driver.background_check_status = 'approved'
    assert driver.is_verified
