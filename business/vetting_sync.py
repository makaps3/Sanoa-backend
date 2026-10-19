"""Synchronize authoritative review decisions to legacy application records."""
from .verification_workflow import sync_review_state

def sync_vetting_application(vendor_profile):
    if vendor_profile is not None:
        sync_review_state(vendor_profile)
    return 0
