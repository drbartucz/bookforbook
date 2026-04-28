import logging

from django.db import connection
from django.db.models import CharField, F, Func, Value
from django.db.models.functions import Cast, Coalesce, Lower
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User

from .models import UserBook, WishlistItem
from .serializers import (
    BrowseBookSerializer,
    BrowseWantedSerializer,
    UserBookCreateSerializer,
    UserBookSerializer,
    UserBookUpdateSerializer,
    WishlistItemCreateSerializer,
    WishlistItemSerializer,
    WishlistItemUpdateSerializer,
)

logger = logging.getLogger(__name__)


def _should_prompt_for_address(user) -> bool:
    if user.has_shipping_address:
        return False

    have_count = (
        UserBook.objects.filter(user=user)
        .exclude(status=UserBook.Status.REMOVED)
        .count()
    )
    want_count = WishlistItem.objects.filter(user=user).count()
    total_listings = have_count + want_count
    return total_listings == 1


def _primary_author(authors) -> str:
    if not authors:
        return ""
    if isinstance(authors, list):
        return str(authors[0]) if authors else ""
    return str(authors)


def _author_last_name(author: str) -> str:
    parts = author.strip().split()
    return parts[-1].lower() if parts else ""


def apply_book_sorting(queryset, sort_by: str, sort_order: str):
    """Apply supported sorting for inventory lists."""
    is_desc = sort_order == "desc"

    if sort_by == "title":
        ordering = "-book__title" if is_desc else "book__title"
        return queryset.order_by(ordering)

    if sort_by == "author":
        if connection.vendor == "postgresql":
            # Postgres path: keep sorting in SQL so pagination doesn't materialize
            # the full queryset in Python.
            primary_author = Lower(
                Coalesce(
                    Cast(F("book__authors__0"), CharField()),
                    Value(""),
                )
            )
            queryset = queryset.annotate(
                _primary_author=primary_author,
                _author_last_name=Func(
                    F("_primary_author"),
                    Value(r"^.*[[:space:]]+"),
                    Value(""),
                    function="regexp_replace",
                    output_field=CharField(),
                ),
            )
            ordering = ["_author_last_name", "_primary_author", "book__title"]
            if is_desc:
                ordering = ["-_author_last_name", "-_primary_author", "-book__title"]
            return queryset.order_by(*ordering)

        # SQLite fallback: preserve last-name behavior for tests/local dev.
        sorted_items = sorted(
            list(queryset),
            key=lambda item: (
                _author_last_name(_primary_author(item.book.authors)),
                _primary_author(item.book.authors).lower(),
                item.book.title.lower() if item.book.title else "",
            ),
            reverse=is_desc,
        )
        return sorted_items

    # Default: date added
    ordering = "-created_at" if is_desc else "created_at"
    return queryset.order_by(ordering)


class EmailVerifiedPermission(permissions.BasePermission):
    """Require that the user has verified their email."""

    message = "Email verification required to manage your book lists."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.email_verified
        )


