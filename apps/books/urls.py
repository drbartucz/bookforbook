from django.urls import path

from . import views

urlpatterns = [
    path("lookup/", views.BookLookupView.as_view(), name="book-lookup"),
    path("from-image/", views.ImageBarcodeView.as_view(), name="book-from-image"),
    path("search/", views.BookSearchView.as_view(), name="book-search"),
    path("<uuid:id>/", views.BookDetailView.as_view(), name="book-detail"),
]
