from unittest.mock import patch
import pytest
from django.core import mail
from accounts.models import User
from platform_admin.models import AdminInvitation, AdminProfile
from core.test_verification_flow import client_for

pytestmark = pytest.mark.django_db


def make_inviter():
    user = User.objects.create_user(username='inviter', email='inviter@example.com', user_type='admin', is_verified=True)
    profile = AdminProfile.objects.create(user=user, role='super_admin', department='operations', work_email=user.email)
    return user, profile


def test_invitation_sends_token_and_acceptance_uses_assigned_role():
    inviter, _ = make_inviter()
    result = client_for(inviter).post('/api/platform-admin/invitations/send/', {
        'email': 'newadmin@example.com', 'role': 'support_admin', 'department': 'operations'}, format='json')
    assert result.status_code == 201, result.data
    invitation = AdminInvitation.objects.get(email='newadmin@example.com')
    assert invitation.token in mail.outbox[-1].body
    user = User.objects.create_user(username='newadmin', email='newadmin@example.com', user_type='admin')
    endpoint = f'/api/platform-admin/invitations/{invitation.token}/accept/'
    assert client_for(user).post(endpoint, {'work_email': user.email}, format='json').status_code == 403
    user.is_verified = True
    user.save(update_fields=['is_verified'])
    result = client_for(user).post(endpoint, {'work_email': user.email, 'role': 'super_admin'}, format='json')
    assert result.status_code == 201, result.data
    assert AdminProfile.objects.get(user=user).role == 'support_admin'
    assert client_for(user).post(endpoint, {'work_email': user.email}, format='json').status_code == 400


def test_failed_invitation_delivery_can_be_retried():
    inviter, _ = make_inviter()
    with patch('core.email.send_branded_email', return_value=False):
        result = client_for(inviter).post('/api/platform-admin/invitations/send/', {
            'email': 'retry@example.com', 'role': 'support_admin', 'department': 'operations'}, format='json')
    assert result.status_code == 503
    assert not AdminInvitation.objects.filter(email='retry@example.com').exists()


def test_expired_invitation_can_be_replaced_after_registration():
    from datetime import timedelta
    from django.utils import timezone
    from platform_admin.serializers import SendInvitationSerializer
    _, profile = make_inviter()
    User.objects.create_user(username='expiredadmin', email='expired@example.com', user_type='admin')
    invitation = AdminInvitation.objects.create(invited_by=profile, email='expired@example.com',
                                                role='support_admin', department='operations')
    AdminInvitation.objects.filter(pk=invitation.pk).update(expires_at=timezone.now() - timedelta(days=1))
    serializer = SendInvitationSerializer(data={'email': 'EXPIRED@example.com',
                                                 'role': 'support_admin', 'department': 'operations'})
    assert serializer.is_valid(), serializer.errors

