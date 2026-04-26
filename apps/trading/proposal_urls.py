from django.urls import path

from . import views

urlpatterns = [
    path('', views.ProposalListCreateView.as_view(), name='proposal-list-create'),
    path('<uuid:pk>/', views.ProposalDetailView.as_view(), name='proposal-detail'),
    path('<uuid:pk>/accept/', views.ProposalAcceptView.as_view(), name='proposal-accept'),
    path('<uuid:pk>/decline/', views.ProposalDeclineView.as_view(), name='proposal-decline'),
]
