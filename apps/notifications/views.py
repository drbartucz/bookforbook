from django.utils import timezone
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


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
