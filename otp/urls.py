from django.urls import path

from .views import ResendOTPView, SendOTPView, VerifyOTPView

app_name = 'otp'

urlpatterns = [
    path('send/', SendOTPView.as_view(), name='send-otp'),
    path('verify/', VerifyOTPView.as_view(), name='verify-otp'),
    path('resend/', ResendOTPView.as_view(), name='resend-otp'),
]
