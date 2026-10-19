from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, SubscriptionViewSet, AdminPlanViewSet, AdminSubscriptionViewSet

router = DefaultRouter()
router.register(r'plans', PlanViewSet, basename='plan')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')

admin_router = DefaultRouter()
admin_router.register(r'plans', AdminPlanViewSet, basename='admin-plan')
admin_router.register(r'subscriptions', AdminSubscriptionViewSet, basename='admin-subscription')

urlpatterns = [
    path('admin/', include(admin_router.urls)),
    path('', include(router.urls)),
]
