"""Explicit API contracts for the mobile verification workspace."""
from rest_framework import serializers

from core.document_validation import validate_document


VENDOR_DOCUMENT_FIELDS = (
    'id_document', 'selfie_with_id', 'proof_of_address', 'cipc_document',
    'tax_clearance_certificate', 'bee_certificate', 'owner_id_document',
    'owner_proof_of_address', 'proof_of_bank',
)


class MissingVettingItemSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()


class VettingChecklistItemSerializer(MissingVettingItemSerializer):
    section = serializers.CharField()
    provided = serializers.BooleanField()
    required = serializers.BooleanField()
    hint = serializers.CharField(allow_blank=True)
    url = serializers.CharField(allow_null=True)


class VettingChecklistSectionSerializer(serializers.Serializer):
    key = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField()
    items = VettingChecklistItemSerializer(many=True)
    complete = serializers.BooleanField()
    provided_count = serializers.IntegerField()
    required_count = serializers.IntegerField()


class VendorVettingWorkspaceSerializer(serializers.Serializer):
    verification_status = serializers.CharField()
    can_trade = serializers.BooleanField()
    rejection_reason = serializers.CharField(allow_blank=True)
    profile_type = serializers.ChoiceField(choices=['individual', 'business'])
    checklist = VettingChecklistSectionSerializer(many=True)
    missing_documents = MissingVettingItemSerializer(many=True)
    can_submit = serializers.BooleanField()


class VendorSelfVettingSerializer(VendorVettingWorkspaceSerializer):
    owner_vetting_passed = serializers.BooleanField()
    business_vetting_passed = serializers.BooleanField()
    verified_at = serializers.DateTimeField(allow_null=True)
    submitted_at = serializers.DateTimeField(required=False)


class VendorDocumentUploadSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=VENDOR_DOCUMENT_FIELDS)
    file = serializers.FileField(validators=[validate_document])


class VendorDocumentUploadedSerializer(VendorVettingWorkspaceSerializer):
    message = serializers.CharField()


class DriverSelfVettingSerializer(serializers.Serializer):
    identity_verification_status = serializers.CharField()
    background_check_status = serializers.CharField()
    vetting_notes = serializers.CharField(allow_blank=True)
    training_completed = serializers.BooleanField()
    terms_accepted = serializers.BooleanField()
    missing_documents = MissingVettingItemSerializer(many=True)
    can_submit = serializers.BooleanField()


class DriverVettingSubmittedSerializer(serializers.Serializer):
    identity_verification_status = serializers.CharField()
    background_check_status = serializers.CharField()
    missing_documents = MissingVettingItemSerializer(many=True)
    submitted_at = serializers.DateTimeField()


class VettingErrorSerializer(serializers.Serializer):
    error = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)
    missing_documents = MissingVettingItemSerializer(many=True, required=False)
    verification_status = serializers.CharField(required=False)
    identity_verification_status = serializers.CharField(required=False)
