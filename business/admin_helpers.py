"""
Shared Django-admin helpers for VendorProfile FKs.

Every admin that used to point at a vendor User (and now points at a
VendorProfile) uses these so the dropdown / filter / list column all show
the business name, never the owner's email.
"""
from django.contrib import admin
from django.db.models import Q

from .models import VendorProfile


def vendor_profile_label(profile):
    """
    Resolve a VendorProfile to its business/store name.

    Order:
      1. profile.trading_name
      2. profile.name
      3. legacy IndividualVendorProfile.store_name
      4. legacy BusinessVendorProfile.business_trading_name / business_name
      5. "(unnamed vendor <id>)" — never falls back to the owner email
    """
    if profile is None:
        return ''

    name = profile.trading_name or profile.name
    if name:
        return name

    user = getattr(profile, 'user', None)
    if user is not None:
        ivp = getattr(user, 'individual_vendor_profile', None)
        if ivp and ivp.store_name:
            return ivp.store_name
        bvp = getattr(user, 'business_vendor_profile', None)
        if bvp:
            legacy = bvp.business_trading_name or bvp.business_name
            if legacy:
                return legacy

    return f"(unnamed vendor {profile.pk})"


def real_vendor_profiles_qs():
    """
    VendorProfile rows that look like a real store:
      * has a legacy IndividualVendorProfile or BusinessVendorProfile, OR
      * is verified, OR
      * has a non-empty trading_name
    Skeleton rows (auto-created by migration / post_save signal without any
    real setup) are excluded from admin pickers.
    """
    return VendorProfile.objects.filter(
        Q(user__individual_vendor_profile__isnull=False)
        | Q(user__business_vendor_profile__isnull=False)
        | Q(verification_status='verified')
        | ~Q(trading_name='')
    )


def vendor_profile_formfield(formfield):
    """
    Apply the `queryset` filter + `label_from_instance` override on an
    existing ModelChoiceField that targets VendorProfile. Use this from
    `ModelAdmin.formfield_for_foreignkey` when the field points at
    VendorProfile so the dropdown renders business names.
    """
    if formfield is None:
        return formfield
    formfield.queryset = real_vendor_profiles_qs().select_related(
        'user',
        'user__individual_vendor_profile',
        'user__business_vendor_profile',
    ).distinct()
    formfield.label_from_instance = vendor_profile_label
    return formfield


class VendorBusinessFilter(admin.SimpleListFilter):
    """
    Sidebar filter that lists vendor profiles by BUSINESS name.

    Subclasses may override `filter_field_name` (default 'vendor') so the
    same class works on models whose vendor FK is called something else
    (e.g. inventory.PurchaseOrder uses `supplier`).

    Subclasses may override `products_relation` (default 'products') if
    they want to restrict the filter to profiles that actually have related
    rows of a specific reverse relation. Set to None to show all profiles.
    """
    title = 'vendor'
    parameter_name = 'vendor'
    filter_field_name = 'vendor'
    products_relation = None   # e.g. 'products', 'carts', 'orders'

    def lookups(self, request, model_admin):
        qs = real_vendor_profiles_qs()
        if self.products_relation:
            qs = qs.filter(**{f'{self.products_relation}__isnull': False})
        qs = qs.select_related(
            'user',
            'user__individual_vendor_profile',
            'user__business_vendor_profile',
        ).distinct()
        items = [(str(p.id), vendor_profile_label(p)) for p in qs]
        items.sort(key=lambda pair: (pair[1] or '').lower())
        return items

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            return queryset.filter(**{f'{self.filter_field_name}_id': value})
        return queryset