class MyBooksView(APIView):
    permission_classes = [EmailVerifiedPermission]

    def get(self, request):
        queryset = (
            UserBook.objects.filter(user=request.user)
            .select_related("book")
            .exclude(status=UserBook.Status.REMOVED)
        )

        sort_by = request.query_params.get("sort_by", "created_at")
        sort_order = request.query_params.get("sort_order", "desc")
        queryset = apply_book_sorting(queryset, sort_by, sort_order)

        # Apply pagination
        paginator = PageNumberPagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = UserBookSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = UserBookCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user_book = serializer.save()

        # Trigger async matching scan
        try:
            from django_q.tasks import async_task

            async_task(
                "apps.matching.tasks.run_matching_for_new_item",
                user_book_id=str(user_book.pk),
            )
        except Exception:
            logger.exception(
                "Failed to queue matching task for user_book %s", user_book.pk
            )

        response = Response(
            UserBookSerializer(user_book).data, status=status.HTTP_201_CREATED
        )
        if _should_prompt_for_address(request.user):
            response["X-Address-Prompt"] = "add_now"
        return response


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
        if obj.status in (
            UserBook.Status.RESERVED,
            UserBook.Status.TRADED,
            UserBook.Status.DONATED,
        ):
            return Response(
                {
                    "detail": "Cannot remove a book that is currently reserved, traded, or donated."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.status = UserBook.Status.REMOVED
        obj.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class WishlistView(APIView):
    permission_classes = [EmailVerifiedPermission]

    def get(self, request):
        queryset = WishlistItem.objects.filter(user=request.user).select_related("book")

        sort_by = request.query_params.get("sort_by", "created_at")
        sort_order = request.query_params.get("sort_order", "desc")
        queryset = apply_book_sorting(queryset, sort_by, sort_order)

        # Apply pagination
        paginator = PageNumberPagination()
        paginated = paginator.paginate_queryset(queryset, request)
        serializer = WishlistItemSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = WishlistItemCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        item = serializer.save()

        # Trigger async matching scan
        try:
            from django_q.tasks import async_task

            async_task(
                "apps.matching.tasks.run_matching_for_new_item",
                wishlist_item_id=str(item.pk),
            )
        except Exception:
            logger.exception(
                "Failed to queue matching task for wishlist_item %s", item.pk
            )

        response = Response(
            WishlistItemSerializer(item).data, status=status.HTTP_201_CREATED
        )
        if _should_prompt_for_address(request.user):
            response["X-Address-Prompt"] = "add_now"
        return response


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
    Public endpoint to browse available books, grouped by title.
    Each result is a unique Book with copy_count and best available condition.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = BrowseBookSerializer

    def get_queryset(self):
        from apps.books.models import Book
        from django.db.models import (
            Case,
            Count,
            IntegerField,
            OuterRef,
            Q,
            Subquery,
            When,
        )

        condition_filter = self.request.query_params.get("condition", "").strip()
        q = self.request.query_params.get("q", "").strip()

        available_q = Q(status=UserBook.Status.AVAILABLE, user__is_active=True)
        if condition_filter:
            available_q &= Q(condition=condition_filter)
        available_book_ids = (
            UserBook.objects.filter(available_q)
            .values_list("book_id", flat=True)
            .distinct()
        )

        best_condition_sq = (
            UserBook.objects.filter(
                book=OuterRef("pk"),
                status=UserBook.Status.AVAILABLE,
                user__is_active=True,
            )
            .annotate(
                rank=Case(
                    When(Q(condition="new"), then=5),
                    When(Q(condition="like_new"), then=4),
                    When(Q(condition="very_good"), then=3),
                    When(Q(condition="good"), then=2),
                    When(Q(condition="acceptable"), then=1),
                    When(Q(condition="poor"), then=0),
                    default=0,
                    output_field=IntegerField(),
                )
            )
            .order_by("-rank")
            .values("condition")[:1]
        )

        qs = (
            Book.objects.filter(id__in=available_book_ids)
            .annotate(
                copy_count=Count(
                    "user_listings",
                    filter=Q(
                        user_listings__status=UserBook.Status.AVAILABLE,
                        user_listings__user__is_active=True,
                    ),
                    distinct=True,
                ),
                best_condition=Subquery(best_condition_sq),
            )
            .order_by("-copy_count", "-created_at")
        )

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(authors__icontains=q)
                | Q(isbn_13__icontains=q)
            )

        return qs


class BrowseWantedView(generics.ListAPIView):
    """
    GET /api/v1/browse/wanted/
    Public endpoint to browse books that users want, grouped by title.
    Each result is a unique Book with want_count.
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = BrowseWantedSerializer

    def get_queryset(self):
        from apps.books.models import Book
        from django.db.models import Count, Q

        q = self.request.query_params.get("q", "").strip()

        wanted_book_ids = (
            WishlistItem.objects.filter(is_active=True, user__is_active=True)
            .values_list("book_id", flat=True)
            .distinct()
        )

        qs = (
            Book.objects.filter(id__in=wanted_book_ids)
            .annotate(
                want_count=Count(
                    "wishlist_entries",
                    filter=Q(
                        wishlist_entries__is_active=True,
                        wishlist_entries__user__is_active=True,
                    ),
                    distinct=True,
                )
            )
            .order_by("-want_count", "-created_at")
        )

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(authors__icontains=q)
                | Q(isbn_13__icontains=q)
            )

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

        has_active_trade = (
            TradeShipment.objects.filter(
                trade__status__in=[
                    "confirmed",
                    "shipping",
                    "one_received",
                    "completed",
                ],
                sender=partner,
                receiver=request.user,
            ).exists()
            or TradeShipment.objects.filter(
                trade__status__in=[
                    "confirmed",
                    "shipping",
                    "one_received",
                    "completed",
                ],
                sender=request.user,
                receiver=partner,
            ).exists()
        )

        if not has_active_trade:
            return Response(
                {"detail": "You can only browse books of confirmed trade partners."},
                status=status.HTTP_403_FORBIDDEN,
            )

        books = (
            UserBook.objects.filter(
                user=partner,
                status=UserBook.Status.AVAILABLE,
            )
            .select_related("book")
            .order_by("-created_at")
        )

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

        return Response(
            {
                "book_id": str(book.id),
                "title": book.title,
                "page_count": book.page_count,
                **estimate,
            }
        )
