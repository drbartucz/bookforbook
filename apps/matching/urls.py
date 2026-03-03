from django.urls import path

from . import views

urlpatterns = [
    path('', views.MatchListView.as_view(), name='match-list'),
    path('<uuid:pk>/', views.MatchDetailView.as_view(), name='match-detail'),
    path('<uuid:pk>/accept/', views.MatchAcceptView.as_view(), name='match-accept'),
    path('<uuid:pk>/decline/', views.MatchDeclineView.as_view(), name='match-decline'),
]
