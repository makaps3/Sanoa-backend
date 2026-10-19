from django.contrib import admin
from business.admin_helpers import (
    VendorBusinessFilter as _BaseVendorBusinessFilter,
    vendor_profile_formfield,
    vendor_profile_label,
)
from .models import (
    DeliveryDriver, DeliveryFare, FareRate,
    DriverShift, DeliveryJob, DriverLocationPing,
    DriverEarning, DriverPayout, DriverRating,
)


class DeliveryFareVendorFilter(_BaseVendorBusinessFilter):
    products_relation = 'delivery_fares'


@admin.register(FareRate)
class FareRateAdmin(admin.ModelAdmin):
    list_display = ['business_category', 'base_fare', 'per_km_rate', 'max_distance_km', 'is_active', 'updated_at']
    list_filter = ['is_active', 'business_category']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DeliveryDriver)
class DeliveryDriverAdmin(admin.ModelAdmin):
    list_display = ['user', 'vehicle_type', 'is_available', 'total_deliveries', 'average_rating', 'created_at']
    list_filter = ['vehicle_type', 'is_available']
    search_fields = ['user__email', 'vehicle_registration', 'license_number']
    raw_id_fields = ['user']
    readonly_fields = ['total_deliveries', 'average_rating', 'created_at', 'updated_at']


@admin.register(DeliveryFare)
class DeliveryFareAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'vendor_display', 'driver', 'business_category', 'distance_km', 'fare_amount', 'status', 'created_at']
    list_filter = [DeliveryFareVendorFilter, 'status', 'business_category', 'created_at']
    search_fields = ['customer__email', 'driver__email', 'vendor__name', 'vendor__trading_name']
    raw_id_fields = ['customer', 'driver', 'address']
    readonly_fields = ['distance_km', 'base_fare', 'per_km_rate', 'fare_amount', 'pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude', 'created_at', 'updated_at', 'accepted_at', 'completed_at']

    @admin.display(description='Vendor', ordering='vendor__name')
    def vendor_display(self, obj):
        return vendor_profile_label(obj.vendor)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == 'vendor':
            return vendor_profile_formfield(formfield)
        return formfield

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'driver', 'vendor', 'vendor__user')


@admin.register(DriverShift)
class DriverShiftAdmin(admin.ModelAdmin):
    list_display = ['driver', 'started_at', 'ended_at', 'is_active']
    list_filter = ['is_active', 'started_at']
    search_fields = ['driver__user__email']
    readonly_fields = ['started_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('driver__user')


class DriverLocationPingInline(admin.TabularInline):
    model = DriverLocationPing
    extra = 0
    readonly_fields = ['latitude', 'longitude', 'accuracy_meters', 'speed_kmh', 'heading_degrees', 'timestamp']
    fields = ['latitude', 'longitude', 'speed_kmh', 'heading_degrees', 'timestamp']
    max_num = 0  # read-only inline


@admin.register(DeliveryJob)
class DeliveryJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'vendor', 'driver', 'status', 'distance_km', 'fare_amount', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['customer__email', 'vendor__name', 'vendor__trading_name']
    raw_id_fields = ['customer', 'vendor', 'driver', 'fare', 'retail_order', 'restaurant_order']
    readonly_fields = ['created_at', 'updated_at', 'accepted_at', 'driver_at_vendor_at', 'picked_up_at', 'delivered_at', 'cancelled_at']
    inlines = [DriverLocationPingInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'driver__user', 'vendor')


@admin.register(DriverEarning)
class DriverEarningAdmin(admin.ModelAdmin):
    list_display = ['driver', 'job', 'gross_amount', 'platform_commission', 'net_amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['driver__user__email']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('driver__user', 'job')


@admin.register(DriverPayout)
class DriverPayoutAdmin(admin.ModelAdmin):
    list_display = ['driver', 'period_start', 'period_end', 'total_net', 'status', 'paid_at']
    list_filter = ['status', 'period_end']
    search_fields = ['driver__user__email', 'payment_reference']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('driver__user')


@admin.register(DriverRating)
class DriverRatingAdmin(admin.ModelAdmin):
    list_display = ['driver', 'customer', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['driver__user__email', 'customer__email']
    readonly_fields = ['created_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('driver__user', 'customer')
