import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

from .models import User
from .serializers import (
    AccountDeletionSerializer,
    AddressVerificationSerializer,
    EmailVerificationSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserMeSerializer,
    UserMeUpdateSerializer,
    UserPublicProfileSerializer,
)
from .throttles import (
    LoginRateThrottle,
    PasswordResetRateThrottle,
    RegisterRateThrottle,
)
from .tokens import email_verification_token

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Send verification email asynchronously
        try:
            from django_q.tasks import async_task

            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = email_verification_token.make_token(user)
            async_task(
                "apps.notifications.tasks.send_verification_email",
                str(user.pk),
                uid,
                token,
            )
        except Exception:
            logger.exception("Failed to queue verification email for user %s", user.pk)

        return Response(
            {"detail": "Account created. Please verify your email address."},
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified", "email_verified_at"])
        return Response({"detail": "Email verified successfully."})


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserMeSerializer(user).data,
            }
        )


class TokenRefreshView(BaseTokenRefreshView):
    """Thin wrapper around simplejwt's token refresh."""

    pass


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            from rest_framework_simplejwt.tokens import RefreshToken

            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass  # Already expired or invalid — treat as logged out
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email, is_active=True)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            from django_q.tasks import async_task

            async_task(
                "apps.notifications.tasks.send_password_reset_email",
                str(user.pk),
                uid,
                token,
            )
        except User.DoesNotExist:
            pass  # Don't reveal if email exists

        return Response(
            {
                "detail": "If an account with that email exists, a reset link has been sent."
            }
        )


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password reset successfully."})


class UserMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserMeSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserMeUpdateSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserMeSerializer(request.user).data)

    def delete(self, request):
        serializer = AccountDeletionSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        if user.deletion_requested_at is not None:
            return Response(
                {"detail": "Account deletion has already been initiated."},
                status=status.HTTP_200_OK,
            )

        # Notify affected counterparties, then cancel active matches/proposals.
        _notify_affected_users_of_account_deletion(user)
        _cancel_user_active_matches(user)

        now = timezone.now()
        scheduled_for = now + timedelta(days=30)

        user.is_active = False
        user.deletion_requested_at = now
        user.deletion_scheduled_for = scheduled_for
        user.save(
            update_fields=[
                "is_active",
                "deletion_requested_at",
                "deletion_scheduled_for",
                "updated_at",
            ]
        )

        # Queue GDPR export + deletion confirmation email.
        try:
            from django_q.tasks import async_task

            async_task(
                "apps.notifications.tasks.send_account_deletion_initiated", str(user.pk)
            )
        except Exception:
            logger.exception(
                "Failed to queue deletion notification for user %s", user.pk
            )

        return Response(
            {
                "detail": "Account deletion initiated. You will receive a data export by email."
            }
        )


class UserAddressVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AddressVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .services.usps import USPSVerificationError, verify_address_with_usps

        user = request.user
        payload = serializer.validated_data
        try:
            normalized = verify_address_with_usps(
                address_line_1=payload["address_line_1"],
                address_line_2=payload.get("address_line_2", ""),
                city=payload["city"],
                state=payload["state"],
                zip_code=payload["zip_code"],
            )
        except USPSVerificationError as exc:
            user.address_verification_status = User.AddressVerificationStatus.FAILED
            user.save(update_fields=["address_verification_status", "updated_at"])
            return Response(
                {
                    "detail": str(exc),
                    "code": "address_verification_failed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.full_name = payload["full_name"]
        user.address_line_1 = normalized["address_line_1"]
        user.address_line_2 = normalized["address_line_2"]
        user.city = normalized["city"]
        user.state = normalized["state"]
        user.zip_code = normalized["zip_code"]
        user.address_verification_status = User.AddressVerificationStatus.VERIFIED
        user.address_verified_at = timezone.now()
        user.save(
            update_fields=[
                "full_name",
                "address_line_1",
                "address_line_2",
                "city",
                "state",
                "zip_code",
                "address_verification_status",
                "address_verified_at",
                "updated_at",
            ]
        )

        return Response(UserMeSerializer(user).data, status=status.HTTP_200_OK)


class UserMeExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        data = _build_user_export(user)
        return Response(data)


class UserPublicProfileView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserPublicProfileSerializer
    queryset = User.objects.filter(is_active=True)
    lookup_field = "id"


class UserRatingsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, id):
        try:
            user = User.objects.get(pk=id, is_active=True)
        except User.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from apps.ratings.models import Rating
        from apps.ratings.serializers import RatingSerializer

        ratings = Rating.objects.filter(rated=user).order_by("-created_at")[:10]
        serializer = RatingSerializer(ratings, many=True)
        return Response(serializer.data)


class UserOfferedBooksView(APIView):
    """
    GET /api/v1/users/:id/offered/
    Public endpoint returning a user's available books (have-list).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, id):
        try:
            user = User.objects.get(pk=id, is_active=True)
        except User.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from apps.inventory.models import UserBook
        from apps.inventory.serializers import UserBookSerializer

        books = (
            UserBook.objects.filter(user=user, status=UserBook.Status.AVAILABLE)
            .select_related("book")
            .order_by("-created_at")
        )
        serializer = UserBookSerializer(books, many=True)
        return Response(serializer.data)


class UserWantedBooksView(APIView):
    """
    GET /api/v1/users/:id/wanted/
    Public endpoint returning a user's active wishlist items (want-list).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, id):
        try:
            user = User.objects.get(pk=id, is_active=True)
        except User.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from apps.inventory.models import WishlistItem
        from apps.inventory.serializers import WishlistItemSerializer

        items = (
            WishlistItem.objects.filter(user=user, is_active=True)
            .select_related("book")
            .order_by("-created_at")
        )
        serializer = WishlistItemSerializer(items, many=True)
        return Response(serializer.data)


class InstitutionListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserPublicProfileSerializer

    def get_queryset(self):
        from django.db.models import Q

        qs = User.objects.filter(
            account_type__in=[User.AccountType.LIBRARY, User.AccountType.BOOKSTORE],
            is_verified=True,
            is_active=True,
        ).order_by("institution_name")

        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(institution_name__icontains=search)
                | Q(username__icontains=search)
                | Q(full_name__icontains=search)
            )

        institution_type = self.request.query_params.get("institution_type", "").strip()
        if institution_type:
            qs = qs.filter(account_type=institution_type)

        return qs


class InstitutionDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserPublicProfileSerializer

    def get_queryset(self):
        return User.objects.filter(
            account_type__in=[User.AccountType.LIBRARY, User.AccountType.BOOKSTORE],
            is_verified=True,
            is_active=True,
        )

    lookup_field = "id"


class InstitutionWantedView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, id):
        try:
            institution = User.objects.get(
                pk=id,
                account_type__in=[User.AccountType.LIBRARY, User.AccountType.BOOKSTORE],
                is_verified=True,
                is_active=True,
            )
        except User.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from apps.inventory.models import WishlistItem
        from apps.inventory.serializers import WishlistItemSerializer

        items = WishlistItem.objects.filter(
            user=institution, is_active=True
        ).select_related("book")
        serializer = WishlistItemSerializer(items, many=True)
        return Response(serializer.data)


# Helper functions


def _cancel_user_active_matches(user):
    """Cancel all active matches and proposals for a user being deleted."""
    from django.db.models import Q

    from apps.matching.models import Match, MatchLeg
    from apps.trading.models import TradeProposal

    # Cancel pending/proposed matches where user is either sender or receiver.
    active_leg_match_ids = MatchLeg.objects.filter(
        Q(sender=user) | Q(receiver=user),
        status__in=[MatchLeg.Status.PENDING, MatchLeg.Status.ACCEPTED],
    ).values_list("match_id", flat=True)
    Match.objects.filter(
        id__in=active_leg_match_ids,
        status__in=[Match.Status.PENDING, Match.Status.PROPOSED],
    ).update(status=Match.Status.EXPIRED)

    # Cancel pending/countered proposals where user is either side.
    TradeProposal.objects.filter(
        Q(proposer=user) | Q(recipient=user),
        status__in=[TradeProposal.Status.PENDING, TradeProposal.Status.COUNTERED],
    ).update(status=TradeProposal.Status.CANCELLED)


