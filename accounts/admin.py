from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Sum
from django.urls import path
from django.template.response import TemplateResponse

from .models import User, CustomerProfile, APIToken


# Configure admin branding
admin.site.site_header = "Sanoa Administration"
admin.site.site_title = "Sanoa Admin"
admin.site.index_title = "Sanoa Admin Dashboard"


def sanoa_admin_dashboard(request):
    # use related apps for queries
    from business.models import IndividualVendorProfile, BusinessVendorProfile
    from products.models import Product
    from orders.models import Order
    from subscriptions.models import Subscription

    stats = {
        'total_users': User.objects.count(),
        'total_customers': User.objects.filter(user_type='customer').count(),
        'total_vendors': User.objects.filter(user_type='vendor').count(),
        'total_products': Product.objects.count(),
        'total_orders': Order.objects.count(),
        'total_order_value': Order.objects.aggregate(sum=Sum('total_amount'))['sum'] or 0,
        'active_subscriptions': Subscription.objects.filter(status='active').count(),
        'vendor_profiles': IndividualVendorProfile.objects.count() + BusinessVendorProfile.objects.count(),
    }

    context = {
        **admin.site.each_context(request),
        'title': 'Sanoa Dashboard',
        'stats': stats,
    }

    return TemplateResponse(request, 'admin/sanoa_dashboard.html', context)


# Add a custom admin URL

def get_admin_urls(old_get_urls):
    def get_urls():
        custom_urls = [
            path('sanoa-dashboard/', admin.site.admin_view(sanoa_admin_dashboard), name='sanoa-dashboard'),
        ]
        return custom_urls + old_get_urls()

    return get_urls

admin.site.get_urls = get_admin_urls(admin.site.get_urls)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'email', 'username', 'first_name', 'last_name',
        'user_type', 'is_verified', 'is_active', 'date_joined'
    ]
    list_filter = ['user_type', 'is_verified', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['email', 'username', 'first_name', 'last_name', 'phone_number']
    ordering = ['-date_joined']

    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('phone_number', 'user_type', 'is_verified', 'date_of_birth')
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('email', 'phone_number', 'user_type', 'is_verified')
        }),
    )


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gender', 'loyalty_points', 'newsletter_subscription', 'member_since']
    list_filter = ['gender', 'newsletter_subscription', 'sms_notifications', 'email_notifications']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['member_since', 'created_at', 'updated_at']

    fieldsets = [
        ('User Info', {'fields': ['user', 'avatar', 'gender', 'bio']}),
        ('Preferences', {
            'fields': [
                'preferred_language', 'newsletter_subscription',
                'sms_notifications', 'email_notifications'
            ]
        }),
        ('Loyalty Program', {'fields': ['loyalty_points', 'member_since']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'user', 'prefix', 'scope', 'is_active',
        'last_used_at', 'total_requests', 'created_at'
    ]
    list_filter = ['scope', 'is_active', 'created_at']
    search_fields = ['name', 'user__email', 'prefix']
    readonly_fields = ['prefix', 'token_hash', 'last_used_at', 'last_used_ip', 'total_requests', 'created_at']

    fieldsets = [
        ('Token Info', {
            'fields': ['user', 'name', 'prefix', 'token_hash', 'scope']
        }),
        ('Status', {
            'fields': ['is_active', 'expires_at']
        }),
        ('Usage', {
            'fields': ['last_used_at', 'last_used_ip', 'total_requests'],
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ['created_at'],
            'classes': ['collapse']
        }),
    ]
