"""The mobile workspace contract must describe real response and upload shapes."""
from django.urls import path
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema

from platform_admin.vetting_views import (
    VendorSelfVettingView, VendorSelfDocumentUploadView, DriverSelfVettingView,
)


def test_workspace_schema_has_checklists_and_binary_uploads():
    schema = SchemaGenerator(patterns=[
        path('vendor/', VendorSelfVettingView.as_view()),
        path('vendor/document/', VendorSelfDocumentUploadView.as_view()),
        path('driver/', DriverSelfVettingView.as_view()),
    ]).get_schema(public=True)
    validate_schema(schema)
    components = schema['components']['schemas']
    vendor = components['VendorSelfVetting']['properties']
    assert vendor['checklist']['type'] == 'array'
    assert vendor['can_trade']['type'] == 'boolean'
    assert components['VettingChecklistItem']['properties']['required']['type'] == 'boolean'
    upload = components['VendorDocumentUploadRequest']['properties']
    assert upload['file']['format'] == 'binary'
    paths = schema['paths']
    assert 'multipart/form-data' in paths['/vendor/document/']['post']['requestBody']['content']
    assert 'requestBody' not in paths['/vendor/']['post']
    assert 'requestBody' not in paths['/driver/']['post']
    assert '409' in paths['/vendor/']['post']['responses']
    assert 'missing_documents' in components['DriverVettingSubmitted']['properties']
