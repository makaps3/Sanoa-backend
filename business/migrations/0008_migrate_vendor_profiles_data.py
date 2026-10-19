"""Copy rows from IndividualVendorProfile + BusinessVendorProfile → VendorProfile."""
from django.db import migrations


def copy_forward(apps, schema_editor):
    Individual = apps.get_model('business', 'IndividualVendorProfile')
    Business = apps.get_model('business', 'BusinessVendorProfile')
    VendorProfile = apps.get_model('business', 'VendorProfile')

    for src in Individual.objects.all():
        if VendorProfile.objects.filter(user=src.user).exists():
            continue
        VendorProfile.objects.create(
            user=src.user,
            profile_type='individual',
            business_category=src.business_category,
            vendor_type=src.vendor_type or '',
            name=src.store_name,
            description=src.store_description or '',
            logo=src.store_logo or None,
            qr_code=src.qr_code or None,
            qr_code_identifier=src.qr_code_identifier,
            id_number=src.id_number or '',
            id_document=src.id_document or None,
            proof_of_address=src.proof_of_address or None,
            selfie_with_id=src.selfie_with_id or None,
            street_address=src.trading_address or '',
            city=src.trading_city or '',
            province=src.trading_province or '',
            postal_code=src.trading_postal_code or '',
            latitude=src.latitude,
            longitude=src.longitude,
            bank_name=src.bank_name or '',
            bank_account_number=src.bank_account_number or '',
            bank_branch_code=src.bank_branch_code or '',
            bank_account_holder=src.bank_account_holder or '',
            verification_status=src.verification_status,
            rejection_reason=src.rejection_reason or '',
            verified_at=src.verified_at,
            verified_by=src.verified_by,
            total_sales=src.total_sales,
            total_orders=src.total_orders,
            average_rating=src.average_rating,
            total_reviews=src.total_reviews,
            commission_rate=src.commission_rate,
            store_active=src.store_active,
            accepts_returns=src.accepts_returns,
            return_window_days=src.return_window_days,
            opening_hours=src.opening_hours or {},
            is_temporarily_closed=src.is_temporarily_closed,
            created_at=src.created_at,
            updated_at=src.updated_at,
        )

    for src in Business.objects.all():
        if VendorProfile.objects.filter(user=src.user).exists():
            continue
        VendorProfile.objects.create(
            user=src.user,
            profile_type='business',
            business_category=src.business_category,
            business_type=src.business_type or '',
            name=src.business_name,
            trading_name=src.business_trading_name or '',
            description=src.business_description or '',
            logo=src.business_logo or None,
            website=src.business_website or '',
            qr_code=src.qr_code or None,
            qr_code_identifier=src.qr_code_identifier,
            cipc_registration_number=src.cipc_registration_number or '',
            cipc_document=src.cipc_document or None,
            tax_number=src.tax_number or '',
            tax_clearance_certificate=src.tax_clearance_certificate or None,
            vat_number=src.vat_number or '',
            bee_certificate=src.bee_certificate or None,
            owner_full_name=src.owner_full_name or '',
            owner_id_number=src.owner_id_number or '',
            owner_id_document=src.owner_id_document or None,
            owner_proof_of_address=src.owner_proof_of_address or None,
            street_address=src.business_street_address or '',
            city=src.business_city or '',
            province=src.business_province or '',
            postal_code=src.business_postal_code or '',
            country=src.business_country or 'South Africa',
            latitude=src.latitude,
            longitude=src.longitude,
            bank_name=src.bank_name or '',
            bank_account_number=src.bank_account_number or '',
            bank_branch_code=src.bank_branch_code or '',
            bank_account_holder=src.bank_account_holder or '',
            verification_status=src.verification_status,
            owner_vetting_passed=src.owner_vetting_passed,
            business_vetting_passed=src.business_vetting_passed,
            rejection_reason=src.rejection_reason or '',
            verified_at=src.verified_at,
            verified_by=src.verified_by,
            total_sales=src.total_sales,
            total_orders=src.total_orders,
            average_rating=src.average_rating,
            total_reviews=src.total_reviews,
            commission_rate=src.commission_rate,
            store_active=src.store_active,
            accepts_returns=src.accepts_returns,
            return_window_days=src.return_window_days,
            opening_hours=src.opening_hours or {},
            is_temporarily_closed=src.is_temporarily_closed,
            created_at=src.created_at,
            updated_at=src.updated_at,
        )


def copy_backward(apps, schema_editor):
    VendorProfile = apps.get_model('business', 'VendorProfile')
    VendorProfile.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [('business', '0007_add_vendorprofile')]
    operations = [migrations.RunPython(copy_forward, reverse_code=copy_backward)]
