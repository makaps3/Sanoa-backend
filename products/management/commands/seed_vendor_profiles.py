"""
Populate sample VendorProfile data for every user who owns at least one Product,
then link each Product (and each VendorReview) to that profile.

Safe to re-run: existing profiles are updated only on fields that are still blank
unless --overwrite is passed.

Usage:
    python manage.py seed_vendor_profiles
    python manage.py seed_vendor_profiles --overwrite
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from business.models import VendorProfile
from products.models import Product, VendorReview

User = get_user_model()


# Real South African city centres with valid lat/lng so the delivery fare
# calculator has something to work with.
SAMPLE_CITIES = [
    {
        'city': 'Cape Town', 'province': 'Western Cape',
        'postal_code': '8001', 'latitude': Decimal('-33.924870'),
        'longitude': Decimal('18.424055'),
    },
    {
        'city': 'Johannesburg', 'province': 'Gauteng',
        'postal_code': '2001', 'latitude': Decimal('-26.204103'),
        'longitude': Decimal('28.047305'),
    },
    {
        'city': 'Durban', 'province': 'KwaZulu-Natal',
        'postal_code': '4001', 'latitude': Decimal('-29.858680'),
        'longitude': Decimal('31.021840'),
    },
    {
        'city': 'Pretoria', 'province': 'Gauteng',
        'postal_code': '0002', 'latitude': Decimal('-25.747868'),
        'longitude': Decimal('28.229271'),
    },
    {
        'city': 'Port Elizabeth', 'province': 'Eastern Cape',
        'postal_code': '6001', 'latitude': Decimal('-33.958050'),
        'longitude': Decimal('25.619600'),
    },
    {
        'city': 'Bloemfontein', 'province': 'Free State',
        'postal_code': '9301', 'latitude': Decimal('-29.085214'),
        'longitude': Decimal('26.159576'),
    },
]

SAMPLE_STREETS = [
    '12 Long Street', '45 Church Street', '89 West Avenue',
    '221 Market Road', '7 Mandela Drive', '156 Main Road',
    '33 Sandton Boulevard', '78 Rivonia Road',
]

DEFAULT_OPENING_HOURS = {
    '0': [{'open': '08:00', 'close': '18:00'}],
    '1': [{'open': '08:00', 'close': '18:00'}],
    '2': [{'open': '08:00', 'close': '18:00'}],
    '3': [{'open': '08:00', 'close': '18:00'}],
    '4': [{'open': '08:00', 'close': '19:00'}],
    '5': [{'open': '09:00', 'close': '19:00'}],
    '6': [{'open': '09:00', 'close': '14:00'}],
}


def _display_name(user):
    full = f"{user.first_name} {user.last_name}".strip()
    if full:
        return full
    if user.email:
        return user.email.split('@')[0].replace('.', ' ').title()
    return user.username or f'Vendor {user.id}'


def _pick(seq, key):
    """Deterministic pick so re-runs give the same sample row for the same user."""
    return seq[key % len(seq)]


def _business_category_for(user):
    """
    'restaurant' (Fast Food) if most of the vendor's products sit in
    restaurant categories, otherwise 'retail' (Groceries).
    """
    counts = {'retail': 0, 'restaurant': 0}
    rows = Product.objects.filter(vendor__user=user).values_list(
        'category__parent__business_category', 'category__business_category',
    )
    for parent_bc, own_bc in rows:
        bc = parent_bc or own_bc
        if bc in counts:
            counts[bc] += 1
    return 'restaurant' if counts['restaurant'] > counts['retail'] else 'retail'


def _profile_type_for(index):
    # Alternate individual / business so the demo shows both flavours.
    return 'individual' if index % 2 == 0 else 'business'


class Command(BaseCommand):
    help = (
        'Create/populate sample VendorProfile rows for every user that owns a '
        'Product, and link those profiles back to Product and VendorReview rows.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Overwrite fields that already have non-default values.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        overwrite = options['overwrite']

        # Product.vendor is a VendorProfile FK — join via vendor__user to
        # get the User rows that own at least one product.
        vendor_user_ids = (
            Product.objects.values_list('vendor__user_id', flat=True).distinct()
        )
        vendors = list(
            User.objects.filter(id__in=vendor_user_ids).order_by('id')
        )

        if not vendors:
            self.stdout.write(self.style.WARNING(
                'No users own any Product rows — nothing to seed.'
            ))
            return

        created = 0
        updated = 0
        linked_products = 0
        linked_reviews = 0

        for index, user in enumerate(vendors):
            profile, was_created = VendorProfile.objects.get_or_create(
                user=user,
                defaults={
                    'profile_type': _profile_type_for(index),
                    'name': _display_name(user),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

            display_name = _display_name(user)
            city = _pick(SAMPLE_CITIES, user.id)
            street = _pick(SAMPLE_STREETS, user.id)
            profile_type = profile.profile_type or _profile_type_for(index)

            desired = {
                'profile_type': profile_type,
                'business_category': _business_category_for(user),
                'name': display_name,
                'trading_name': f"{display_name} Store",
                'description': (
                    f"Sample storefront for {display_name}. Auto-generated "
                    "for local marketplace demonstration."
                ),
                'street_address': street,
                'city': city['city'],
                'province': city['province'],
                'postal_code': city['postal_code'],
                'country': 'South Africa',
                'latitude': city['latitude'],
                'longitude': city['longitude'],
                'bank_name': 'FNB',
                'bank_account_number': f"62{user.id:010d}"[:11],
                'bank_branch_code': '250655',
                'bank_account_holder': display_name,
                'verification_status': 'verified',
                'owner_vetting_passed': True,
                'business_vetting_passed': True,
                'store_active': True,
                'opening_hours': DEFAULT_OPENING_HOURS,
            }

            if profile_type == 'individual':
                desired['vendor_type'] = 'local_brand'
            else:
                desired['business_type'] = 'pty_ltd'
                desired['cipc_registration_number'] = (
                    f"2024/{user.id:06d}/07"
                )
                desired['owner_full_name'] = display_name

            dirty_fields = []
            for field, value in desired.items():
                current = getattr(profile, field)
                is_blank = current in (None, '', {}, Decimal('0'), 0)
                if overwrite or is_blank:
                    if current != value:
                        setattr(profile, field, value)
                        dirty_fields.append(field)

            if dirty_fields:
                profile.save(update_fields=dirty_fields)

            # Product.vendor is now the VendorProfile FK itself, so
            # products owned by this user are already linked via the
            # migration. Realign any that happen to point elsewhere.
            linked_products += Product.objects.filter(
                vendor__user=user,
            ).exclude(vendor=profile).update(vendor=profile)

            # VendorReview still FKs to User (legacy) with an optional
            # vendor_profile mirror — keep the mirror pointing at the
            # unified profile for this vendor.
            linked_reviews += VendorReview.objects.filter(
                vendor=user,
            ).exclude(vendor_profile=profile).update(vendor_profile=profile)

            self.stdout.write(
                f"{'CREATED' if was_created else 'UPDATED'} "
                f"{profile.profile_type:<10} {display_name} "
                f"({city['city']}) -> {user.email}"
            )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created} created, {updated} existing updated. "
            f"Linked {linked_products} products and {linked_reviews} reviews."
        ))
