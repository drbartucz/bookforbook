from django.urls import path

from . import views
from apps.messaging.views import TradeMessageListView

urlpatterns = [
    path('', views.TradeListView.as_view(), name='trade-list'),
    path('<uuid:pk>/', views.TradeDetailView.as_view(), name='trade-detail'),
    path('<uuid:pk>/mark-shipped/', views.TradeMarkShippedView.as_view(), name='trade-mark-shipped'),
    path('<uuid:pk>/mark-received/', views.TradeMarkReceivedView.as_view(), name='trade-mark-received'),
    path('<uuid:pk>/rate/', views.TradeRateView.as_view(), name='trade-rate'),
    path('<uuid:pk>/messages/', TradeMessageListView.as_view(), name='trade-messages'),
]
