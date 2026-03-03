from django.urls import path

from . import views

urlpatterns = [
    path('available/', views.BrowseAvailableView.as_view(), name='browse-available'),
    path('partner/<uuid:user_id>/books/', views.PartnerBooksView.as_view(), name='browse-partner-books'),
    path('shipping-estimate/<uuid:book_id>/', views.ShippingEstimateView.as_view(), name='shipping-estimate'),
]
