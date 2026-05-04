from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class ContactRateThrottle(AnonRateThrottle, UserRateThrottle):
    """
    Combined throttle for the contact form.
    Applies to both anonymous and authenticated users using the same scope.
    """

    scope = "contact_support"

    def get_cache_key(self, request, view):
        # We want a single pool for this specific endpoint regardless of auth status
        # but UserRateThrottle and AnonRateThrottle have different logic.
        # Actually, let's just use a simple one.
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
