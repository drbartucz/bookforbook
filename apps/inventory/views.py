import logging

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from .models import UserBook, WishlistItem
from .serializers import (
    UserBookCreateSerializer,
    UserBookSerializer,
    UserBookUpdateSerializer,
    WishlistItemCreateSerializer,
    WishlistItemSerializer,
    WishlistItemUpdateSerializer,
)

logger = logging.getLogger(__name__)


class EmailVerifiedPermission(permissions.BasePermission):
    """Require that the user has verified their email."""
    message = 'Email verification required to manage your book lists.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.email_verified
        )


class MyBooksView(APIView):
    permission_classes = [EmailVerifiedPermission]

    def get(self, request):
        queryset = UserBook.objects.filter(
            user=request.user
        ).select_related('book').exclude(
            status=UserBook.Status.REMOVED
        ).order_by('-created_at')
        serializer = UserBookSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserBookCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user_book = serializer.save()

        # Trigger async matching scan
        try:
            from django_q.tasks import async_task
            async_task('apps.matching.tasks.run_matching_for_new_item', user_book_id=str(user_book.pk))
        except Exception:
            logger.exception('Failed to queue matching task for user_book %s', user_book.pk)

        return Response(UserBookSerializer(user_book).data, status=status.HTTP_201_CREATED)


class MyBookDetailView(APIView):
    permission_classes = [EmailVerifiedPermission]

    def get_object(self, request, pk):
        return get_object_or_404(UserBook, pk=pk, user=request.user)

    def get(self, request, pk):
        obj = self.get_object(request, pk)
        return Response(UserBookSerializer(obj).data)

    def patch(self, request, pk):
        obj = self.get_object(request, pk)
        serializer = UserBookUpdateSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserBookSerializer(obj).data)

    def delete(self, request, pk):
        obj = self.get_object(request, pk)
        if obj.status in (UserBook.Status.RESERVED, UserBook.Status.TRADED, UserBook.Status.DONATED):
            return Response(
                {'detail': 'Cannot remove a book that is currently reserved, traded, or donated.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.status = UserBook.Status.REMOVED
        obj.save(update_fields=['status'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class WishlistView(APIView):
    permission_classes = [EmailVerifiedPermission]

    def get(self, request):
        queryset = WishlistItem.objects.filter(
            user=request.user
        ).select_related('book').order_by('-created_at')
        serializer = WishlistItemSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WishlistItemCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()

        # Trigger async matching scan
        try:
            from django_q.tasks import async_task
            async_task('apps.matching.tasks.run_matching_for_new_item', wishlist_item_id=str(item.pk))
        except Exception:
            logger.exception('Failed to queue matching task for wishlist_item %s', item.pk)

        return Response(WishlistItemSerializer(item).data, status=status.HTTP_201_CREATED)


class WishlistItemDetailView(APIView):
    permission_classes = [EmailVerifiedPermission]

    def get_object(self, request, pk):
        return get_object_or_404(WishlistItem, pk=pk, user=request.user)

    def get(self, request, pk):
        obj = self.get_object(request, pk)
        return Response(WishlistItemSerializer(obj).data)

    def patch(self, request, pk):
        obj = self.get_object(request, pk)
        serializer = WishlistItemUpdateSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(WishlistItemSerializer(obj).data)

    def delete(self, request, pk):
        obj = self.get_object(request, pk)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BrowseAvailableView(generics.ListAPIView):
    """
    GET /api/v1/browse/available/
    Public endpoint to browse all available books for trade.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = UserBookSerializer

    def get_queryset(self):
        qs = UserBook.objects.filter(
            status=UserBook.Status.AVAILABLE,
        ).select_related('book', 'user').order_by('-created_at')

        q = self.request.query_params.get('q', '').strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(book__title__icontains=q)
                | Q(book__authors__icontains=q)
                | Q(book__isbn_13__icontains=q)
            )

        condition = self.request.query_params.get('condition')
        if condition:
            qs = qs.filter(condition=condition)

        return qs


class PartnerBooksView(APIView):
    """
    GET /api/v1/browse/partner/:user_id/books/
    Browse a confirmed trade partner's available books.
    Requires the requesting user to be in a confirmed trade with the partner.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        partner = get_object_or_404(User, pk=user_id, is_active=True)

        # Verify that the requesting user has a confirmed (or later) trade with this partner
        from apps.trading.models import Trade, TradeShipment
        has_active_trade = TradeShipment.objects.filter(
            trade__status__in=['confirmed', 'shipping', 'one_received', 'completed'],
            sender=partner,
            receiver=request.user,
        ).exists() or TradeShipment.objects.filter(
            trade__status__in=['confirmed', 'shipping', 'one_received', 'completed'],
            sender=request.user,
            receiver=partner,
        ).exists()

        if not has_active_trade:
            return Response(
                {'detail': 'You can only browse books of confirmed trade partners.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        books = UserBook.objects.filter(
            user=partner,
            status=UserBook.Status.AVAILABLE,
        ).select_related('book').order_by('-created_at')

        serializer = UserBookSerializer(books, many=True)
        return Response(serializer.data)


class ShippingEstimateView(APIView):
    """
    GET /api/v1/browse/shipping-estimate/:book_id/
    Get an estimated shipping cost for a book.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, book_id):
        from apps.books.models import Book
        book = get_object_or_404(Book, pk=book_id)

        from .services.shipping import estimate_shipping
        estimate = estimate_shipping(book.page_count)

        return Response({
            'book_id': str(book.id),
            'title': book.title,
            'page_count': book.page_count,
            **estimate,
        })
