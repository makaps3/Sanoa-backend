from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TransactionViewSet,
    SubaccountViewSet,
    TransactionSplitViewSet,
    RefundViewSet,
    DisputeViewSet,
    PaymentLogViewSet,
    BankListView,
    ResolveAccountView,
    PaystackWebhookView,
    VendorPublicSubaccountView,
    VendorTransactionsView,
    VendorTransactionDetailView,
    VendorTransactionChargesView,
    VendorChargesSummaryView,
    VendorRefundsView,
    VendorDisputesView,
)
from .bank_views import (
    list_supported_banks,
    VendorRecipientView,
    DriverRecipientView,
    AdminApproveRecipientView,
)
from .wallet_views import (
    MyWalletView,
    MyWalletTransactionsView,
    MyPayoutsView,
    AdminWalletListView,
    AdminWalletDetailView,
    AdminWalletAdjustView,
    AdminWalletFreezeView,
    AdminWalletRecomputeView,
    AdminReleaseDriverEscrowView,
    AdminPayoutListView,
    AdminPayoutDetailView,
    AdminPayoutInitiateView,
    AdminPayoutRetryView,
    AdminRecipientListView,
    AdminRecipientDetailView,
    AdminMarketplaceOverviewView,
)

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'subaccounts', SubaccountViewSet, basename='subaccount')
router.register(r'splits', TransactionSplitViewSet, basename='transaction-split')
router.register(r'refunds', RefundViewSet, basename='refund')
router.register(r'disputes', DisputeViewSet, basename='dispute')
router.register(r'logs', PaymentLogViewSet, basename='payment-log')

urlpatterns = [
    path('', include(router.urls)),
    path('banks/', BankListView.as_view(), name='bank-list'),
    path('banks/resolve/', ResolveAccountView.as_view(), name='resolve-account'),
    path('webhooks/paystack/', PaystackWebhookView.as_view(), name='paystack-webhook'),
    # Vendor-scoped payment endpoints
    path('vendor/<uuid:vendor_uuid>/subaccount/', VendorPublicSubaccountView.as_view(), name='vendor-public-subaccount'),
    path('vendor/<uuid:vendor_uuid>/transactions/', VendorTransactionsView.as_view(), name='vendor-transactions'),
    path('vendor/<uuid:vendor_uuid>/transactions/<uuid:pk>/', VendorTransactionDetailView.as_view(), name='vendor-transaction-detail'),
    path('vendor/<uuid:vendor_uuid>/transactions/<uuid:pk>/charges/', VendorTransactionChargesView.as_view(), name='vendor-transaction-charges'),
    path('vendor/<uuid:vendor_uuid>/charges-summary/', VendorChargesSummaryView.as_view(), name='vendor-charges-summary'),
    path('vendor/<uuid:vendor_uuid>/refunds/', VendorRefundsView.as_view(), name='vendor-refunds'),
    path('vendor/<uuid:vendor_uuid>/disputes/', VendorDisputesView.as_view(), name='vendor-disputes'),

    # ── Marketplace bank verification + recipient management ────────
    #
    # New flow per the redesign: customers pay the platform, the
    # platform credits internal wallets, and scheduled payouts use
    # Paystack Transfer Recipients (RCP_xxx) to settle vendors and
    # drivers. The subaccount-based split flow above is being retired
    # — endpoints still exist for backwards compat but new vendors
    # should onboard via the recipient endpoints below.
    path('marketplace/banks/', list_supported_banks, name='mkt-bank-list'),
    path('marketplace/me/vendor-recipient/', VendorRecipientView.as_view(),
         name='mkt-vendor-recipient'),
    path('marketplace/me/driver-recipient/', DriverRecipientView.as_view(),
         name='mkt-driver-recipient'),
    path('marketplace/admin/recipients/<uuid:recipient_id>/approve/',
         AdminApproveRecipientView.as_view(), name='mkt-recipient-approve'),

    # Owner-facing wallet + payout endpoints (vendor or driver).
    path('marketplace/me/wallet/', MyWalletView.as_view(), name='mkt-my-wallet'),
    path('marketplace/me/wallet/transactions/',
         MyWalletTransactionsView.as_view(), name='mkt-my-wallet-transactions'),
    path('marketplace/me/payouts/', MyPayoutsView.as_view(), name='mkt-my-payouts'),

    # Admin: wallets
    path('marketplace/admin/overview/',
         AdminMarketplaceOverviewView.as_view(), name='mkt-admin-overview'),
    path('marketplace/admin/wallets/',
         AdminWalletListView.as_view(), name='mkt-admin-wallets'),
    path('marketplace/admin/wallets/<uuid:wallet_id>/',
         AdminWalletDetailView.as_view(), name='mkt-admin-wallet-detail'),
    path('marketplace/admin/wallets/<uuid:wallet_id>/adjust/',
         AdminWalletAdjustView.as_view(), name='mkt-admin-wallet-adjust'),
    path('marketplace/admin/wallets/<uuid:wallet_id>/freeze/',
         AdminWalletFreezeView.as_view(), {'action': 'freeze'},
         name='mkt-admin-wallet-freeze'),
    path('marketplace/admin/wallets/<uuid:wallet_id>/unfreeze/',
         AdminWalletFreezeView.as_view(), {'action': 'unfreeze'},
         name='mkt-admin-wallet-unfreeze'),
    path('marketplace/admin/wallets/<uuid:wallet_id>/recompute/',
         AdminWalletRecomputeView.as_view(),
         name='mkt-admin-wallet-recompute'),
    path('marketplace/admin/wallets/release-driver-escrow/',
         AdminReleaseDriverEscrowView.as_view(),
         name='mkt-admin-release-driver-escrow'),

    # Admin: payouts
    path('marketplace/admin/payouts/',
         AdminPayoutListView.as_view(), name='mkt-admin-payouts'),
    path('marketplace/admin/payouts/initiate/',
         AdminPayoutInitiateView.as_view(), name='mkt-admin-payout-initiate'),
    path('marketplace/admin/payouts/<uuid:payout_id>/',
         AdminPayoutDetailView.as_view(), name='mkt-admin-payout-detail'),
    path('marketplace/admin/payouts/<uuid:payout_id>/retry/',
         AdminPayoutRetryView.as_view(), name='mkt-admin-payout-retry'),

    # Admin: recipients
    path('marketplace/admin/recipients/',
         AdminRecipientListView.as_view(), name='mkt-admin-recipients'),
    path('marketplace/admin/recipients/<uuid:recipient_id>/',
         AdminRecipientDetailView.as_view(), name='mkt-admin-recipient-detail'),
]
