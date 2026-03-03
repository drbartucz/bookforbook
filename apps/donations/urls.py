from django.urls import path

from . import views

urlpatterns = [
    path('', views.DonationListCreateView.as_view(), name='donation-list-create'),
    path('<uuid:pk>/accept/', views.DonationAcceptView.as_view(), name='donation-accept'),
    path('<uuid:pk>/decline/', views.DonationDeclineView.as_view(), name='donation-decline'),
]
