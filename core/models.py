"""
Base model abstractions for common functionality
"""
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Base model that includes creation and modification timestamps"""
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['-updated_at']),
        ]


class SoftDeleteModel(TimeStampedModel):
    """Base model that supports soft deletes"""
    
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        """Soft delete the model instance"""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft deleted instance"""
        self.deleted_at = None
        self.save()
    
    @property
    def is_deleted(self):
        """Check if instance is soft deleted"""
        return self.deleted_at is not None


class ActiveModel(TimeStampedModel):
    """Base model for records with active/inactive state"""
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True
    
    def deactivate(self):
        """Deactivate the model instance"""
        self.is_active = False
        self.save()
    
    def activate(self):
        """Activate the model instance"""
        self.is_active = True
        self.save()
