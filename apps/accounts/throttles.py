from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "auth_login"


class RegisterRateThrottle(AnonRateThrottle):
    scope = "auth_register"


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "auth_password_reset"


class EmailVerifyRateThrottle(AnonRateThrottle):
    scope = "auth_email_verify"


class PasswordResetConfirmRateThrottle(AnonRateThrottle):
    scope = "auth_reset_confirm"


class DataExportRateThrottle(UserRateThrottle):
    scope = "data_export"


class AccountDeletionRateThrottle(UserRateThrottle):
    scope = "account_deletion"
