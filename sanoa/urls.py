"""
URL configuration for sanoa project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.private_documents import public_media
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path('', include('django_prometheus.urls')),  # exposes /metrics for Prometheus scraping
    path('admin/', admin.site.urls),

    # JWT Authentication
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # API endpoints
    path('api/accounts/', include('accounts.urls')),
    path('api/business/', include('business.urls')),
    path('api/products/', include('products.urls')),
    path('api/orders/', include('orders.urls')),
    path('api/restaurant/', include('restaurant.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/debit/', include('debit.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),
    path('api/negotiations/', include('negotiations.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/tickets/', include('tickets.urls')),
    path('api/promotions/', include('promotions.urls')),
    path('api/otp/', include('otp.urls')),
    path('api/tiers/', include('tiers.urls')),
    path('api/audit/', include('audit.urls')),
    path('api/delivery/', include('delivery.urls')),
    path('api/fraud/', include('fraud.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/platform-admin/', include('platform_admin.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT, view=public_media)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]
