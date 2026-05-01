from rest_framework.permissions import BasePermission


class EmailVerifiedPermission(BasePermission):
    message = "You must verify your email address before performing this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.email_verified
        )
