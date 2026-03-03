from django.urls import path

from . import views

urlpatterns = [
    path('', views.InstitutionListView.as_view(), name='institution-list'),
    path('<uuid:id>/', views.InstitutionDetailView.as_view(), name='institution-detail'),
    path('<uuid:id>/wanted/', views.InstitutionWantedView.as_view(), name='institution-wanted'),
]
