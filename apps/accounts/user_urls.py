from django.urls import path

from . import views

urlpatterns = [
    path('me/', views.UserMeView.as_view(), name='user-me'),
    path('me/export/', views.UserMeExportView.as_view(), name='user-me-export'),
    path('<uuid:id>/', views.UserPublicProfileView.as_view(), name='user-public-profile'),
    path('<uuid:id>/ratings/', views.UserRatingsView.as_view(), name='user-ratings'),
]
