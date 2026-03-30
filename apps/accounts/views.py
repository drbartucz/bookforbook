import logging

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
    EmailVerificationSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UserMeSerializer,
    UserMeUpdateSerializer,
    UserPublicProfileSerializer,
)
from .tokens import email_verification_token

logger = logging.getLogger(__name__)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Send verification email asynchronously
        try:
            from django.conf import settings as django_settings
            logger.warning('DEBUG email backend: %s', django_settings.EMAIL_BACKEND)
            from django_q.tasks import async_task
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = email_verification_token.make_token(user)
            async_task('apps.notifications.tasks.send_verification_email', str(user.pk), uid, token)
        except Exception:
            logger.exception('Failed to queue verification email for user %s', user.pk)

        return Response(
            {'detail': 'Account created. Please verify your email address.'},
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        user.email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=['email_verified', 'email_verified_at'])
        return Response({'detail': 'Email verified successfully.'})


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserMeSerializer(user).data,
        })


class TokenRefreshView(BaseTokenRefreshView):
    """Thin wrapper around simplejwt's token refresh."""
    pass


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email, is_active=True)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            from django_q.tasks import async_task
            async_task('apps.notifications.tasks.send_password_reset_email', str(user.pk), uid, token)
        except User.DoesNotExist:
            pass  # Don't reveal if email exists

        return Response({'detail': 'If an account with that email exists, a reset link has been sent.'})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])
        return Response({'detail': 'Password reset successfully.'})


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
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        # Cancel active matches and proposals
        _cancel_user_active_matches(user)

        # Queue GDPR export + deletion
        try:
            from django_q.tasks import async_task
            async_task('apps.notifications.tasks.send_account_deletion_initiated', str(user.pk))
        except Exception:
            logger.exception('Failed to queue deletion notification for user %s', user.pk)

        # For now, deactivate the account (30-day grace period would require a scheduled task)
        user.is_active = False
        user.save(update_fields=['is_active'])

        return Response({'detail': 'Account deletion initiated. You will receive a data export by email.'})


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
    lookup_field = 'id'


class UserRatingsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, id):
        try:
            user = User.objects.get(pk=id, is_active=True)
        except User.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.ratings.models import Rating
        from apps.ratings.serializers import RatingSerializer
        ratings = Rating.objects.filter(rated=user).order_by('-created_at')[:10]
        serializer = RatingSerializer(ratings, many=True)
        return Response(serializer.data)


class InstitutionListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserPublicProfileSerializer

    def get_queryset(self):
        return User.objects.filter(
            account_type__in=[User.AccountType.LIBRARY, User.AccountType.BOOKSTORE],
            is_verified=True,
            is_active=True,
        ).order_by('institution_name')


class InstitutionDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = UserPublicProfileSerializer

    def get_queryset(self):
        return User.objects.filter(
            account_type__in=[User.AccountType.LIBRARY, User.AccountType.BOOKSTORE],
            is_verified=True,
            is_active=True,
        )

    lookup_field = 'id'


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
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        from apps.inventory.models import WishlistItem
        from apps.inventory.serializers import WishlistItemSerializer
        items = WishlistItem.objects.filter(user=institution, is_active=True).select_related('book')
        serializer = WishlistItemSerializer(items, many=True)
        return Response(serializer.data)


# Helper functions

def _cancel_user_active_matches(user):
    """Cancel all active matches and proposals for a user being deleted."""
    from apps.matching.models import Match, MatchLeg
    from apps.trading.models import TradeProposal

    # Cancel pending matches
    active_leg_match_ids = MatchLeg.objects.filter(
        sender=user, status__in=['pending', 'accepted']
    ).values_list('match_id', flat=True)
    Match.objects.filter(
        id__in=active_leg_match_ids, status__in=['pending', 'proposed']
    ).update(status='expired')

    # Cancel pending proposals
    TradeProposal.objects.filter(
        proposer=user, status__in=['pending', 'countered']
    ).update(status='cancelled')
    TradeProposal.objects.filter(
        recipient=user, status__in=['pending', 'countered']
    ).update(status='cancelled')


def _build_user_export(user):
    """Build a full JSON export of user data for GDPR compliance."""
    from apps.inventory.models import UserBook, WishlistItem
    from apps.ratings.models import Rating
    from apps.trading.models import Trade, TradeProposal

    export = {
        'profile': {
            'id': str(user.id),
            'email': user.email,
            'username': user.username,
            'account_type': user.account_type,
            'created_at': user.created_at.isoformat(),
            'total_trades': user.total_trades,
            'avg_recent_rating': str(user.avg_recent_rating) if user.avg_recent_rating else None,
        },
        'address': {
            'full_name': user.full_name,
            'address_line_1': user.address_line_1,
            'address_line_2': user.address_line_2,
            'city': user.city,
            'state': user.state,
            'zip_code': user.zip_code,
        },
        'books': [
            {
                'id': str(b.id),
                'isbn_13': b.book.isbn_13,
                'title': b.book.title,
                'condition': b.condition,
                'status': b.status,
                'created_at': b.created_at.isoformat(),
            }
            for b in UserBook.objects.filter(user=user).select_related('book')
        ],
        'wishlist': [
            {
                'id': str(w.id),
                'isbn_13': w.book.isbn_13,
                'title': w.book.title,
                'min_condition': w.min_condition,
                'is_active': w.is_active,
            }
            for w in WishlistItem.objects.filter(user=user).select_related('book')
        ],
        'ratings_given': [
            {
                'id': str(r.id),
                'trade_id': str(r.trade_id),
                'rated_username': r.rated.username,
                'score': r.score,
                'comment': r.comment,
                'created_at': r.created_at.isoformat(),
            }
            for r in Rating.objects.filter(rater=user).select_related('rated')
        ],
        'ratings_received': [
            {
                'id': str(r.id),
                'trade_id': str(r.trade_id),
                'score': r.score,
                'comment': r.comment,
                'book_condition_accurate': r.book_condition_accurate,
                'created_at': r.created_at.isoformat(),
            }
            for r in Rating.objects.filter(rated=user)
        ],
    }
    return export
