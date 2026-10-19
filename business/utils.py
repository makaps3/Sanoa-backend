"""Shared helpers for the business app."""


def _resolve_vendor_profile(vendor):
    """
    Return the unified VendorProfile for a vendor user, or None if not created.
    Falls back to legacy Individual/Business profiles during migration.
    """
    if not vendor:
        return None
    # Preferred: unified VendorProfile
    profile = getattr(vendor, 'vendor_profile', None)
    if profile:
        return profile
    # Fallback: legacy profiles (still present during transition)
    return (
        getattr(vendor, 'business_vendor_profile', None)
        or getattr(vendor, 'individual_vendor_profile', None)
    )


def build_vendor_info(vendor, request=None):
    """
    Return a consistent vendor info dict for API responses.

    Resolution order for `name`, `logo`, `average_rating`, `review_count`:
      1. Unified VendorProfile (name, logo, ...)
      2. Legacy business/individual profiles (fallback during migration)
      3. Fallback to the user's own first/last name, username, or email local part
    """
    if not vendor:
        return None

    profile = _resolve_vendor_profile(vendor)

    name = ''
    logo_file = None
    average_rating = '0.00'
    review_count = 0
    profile_id = None
    profile_type = None

    if profile is not None:
        # Try unified VendorProfile fields first, fall back to legacy names.
        name = (
            getattr(profile, 'name', None)
            or getattr(profile, 'business_name', None)
            or getattr(profile, 'store_name', None)
            or ''
        )
        logo_file = (
            getattr(profile, 'logo', None)
            or getattr(profile, 'business_logo', None)
            or getattr(profile, 'store_logo', None)
            or None
        )
        average_rating = str(getattr(profile, 'average_rating', '0.00'))
        review_count = getattr(profile, 'total_reviews', 0)
        profile_id = str(getattr(profile, 'id', '')) or None
        profile_type = getattr(profile, 'profile_type', None)

    if not name:
        full_name = f"{vendor.first_name} {vendor.last_name}".strip()
        name = full_name or vendor.username or (vendor.email or '').split('@')[0]

    logo = None
    if logo_file:
        try:
            url = logo_file.url
        except Exception:
            url = None
        if url:
            logo = request.build_absolute_uri(url) if request else url

    return {
        'id': str(vendor.id),
        'profile_id': profile_id,
        'profile_type': profile_type,
        'name': name,
        'email': vendor.email,
        'logo': logo,
        'average_rating': average_rating,
        'review_count': review_count,
    }
