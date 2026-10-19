"""Authenticated access to verification evidence; never expose a public file URL."""
from functools import reduce
from operator import or_
from pathlib import PurePosixPath
from urllib.parse import quote

from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404
from django.utils.deconstruct import deconstructible
from django.views.static import serve
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q

PRIVATE_PREFIXES = ('docs/', 'documents/', 'drivers/id_docs/', 'drivers/insurance/', 'drivers/licenses/')


@deconstructible
class VerificationDocumentStorage(FileSystemStorage):
    def url(self, name):
        return '/api/accounts/documents/' + quote(name, safe='/')


private_document_storage = VerificationDocumentStorage()


def public_media(request, path, document_root=None, **kwargs):
    normalized = path.replace('\\', '/')
    if '..' in PurePosixPath(normalized).parts or normalized.startswith(PRIVATE_PREFIXES):
        raise Http404
    return serve(request, path, document_root=document_root, **kwargs)


class VerificationDocumentView(APIView):
    permission_classes = [IsAuthenticated]
    unverified_actions = ('get', 'head')

    def get(self, request, path):
        from business.models import (VendorProfile, IndividualVendorProfile, BusinessVendorProfile,
                                     VendorDocument, VendorEmployee)
        from delivery.models import DeliveryDriver
        if '..' in PurePosixPath(path).parts or '\\' in path or path.startswith('/'):
            raise Http404
        admin = getattr(request.user, 'admin_profile', None)
        for model in (VendorProfile, IndividualVendorProfile, BusinessVendorProfile, VendorDocument,
                      VendorEmployee, DeliveryDriver):
            fields = [f.name for f in model._meta.fields
                      if isinstance(getattr(f, 'storage', None), VerificationDocumentStorage)]
            if not fields:
                continue
            matches = model.objects.filter(reduce(or_, [Q(**{name: path}) for name in fields]))
            for obj in matches:
                if model is VendorDocument:
                    owner = obj.individual_vendor or obj.business_vendor
                    owner_id = owner.user_id if owner else None
                else:
                    owner_id = obj.user_id
                permission = 'manage_drivers' if model is DeliveryDriver else 'manage_vendors'
                allowed = owner_id == request.user.pk or request.user.is_superuser or (
                    admin is not None and admin.status == 'active' and admin.has_permission(permission))
                if not allowed:
                    continue
                document = next(getattr(obj, field) for field in fields if str(getattr(obj, field)) == path)
                try:
                    response = FileResponse(document.open('rb'), filename=PurePosixPath(path).name)
                except (FileNotFoundError, OSError):
                    raise Http404
                response['Cache-Control'] = 'private, no-store'
                response['X-Content-Type-Options'] = 'nosniff'
                return response
        raise Http404
