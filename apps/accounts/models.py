import uuid

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField


CONTINENTAL_US_STATES = [
    "AL",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
]

STATE_CHOICES = [(s, s) for s in CONTINENTAL_US_STATES]


class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        if not username:
            raise ValueError("Users must have a username")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_verified", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class AddressVerificationStatus(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        VERIFIED = "verified", "Verified"
        FAILED = "failed", "Failed"

    class AccountType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        LIBRARY = "library", "Library"
        BOOKSTORE = "bookstore", "Bookstore"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    username = models.CharField(max_length=150, unique=True, db_index=True)
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.INDIVIDUAL,
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Admin-approved for institutional accounts.",
    )
    institution_name = models.CharField(max_length=255, null=True, blank=True)
    institution_url = models.URLField(null=True, blank=True)

    # Shipping info — encrypted at rest
    full_name = EncryptedCharField(max_length=255, blank=True, default="")
    address_line_1 = EncryptedCharField(max_length=255, blank=True, default="")
    address_line_2 = EncryptedCharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(
        max_length=2, choices=STATE_CHOICES, blank=True, default=""
    )
    zip_code = models.CharField(max_length=10, blank=True, default="")
    address_verification_status = models.CharField(
        max_length=20,
        choices=AddressVerificationStatus.choices,
        default=AddressVerificationStatus.UNVERIFIED,
    )
    address_verified_at = models.DateTimeField(null=True, blank=True)

    # Public stats (denormalized)
    total_trades = models.PositiveIntegerField(default=0)
    avg_recent_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )
    rating_count = models.PositiveIntegerField(default=0)

    # Inactivity tracking
    inactivity_warned_1m = models.DateTimeField(null=True, blank=True)
    inactivity_warned_2m = models.DateTimeField(null=True, blank=True)
    books_delisted_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active_at = models.DateTimeField(auto_now_add=True)

    # Django admin flags
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.username} <{self.email}>"

    def delete(self, *args, **kwargs):
        # simplejwt uses SET_NULL on OutstandingToken, so clean up tokens manually
        try:
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

            OutstandingToken.objects.filter(user=self).delete()
        except Exception:
            pass
        super().delete(*args, **kwargs)

    @property
    def max_active_matches(self):
        """Compute match capacity based on rating count."""
        return min(max(self.rating_count, 1), 10)

    @property
    def is_institutional(self):
        return self.account_type in (
            self.AccountType.LIBRARY,
            self.AccountType.BOOKSTORE,
        )

    @property
    def has_shipping_address(self) -> bool:
        return bool(
            self.full_name
            and self.address_line_1
            and self.city
            and self.state
            and self.zip_code
        )
