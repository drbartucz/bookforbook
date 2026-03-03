from django.urls import path

from . import views

urlpatterns = [
    path('', views.WishlistView.as_view(), name='wishlist-list'),
    path('<uuid:pk>/', views.WishlistItemDetailView.as_view(), name='wishlist-detail'),
]
