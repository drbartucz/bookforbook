import requests
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.db.models import Q
from rest_framework import permissions, status, throttling
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer
from .email import send_support_contact_email


class NotificationListView(APIView):
    """GET /api/v1/notifications/ — user's notifications."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            return Response(
                {"detail": "page and page_size must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if page < 1 or page_size < 1:
            return Response(
                {"detail": "page and page_size must be greater than 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        page_size = min(page_size, 100)

        base_qs = Notification.objects.filter(user=request.user).order_by("-created_at")
        total_count = base_qs.count()
        start = (page - 1) * page_size
        end = start + page_size

        notifications = base_qs[start:end]
        return Response(
            {
                "count": total_count,
                "page": page,
                "page_size": page_size,
                "results": NotificationSerializer(notifications, many=True).data,
            }
        )


class PendingCountsView(APIView):
    """GET /api/v1/notifications/counts/ — consolidated badge counts for navbar."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.matching.models import Match, MatchLeg
        from apps.trading.models import TradeProposal

        pending_matches = (
            MatchLeg.objects.filter(
                match__status__in=[Match.Status.PENDING, Match.Status.PROPOSED]
            )
            .filter(Q(sender=request.user) | Q(receiver=request.user))
            .values("match_id")
            .distinct()
            .count()
        )
        pending_proposals = TradeProposal.objects.filter(
            recipient=request.user,
            status=TradeProposal.Status.PENDING,
        ).count()
        unread_notifications = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()

        return Response(
            {
                "pending_matches": pending_matches,
                "pending_proposals": pending_proposals,
                "unread_notifications": unread_notifications,
                "total_pending": pending_matches + pending_proposals,
            }
        )


class NotificationMarkReadView(APIView):
    """POST /api/v1/notifications/:id/read/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadView(APIView):
    """POST /api/v1/notifications/read-all/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        now = timezone.now()
        updated = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True, read_at=now
        )
        return Response({"detail": f"{updated} notification(s) marked as read."})


class ContactSupportThrottle(throttling.SimpleRateThrottle):
    """
    IP-based throttle that applies to all requests regardless of authentication
    status. AnonRateThrottle would skip authenticated users; this does not.
    """

    scope = "contact_support"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class ContactSupportView(APIView):
    """
    POST /api/v1/notifications/contact/
    Public endpoint to send support messages.
    Protected by Cloudflare Turnstile and DRF throttling.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [ContactSupportThrottle]

    def post(self, request):
        name = request.data.get("name", "").strip()
        email = request.data.get("email", "").strip()
        message = request.data.get("message", "").strip()
        turnstile_token = request.data.get("turnstile_token", "").strip()

        if not all([name, email, message, turnstile_token]):
            return Response(
                {"detail": "All fields are required, including the captcha."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if any(c in name for c in ("\n", "\r")) or any(c in email for c in ("\n", "\r")):
            return Response(
                {"detail": "Invalid characters in name or email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(email)
        except DjangoValidationError:
            return Response(
                {"detail": "Invalid email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify Turnstile token
        try:
            verify_res = requests.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": settings.TURNSTILE_SECRET_KEY,
                    "response": turnstile_token,
                    "remoteip": request.META.get("REMOTE_ADDR"),
                },
                timeout=5,
            )
            verify_res.raise_for_status()
            verify_data = verify_res.json()
        except requests.RequestException:
            return Response(
                {"detail": "Verification service unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not verify_data.get("success"):
            return Response(
                {"detail": "Captcha verification failed. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Send email
        success = send_support_contact_email(name, email, message)
        if success:
            return Response({"detail": "Message sent successfully!"})
        else:
            return Response(
                {"detail": "Failed to send message. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
