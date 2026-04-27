from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email",
        "username",
        "account_type",
        "is_verified",
        "email_verified",
        "is_active",
        "total_trades",
        "created_at",
    ]
    list_filter = [
        "account_type",
        "is_verified",
        "email_verified",
        "is_active",
        "is_staff",
    ]
    search_fields = ["email", "username", "institution_name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at", "last_active_at"]

    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "username",
                    "account_type",
                    "is_verified",
                    "institution_name",
                    "institution_url",
                )
            },
        ),
        (
            "Address (Encrypted)",
            {
                "fields": (
                    "full_name",
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "zip_code",
                )
            },
        ),
        ("Email Verification", {"fields": ("email_verified", "email_verified_at")}),
        ("Stats", {"fields": ("total_trades", "avg_recent_rating", "rating_count")}),
        (
            "Inactivity",
            {
                "fields": (
                    "inactivity_warned_1m",
                    "inactivity_warned_2m",
                    "books_delisted_at",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at", "last_active_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "username",
                    "password1",
                    "password2",
                    "account_type",
                ),
            },
        ),
    )

    class Media:
        js = ("admin/accounts/user_admin.js",)
