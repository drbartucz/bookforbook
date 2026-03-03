from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/users/', include('apps.accounts.user_urls')),
    path('api/v1/books/', include('apps.books.urls')),
    path('api/v1/my-books/', include('apps.inventory.book_urls')),
    path('api/v1/wishlist/', include('apps.inventory.wishlist_urls')),
    path('api/v1/matches/', include('apps.matching.urls')),
    path('api/v1/proposals/', include('apps.trading.proposal_urls')),
    path('api/v1/trades/', include('apps.trading.trade_urls')),
    path('api/v1/donations/', include('apps.donations.urls')),
    path('api/v1/institutions/', include('apps.accounts.institution_urls')),
    path('api/v1/browse/', include('apps.inventory.browse_urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
]
