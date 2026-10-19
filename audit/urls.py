"""
URL configuration for the audit trail API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from audit.views import AuditLogViewSet, LoginAttemptViewSet

router = DefaultRouter()
router.register(r'logs', AuditLogViewSet, basename='audit-log')
router.register(r'login-attempts', LoginAttemptViewSet, basename='login-attempt')

app_name = 'audit'

urlpatterns = [
    path('', include(router.urls)),
]
