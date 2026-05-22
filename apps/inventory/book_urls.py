from django.urls import path

from . import views

urlpatterns = [
    path('', views.MyBooksView.as_view(), name='my-books-list'),
    path('<uuid:pk>/', views.MyBookDetailView.as_view(), name='my-book-detail'),
    path('<uuid:pk>/wanted-by/', views.BookWantedByView.as_view(), name='my-book-wanted-by'),
]
