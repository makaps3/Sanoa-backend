"""
Common serializer mixins and base classes
"""
from rest_framework import serializers


class TimestampedSerializerMixin:
    """Mixin to add timestamps to serializers"""
    
    def to_representation(self, instance):
        """Add timestamps to response"""
        data = super().to_representation(instance)
        if hasattr(instance, 'created_at'):
            data['created_at'] = instance.created_at
        if hasattr(instance, 'updated_at'):
            data['updated_at'] = instance.updated_at
        return data


class OwnerFilteredSerializerMixin:
    """Mixin to filter data by owner in list views"""
    
    def get_queryset(self):
        """Filter queryset by current user (owner)"""
        queryset = super().get_queryset()
        user = self.request.user
        if user and user.is_authenticated:
            return queryset.filter(user=user)
        return queryset.none()


class AuditSerializerMixin:
    """Mixin to include audit information in serializers"""
    
    created_by = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()
    
    def get_created_by(self, obj):
        if hasattr(obj, 'created_by'):
            return obj.created_by.email if obj.created_by else None
        return None
    
    def get_updated_by(self, obj):
        if hasattr(obj, 'updated_by'):
            return obj.updated_by.email if obj.updated_by else None
        return None
