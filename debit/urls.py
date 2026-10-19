from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CreditAccountView,
    CreditAccountCreateView,
    CreditEligibilityView,
    CreditPurchaseViewSet,
)

router = DefaultRouter()
router.register(r'purchases', CreditPurchaseViewSet, basename='credit-purchase')

urlpatterns = [
    path('account/', CreditAccountView.as_view(), name='credit-account'),
    path('account/create/', CreditAccountCreateView.as_view(), name='credit-account-create'),
    path('eligibility/', CreditEligibilityView.as_view(), name='credit-eligibility'),
    path('', include(router.urls)),
]
