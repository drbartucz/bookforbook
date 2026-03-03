from django.urls import path

from . import views

urlpatterns = [
    path('lookup/', views.BookLookupView.as_view(), name='book-lookup'),
    path('search/', views.BookSearchView.as_view(), name='book-search'),
    path('<uuid:id>/', views.BookDetailView.as_view(), name='book-detail'),
]
