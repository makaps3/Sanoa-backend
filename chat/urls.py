from django.urls import path

from .views import (
    AdminConversationDetailView,
    AdminConversationsListView,
    ConversationByDeliveryJobView,
    ConversationDetailView,
    ConversationMarkReadView,
    ConversationMessagesView,
    MyConversationsView,
)

app_name = 'chat'

urlpatterns = [
    path('conversations/',
         MyConversationsView.as_view(),
         name='conversations'),
    path('conversations/by-delivery/<int:job_id>/',
         ConversationByDeliveryJobView.as_view(),
         name='conversation-by-delivery'),
    path('conversations/<uuid:conv_id>/',
         ConversationDetailView.as_view(),
         name='conversation-detail'),
    path('conversations/<uuid:conv_id>/messages/',
         ConversationMessagesView.as_view(),
         name='conversation-messages'),
    path('conversations/<uuid:conv_id>/read/',
         ConversationMarkReadView.as_view(),
         name='conversation-read'),

    # Platform admin oversight.
    path('admin/conversations/',
         AdminConversationsListView.as_view(),
         name='admin-conversations'),
    path('admin/conversations/<uuid:conv_id>/',
         AdminConversationDetailView.as_view(),
         name='admin-conversation-detail'),
]
