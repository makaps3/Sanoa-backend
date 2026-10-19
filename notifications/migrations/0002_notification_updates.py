# Generated manually — adds inventory notifications preference and new notification types/categories

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
    ]

    operations = [
        # 1. Add inventory_notifications toggle to NotificationPreference
        migrations.AddField(
            model_name='notificationpreference',
            name='inventory_notifications',
            field=models.BooleanField(default=True),
        ),

        # 2. Update Notification.category choices — adds 'inventory'
        migrations.AlterField(
            model_name='notification',
            name='category',
            field=models.CharField(
                choices=[
                    ('order',        'Order'),
                    ('payment',      'Payment'),
                    ('subscription', 'Subscription'),
                    ('credit',       'Credit'),
                    ('negotiation',  'Negotiation'),
                    ('delivery',     'Delivery'),
                    ('social',       'Social'),
                    ('fraud',        'Fraud'),
                    ('account',      'Account'),
                    ('admin',        'Admin'),
                    ('inventory',    'Inventory'),
                ],
                max_length=20,
            ),
        ),

        # 3. Update Notification.notification_type choices — adds all new types
        migrations.AlterField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                max_length=40,
                choices=[
                    # Customer-facing — general
                    ('welcome',                    'Welcome'),
                    ('order_created',              'Order Created'),
                    ('order_processing',           'Order Processing'),
                    ('order_shipped',              'Order Shipped'),
                    ('order_delivered',            'Order Delivered'),
                    ('order_cancelled',            'Order Cancelled'),
                    ('order_refunded',             'Order Refunded'),
                    ('payment_success',            'Payment Successful'),
                    ('payment_failed',             'Payment Failed'),
                    ('subscription_created',       'Subscription Created'),
                    ('subscription_expiring',      'Subscription Expiring Soon'),
                    ('subscription_expired',       'Subscription Expired'),
                    ('subscription_past_due',      'Subscription Past Due'),
                    ('credit_account_created',     'Credit Account Created'),
                    ('credit_purchase_created',    'Credit Purchase Created'),
                    ('credit_repayment_received',  'Credit Repayment Received'),
                    ('credit_low_balance',         'Low Credit Balance'),
                    ('credit_overdue',             'Credit Payment Overdue'),
                    ('credit_suspended',           'Credit Account Suspended'),
                    ('credit_unsuspended',         'Credit Account Reactivated'),
                    ('negotiation_offer',          'New Negotiation Offer'),
                    ('negotiation_counter',        'Negotiation Counter-Offer'),
                    ('negotiation_accepted',       'Offer Accepted'),
                    ('negotiation_rejected',       'Offer Rejected'),
                    ('negotiation_reminder',       'Negotiation Expiry Reminder'),
                    ('negotiation_expired',        'Negotiation Expired'),
                    ('negotiation_agreed',         'Price Agreement Reached'),
                    ('delivery_assigned',          'Delivery Assigned'),
                    ('delivery_picked_up',         'Order Picked Up'),
                    ('delivery_in_transit',        'Order In Transit'),
                    ('delivery_completed',         'Delivery Completed'),
                    ('vendor_followed',            'Vendor Followed'),
                    ('vendor_unfollowed',          'Vendor Unfollowed'),
                    ('refund_requested',           'Refund Requested'),
                    ('refund_processed',           'Refund Processed'),
                    ('dispute_created',            'Dispute Opened'),
                    ('dispute_resolved',           'Dispute Resolved'),
                    # Vendor-facing — general
                    ('new_order',                      'New Order Received'),
                    ('new_follower',                   'New Follower'),
                    ('unfollowed_by',                  'Unfollowed By Customer'),
                    ('vendor_negotiation_offer',       'Offer Received from Buyer'),
                    ('vendor_negotiation_reminder',    'Pending Offer Reminder'),
                    ('vendor_payment_received',        'Payment Received'),
                    ('verification_approved',          'Verification Approved'),
                    ('verification_rejected',          'Verification Rejected'),
                    ('vendor_order_cancelled',         'Order Cancelled by Customer'),
                    ('vendor_refund_requested',        'Customer Refund Request'),
                    ('vendor_dispute',                 'Dispute Filed Against You'),
                    ('vendor_fraud_flagged',           'Account Flagged for Review'),
                    ('vendor_fraud_cleared',           'Fraud Review Cleared'),
                    # Vendor-facing — tier subscription
                    ('vendor_tier_activated',          'Business Tier Activated'),
                    ('vendor_tier_expiring',           'Business Tier Expiring Soon'),
                    ('vendor_tier_expired',            'Business Tier Expired'),
                    ('vendor_tier_past_due',           'Business Tier Payment Overdue'),
                    ('vendor_tier_cancelled',          'Business Tier Cancelled'),
                    # Vendor-facing — inventory
                    ('vendor_low_stock',               'Product Low Stock'),
                    ('vendor_out_of_stock',            'Product Out of Stock'),
                    # Vendor-facing — vetting
                    ('vendor_vetting_passed',          'Vetting Check Passed'),
                    ('vendor_vetting_failed',          'Vetting Check Failed'),
                    ('vendor_vetting_resubmit',        'Vetting Resubmission Required'),
                    # Admin-facing
                    ('admin_new_user',                 'New User Signup'),
                    ('admin_new_business',             'New Business Registered'),
                    ('admin_refund_pending',           'Refund Needs Approval'),
                    ('admin_dispute',                  'New Dispute Filed'),
                    ('admin_fraud_high',               'High Fraud Risk Detected'),
                    ('admin_fraud_critical',           'Critical Fraud Risk Detected'),
                    ('admin_credit_defaulted',         'Credit Default'),
                    ('admin_vendor_pending',           'Vendor Awaiting Verification'),
                    ('admin_vetting_submitted',        'Vetting Application Submitted'),
                    ('admin_payment_failed',           'Payment Transaction Failed'),
                    ('admin_tier_past_due',            'Vendor Tier Payment Overdue'),
                ],
            ),
        ),
    ]
