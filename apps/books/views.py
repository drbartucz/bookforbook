import logging

from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import Book
from .serializers import BookLookupSerializer, BookSerializer, ImageBarcodeSerializer

logger = logging.getLogger(__name__)


class ISBNLookupThrottle(UserRateThrottle):
    scope = "isbn_lookup"


class BookLookupView(APIView):
    """
    POST /api/v1/books/lookup/
    Look up a book by ISBN. Creates the book record if not already cached.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ISBNLookupThrottle]

    def post(self, request):
        serializer = BookLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        isbn = serializer.validated_data["isbn"]

        try:
            from .services.openlibrary import get_or_create_book

            book = get_or_create_book(isbn)
            return Response(BookSerializer(book).data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("ISBN lookup failed for %s", isbn)
            return Response(
                {"detail": "Failed to look up book. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class ImageBarcodeView(APIView):
    """
    POST /api/v1/books/from-image/
    Backend fallback for barcode/ISBN extraction from an uploaded image.
    Accepts multipart/form-data with an 'image' field.
    Returns { isbn } on success, or 404 when no barcode is found.
    Callers should then hit /api/v1/books/lookup/ with the returned ISBN.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ISBNLookupThrottle]  # reuse same throttle scope
    parser_classes = [MultiPartParser]

    def post(self, request):
        serializer = ImageBarcodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image_file = serializer.validated_data["image"]

        try:
            from .services.barcode import extract_isbn_from_image

            isbn = extract_isbn_from_image(image_file)
        except ImportError:
            logger.warning("pyzbar not available; backend barcode extraction skipped")
            return Response(
                {"detail": "Barcode extraction is not available on this server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected error during image barcode extraction")
            return Response(
                {"detail": "Failed to process image. Please try again."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if isbn is None:
            return Response(
                {"detail": "No valid ISBN barcode found in the image."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"isbn": isbn}, status=status.HTTP_200_OK)


class BookDetailView(generics.RetrieveAPIView):
    """GET /api/v1/books/:id/"""

    permission_classes = [permissions.AllowAny]
    serializer_class = BookSerializer
    queryset = Book.objects.all()
    lookup_field = "id"


class BookSearchView(generics.ListAPIView):
    """GET /api/v1/books/search/?q=..."""

    permission_classes = [permissions.AllowAny]
    serializer_class = BookSerializer

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        if not q:
            return Book.objects.none()
        return Book.objects.filter(
            Q(title__icontains=q)
            | Q(authors__icontains=q)
            | Q(isbn_13__icontains=q)
            | Q(isbn_10__icontains=q)
            | Q(publisher__icontains=q)
        ).order_by("title")[:50]
