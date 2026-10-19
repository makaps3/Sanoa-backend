"""Shared upload validation for identity, company and driving documents."""
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers


def validate_document(upload):
    if not upload:
        return upload
    if not upload.size or upload.size > 10 * 1024 * 1024:
        raise serializers.ValidationError('Choose a non-empty file no larger than 10 MB.')
    extension = Path(upload.name).suffix.lower()
    if extension not in {'.pdf', '.jpg', '.jpeg', '.png'}:
        raise serializers.ValidationError('Use a PDF, JPG or PNG document.')
    position = upload.tell()
    try:
        upload.seek(0)
        if extension == '.pdf':
            if upload.read(5) != b'%PDF-':
                raise serializers.ValidationError('The file is not a valid PDF.')
        else:
            with Image.open(upload) as image:
                expected = 'PNG' if extension == '.png' else 'JPEG'
                if image.format != expected:
                    raise serializers.ValidationError('The image type does not match its file extension.')
                image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise serializers.ValidationError('The image could not be read. Upload a valid JPG or PNG.')
    finally:
        upload.seek(position)
    return upload


class DocumentValidationMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = {}
        for key, value in attrs.items():
            if hasattr(value, 'content_type'):
                try:
                    validate_document(value)
                except serializers.ValidationError as exc:
                    errors[key] = exc.detail
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
