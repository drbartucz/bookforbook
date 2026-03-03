from django.urls import path

from . import views

urlpatterns = [
    path('', views.DonationListView.as_view(), name='donation-list'),
    path('offer/', views.DonationOfferView.as_view(), name='donation-offer'),
    path('<uuid:pk>/accept/', views.DonationAcceptView.as_view(), name='donation-accept'),
    path('<uuid:pk>/decline/', views.DonationDeclineView.as_view(), name='donation-decline'),
]
