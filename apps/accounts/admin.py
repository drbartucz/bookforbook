from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.inventory.models import UserBook, WishlistItem

from .models import User


class BooksOfferedInline(admin.TabularInline):
    model = UserBook
    fields = ("book", "condition", "status", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False
    ordering = ("-created_at",)
    verbose_name = "Book Offered"
    verbose_name_plural = "Books Offered"

    def has_add_permission(self, request, obj=None):
        return False


class BooksWantedInline(admin.TabularInline):
    model = WishlistItem
    fields = ("book", "min_condition", "wishlist_status", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False
    ordering = ("-created_at",)
    verbose_name = "Book Wanted"
    verbose_name_plural = "Books Wanted"

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Status")
    def wishlist_status(self, obj):
        return "Active" if obj.is_active else "Inactive"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email",
        "username",
        "account_type",
        "is_verified",
        "email_verified",
        "address_verification_label",
        "is_active",
        "total_trades",
        "created_at",
    ]
    list_filter = [
        "account_type",
        "is_verified",
        "email_verified",
        "address_verification_status",
        "is_active",
        "is_staff",
    ]
    search_fields = ["email", "username", "institution_name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at", "last_active_at"]
    inlines = [BooksOfferedInline, BooksWantedInline]

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
        (
            "Address Verification",
            {
                "fields": (
                    "address_verification_status",
                    "address_verified_at",
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

    @admin.display(
        description="Address verification",
        ordering="address_verification_status",
    )
    def address_verification_label(self, obj):
        return obj.get_address_verification_status_display()

    class Media:
        js = ("admin/accounts/user_admin.js",)
