from django.urls import path, include
from rest_framework.routers import DefaultRouter
from core.private_documents import VerificationDocumentView
from .views import (
    UserRegisterView, UserProfileView, UserViewSet,
    CustomerProfileViewSet, APITokenViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'profiles/customer', CustomerProfileViewSet, basename='customer-profile')
router.register(r'tokens', APITokenViewSet, basename='api-token')

urlpatterns = [
    path('documents/<path:path>', VerificationDocumentView.as_view(), name='verification-document'),
    path('register/', UserRegisterView.as_view(), name='user-register'),
    path('me/', UserProfileView.as_view(), name='user-profile'),
    path('', include(router.urls)),
]
