from django.urls import path

from . import views

urlpatterns = [
    path('', views.ProposalListView.as_view(), name='proposal-list'),
    path('new/', views.ProposalCreateView.as_view(), name='proposal-create'),
    path('<uuid:pk>/', views.ProposalDetailView.as_view(), name='proposal-detail'),
    path('<uuid:pk>/accept/', views.ProposalAcceptView.as_view(), name='proposal-accept'),
    path('<uuid:pk>/decline/', views.ProposalDeclineView.as_view(), name='proposal-decline'),
    path('<uuid:pk>/counter/', views.ProposalCounterView.as_view(), name='proposal-counter'),
]
