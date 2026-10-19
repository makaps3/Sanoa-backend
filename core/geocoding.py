"""Lightweight Google Maps geocoding helper.

Used to convert address text -> (latitude, longitude) when a client
saves a `orders.ShippingAddress` or `business.Address` without supplying
coordinates. The hot path is a single HTTPS request to Google's
Geocoding API gated by `settings.GOOGLE_MAPS_API_KEY`.

Design choices:
- No external SDK — `requests` is already a project dependency and the
  Geocoding API is one endpoint, so an SDK adds nothing.
- Short timeout (4 s) so a slow upstream never holds a user form
  submit for very long. Address rows save with NULL coordinates on
  failure rather than 5xx — the delivery flow can still compute fare
  from the textual address as a fallback elsewhere.
- Returns Decimals (not floats) so callers can drop them straight into
  the model's DecimalField columns without precision games.
- Pure function, no I/O on import — safe to import from model `save()`
  paths.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from functools import lru_cache
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger('sanoa.geocoding')

_GOOGLE_GEOCODE_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
_REQUEST_TIMEOUT = 4  # seconds


@lru_cache(maxsize=1024)
def _reverse_geocode_cached(lat_str: str, lng_str: str) -> Optional[str]:
    api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '') or ''
    if not api_key:
        return None
    try:
        response = requests.get(
            _GOOGLE_GEOCODE_URL,
            params={'latlng': f'{lat_str},{lng_str}', 'key': api_key, 'region': 'za'},
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning('Reverse geocoding failed for %s,%s: %s', lat_str, lng_str, exc)
        return None
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if payload.get('status') != 'OK':
        return None
    results = payload.get('results') or []
    return (results[0].get('formatted_address') if results else None) or None


def reverse_geocode(latitude, longitude) -> Optional[str]:
    """Return a human-readable address for a coordinate, or ``None`` when the
    API key isn't configured / Google can't resolve it. Cached on coords
    rounded to ~1 m so repeat lookups for the same place are free.

    Meant for on-demand paths (e.g. a job-detail screen) — never call it in a
    tight loop or a high-traffic hot path."""
    if latitude is None or longitude is None:
        return None
    try:
        lat_str = f'{float(latitude):.5f}'
        lng_str = f'{float(longitude):.5f}'
    except (TypeError, ValueError):
        return None
    return _reverse_geocode_cached(lat_str, lng_str)


def geocode_address(
    *,
    street_address: str = '',
    apartment_number: str = '',
    city: str = '',
    state_province: str = '',
    postal_code: str = '',
    country: str = 'South Africa',
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """Return (latitude, longitude) for the supplied address fields.

    Falls back to (None, None) when the API key isn't configured, the
    address is too thin to bother with, or Google can't find a match.
    The caller is responsible for handling NULL coordinates — usually
    by just saving without them.
    """
    api_key = getattr(settings, 'GOOGLE_MAPS_API_KEY', '') or ''
    if not api_key:
        return None, None

    # Build a single freeform string — Google's geocoder works better
    # with a natural address line than with structured components. We
    # deliberately drop the apartment / unit number because it almost
    # never affects the resolved coordinate and sometimes confuses the
    # geocoder (e.g. "Apt 4B" mistaken for a street suffix).
    parts = [
        street_address,
        city,
        state_province,
        postal_code,
        country or 'South Africa',
    ]
    address_text = ', '.join(p.strip() for p in parts if p and p.strip())
    if len(address_text) < 6:
        # Not enough signal to geocode usefully (e.g. only "ZA" left
        # after stripping). Skip the round trip.
        return None, None

    try:
        response = requests.get(
            _GOOGLE_GEOCODE_URL,
            params={
                'address': address_text,
                'key': api_key,
                # Bias results to South Africa unless the country
                # explicitly says otherwise — Google occasionally
                # picks up partial-match same-named towns abroad.
                'region': 'za',
            },
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning('Geocoding request failed for %r: %s', address_text, exc)
        return None, None

    if response.status_code != 200:
        logger.warning(
            'Geocoding non-200 (%s) for %r: %s',
            response.status_code, address_text, response.text[:200],
        )
        return None, None

    try:
        payload = response.json()
    except ValueError:
        logger.warning('Geocoding returned non-JSON for %r', address_text)
        return None, None

    api_status = payload.get('status')
    if api_status != 'OK':
        # ZERO_RESULTS, OVER_QUERY_LIMIT, REQUEST_DENIED, INVALID_REQUEST,
        # UNKNOWN_ERROR — none warrant raising; just leave coords blank.
        if api_status not in ('OK', 'ZERO_RESULTS'):
            logger.warning(
                'Geocoding API status %s for %r: %s',
                api_status, address_text, payload.get('error_message', ''),
            )
        return None, None

    results = payload.get('results') or []
    if not results:
        return None, None

    location = (
        results[0].get('geometry', {}).get('location') or {}
    )
    lat = location.get('lat')
    lng = location.get('lng')
    if lat is None or lng is None:
        return None, None

    # Cast through str to dodge float-binary noise before the Decimal
    # ends up in a 9,6 column.
    try:
        return Decimal(str(lat)), Decimal(str(lng))
    except (ArithmeticError, ValueError):
        return None, None