def _notify_affected_users_of_account_deletion(user):
    """Notify counterparties that active interactions were cancelled due to deletion."""
    from django.db.models import Q

    from apps.matching.models import MatchLeg
    from apps.notifications.models import Notification
    from apps.trading.models import TradeProposal

    counterparty_ids = set()

    active_legs = MatchLeg.objects.filter(
        Q(sender=user) | Q(receiver=user),
        status__in=[MatchLeg.Status.PENDING, MatchLeg.Status.ACCEPTED],
    ).values_list("sender_id", "receiver_id")
    for sender_id, receiver_id in active_legs:
        if sender_id != user.id:
            counterparty_ids.add(sender_id)
        if receiver_id != user.id:
            counterparty_ids.add(receiver_id)

    active_proposals = TradeProposal.objects.filter(
        Q(proposer=user) | Q(recipient=user),
        status__in=[TradeProposal.Status.PENDING, TradeProposal.Status.COUNTERED],
    ).values_list("proposer_id", "recipient_id")
    for proposer_id, recipient_id in active_proposals:
        if proposer_id != user.id:
            counterparty_ids.add(proposer_id)
        if recipient_id != user.id:
            counterparty_ids.add(recipient_id)

    if not counterparty_ids:
        return

    Notification.objects.bulk_create(
        [
            Notification(
                user_id=counterparty_id,
                notification_type="account_deleted_impact",
                title="A user left BookForBook",
                body="An active match or proposal was cancelled because the other user deleted their account.",
                metadata={"deleted_user_id": str(user.pk)},
            )
            for counterparty_id in counterparty_ids
        ]
    )


def _build_user_export(user):
    """Build a full JSON export of user data for GDPR compliance."""
    from apps.inventory.models import UserBook, WishlistItem
    from apps.ratings.models import Rating
    from apps.trading.models import Trade, TradeProposal

    export = {
        "profile": {
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "account_type": user.account_type,
            "created_at": user.created_at.isoformat(),
            "total_trades": user.total_trades,
            "avg_recent_rating": (
                str(user.avg_recent_rating) if user.avg_recent_rating else None
            ),
        },
        "address": {
            "full_name": user.full_name,
            "address_line_1": user.address_line_1,
            "address_line_2": user.address_line_2,
            "city": user.city,
            "state": user.state,
            "zip_code": user.zip_code,
        },
        "books": [
            {
                "id": str(b.id),
                "isbn_13": b.book.isbn_13,
                "title": b.book.title,
                "condition": b.condition,
                "status": b.status,
                "created_at": b.created_at.isoformat(),
            }
            for b in UserBook.objects.filter(user=user).select_related("book")
        ],
        "wishlist": [
            {
                "id": str(w.id),
                "isbn_13": w.book.isbn_13,
                "title": w.book.title,
                "min_condition": w.min_condition,
                "is_active": w.is_active,
            }
            for w in WishlistItem.objects.filter(user=user).select_related("book")
        ],
        "ratings_given": [
            {
                "id": str(r.id),
                "trade_id": str(r.trade_id),
                "rated_username": r.rated.username,
                "score": r.score,
                "comment": r.comment,
                "created_at": r.created_at.isoformat(),
            }
            for r in Rating.objects.filter(rater=user).select_related("rated")
        ],
        "ratings_received": [
            {
                "id": str(r.id),
                "trade_id": str(r.trade_id),
                "score": r.score,
                "comment": r.comment,
                "book_condition_accurate": r.book_condition_accurate,
                "created_at": r.created_at.isoformat(),
            }
            for r in Rating.objects.filter(rated=user)
        ],
    }
    return export


def user_has_verified_shipping_address(user: User) -> bool:
    return (
        user.has_shipping_address
        and user.address_verification_status == User.AddressVerificationStatus.VERIFIED
    )
