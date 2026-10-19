from django.urls import path

from . import views

urlpatterns = [
    # Buyer self-service (own risk score — transparency only)
    path('me/', views.MyFraudProfileView.as_view(), name='fraud-my-profile'),

    # Admin: profile list/detail/review
    path('profiles/',       views.FraudProfileListView.as_view(),   name='fraud-profile-list'),
    path('profiles/<int:pk>/', views.FraudProfileDetailView.as_view(), name='fraud-profile-detail'),

    # Admin: fraud event list + resolution
    path('events/',                        views.FraudEventListView.as_view(),  name='fraud-event-list'),
    path('events/<uuid:pk>/action/',       views.ResolveEventView.as_view(),    name='fraud-event-action'),

    # Admin: on-demand rescoring
    path('rescore/user/<int:user_id>/',    views.RescoreUserView.as_view(),     name='fraud-rescore-user'),
    path('rescore/vendor/<uuid:vendor_id>/', views.RescoreVendorView.as_view(), name='fraud-rescore-vendor'),

    # Admin: retrain XGBoost models
    path('train/', views.TrainModelsView.as_view(), name='fraud-train'),
]
