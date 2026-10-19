"""
Platform-wide humanized error responses.

Registered as DRF's ``EXCEPTION_HANDLER`` so EVERY endpoint returns errors
in one consistent, human-readable shape — without touching each view:

    {
      "detail": "A clear sentence the user can understand.",
      "errors": {"field": ["message", ...]},   # only for validation errors
      "code":   "validation_error"              # machine-friendly slug
    }

The original DRF field keys are preserved alongside ``detail``/``errors`` so
existing clients that read them keep working; new clients just read
``detail``. Generic framework phrases ("Authentication credentials were not
provided.", "Not found.", …) are rewritten into friendly language.
"""
import logging

from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger('sanoa.exceptions')


# Generic DRF / auth phrases → friendly equivalents.
_FRIENDLY = {
    'authentication credentials were not provided.':
        'Please sign in to continue.',
    'incorrect authentication credentials.':
        'Your session has expired. Please sign in again.',
    'invalid token.':
        'Your session has expired. Please sign in again.',
    'token is invalid or expired':
        'Your session has expired. Please sign in again.',
    'user not found':
        'Your session has expired. Please sign in again.',
    'given token not valid for any token type':
        'Your session has expired. Please sign in again.',
    'you do not have permission to perform this action.':
        "You don't have permission to do that.",
    'not found.':
        "We couldn't find what you were looking for.",
    'a server error occurred.':
        'Something went wrong on our end. Please try again shortly.',
}


def _friendly(message: str, status_code: int) -> str:
    """Map a generic framework message to friendlier language."""
    if not message:
        return _by_status(status_code)
    key = message.strip().lower()
    if key in _FRIENDLY:
        return _FRIENDLY[key]
    if key.startswith('method ') and 'not allowed' in key:
        return "That action isn't available here."
    if 'throttled' in key or 'request was throttled' in key:
        return ("You're doing that a little too often. "
                'Please wait a moment and try again.')
    return message


def _by_status(status_code: int) -> str:
    return {
        400: 'Please check the details you entered and try again.',
        401: 'Please sign in to continue.',
        403: "You don't have permission to do that.",
        404: "We couldn't find what you were looking for.",
        405: "That action isn't available here.",
        409: 'That request conflicts with something that already exists.',
        413: 'That file or request is too large.',
        429: ("You're doing that a little too often. "
              'Please wait a moment and try again.'),
    }.get(status_code, 'Something went wrong. Please try again.')


# Words that must keep their casing in a field label.
_ACRONYMS = {
    'cipc': 'CIPC', 'id': 'ID', 'vat': 'VAT', 'bee': 'BEE', 'sms': 'SMS',
    'otp': 'OTP', 'url': 'URL', 'qr': 'QR', 'api': 'API', 'pin': 'PIN',
}


def _humanize_field(name: str) -> str:
    """'cipc_document' → 'CIPC document'; 'owner_id_number' → 'Owner ID number'."""
    if name in ('non_field_errors', 'detail', '__all__'):
        return ''
    words = name.replace('_', ' ').strip().split()
    if not words:
        return ''
    out = []
    for i, w in enumerate(words):
        low = w.lower()
        if low in _ACRONYMS:
            out.append(_ACRONYMS[low])
        elif i == 0:
            out.append(w.capitalize())
        else:
            out.append(low)
    return ' '.join(out)


def _flatten(value) -> list:
    """Collect leaf error strings from DRF's nested error structures."""
    out = []
    if isinstance(value, dict):
        for v in value.values():
            out.extend(_flatten(v))
    elif isinstance(value, (list, tuple)):
        for v in value:
            out.extend(_flatten(v))
    elif value is not None:
        out.append(str(value))
    return out


def _collect_field_errors(data: dict) -> dict:
    errors = {}
    for field, messages in data.items():
        if field in ('detail', 'code', 'errors'):
            continue
        msgs = _flatten(messages)
        if msgs:
            errors[field] = msgs
    return errors


def _summary(errors: dict, status_code: int) -> str:
    """Build one readable sentence from field errors."""
    if not errors:
        return _by_status(status_code)
    parts = []
    for field, msgs in errors.items():
        label = _humanize_field(field)
        msg = msgs[0]
        parts.append(f'{label}: {msg}' if label else msg)
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f'{parts[0]}  {parts[1]}'
    return 'Please fix a few things: ' + '  '.join(parts[:3]) + (
        ' …' if len(parts) > 3 else '')


def humanized_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        # Not a DRF-handled exception (e.g. an uncaught 500). Leave it for
        # Django; we never want to mask a real crash as a friendly response.
        logger.error('Unhandled exception in %s: %s',
                     context.get('view'), exc, exc_info=True)
        return None

    code = getattr(exc, 'default_code', None) or 'error'
    data = response.data
    status_code = response.status_code

    if isinstance(data, dict):
        field_errors = _collect_field_errors(data)
        if 'detail' in data and not field_errors:
            # Single framework/detail message — just humanize it.
            data['detail'] = _friendly(str(data['detail']), status_code)
            data.setdefault('code', code)
        else:
            data.setdefault('detail', _summary(field_errors, status_code))
            data['errors'] = field_errors
            data.setdefault('code', code)
        response.data = data
    elif isinstance(data, list):
        joined = '  '.join(str(x) for x in _flatten(data))
        response.data = {'detail': _friendly(joined, status_code), 'code': code}
    else:
        response.data = {
            'detail': _friendly(str(data), status_code), 'code': code}
    return response


# Backwards-compatible alias — the old settings key referenced this name.
custom_exception_handler = humanized_exception_handler
