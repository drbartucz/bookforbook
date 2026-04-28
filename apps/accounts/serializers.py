from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .disposable_email_domains import DISPOSABLE_EMAIL_DOMAINS
from .models import CONTINENTAL_US_STATES, User
from .tokens import email_verification_token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "username",
            "password",
            "password2",
            "account_type",
            "institution_name",
            "institution_url",
        ]

    def validate_email(self, value: str) -> str:
        domain = value.rsplit("@", 1)[-1].lower()
        if domain in DISPOSABLE_EMAIL_DOMAINS:
            raise serializers.ValidationError(
                "Registration with disposable email addresses is not allowed. "
                "Please use a permanent email address."
            )
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        account_type = attrs.get("account_type", User.AccountType.INDIVIDUAL)
        if account_type in (User.AccountType.LIBRARY, User.AccountType.BOOKSTORE):
            if not attrs.get("institution_name"):
                raise serializers.ValidationError(
                    {
                        "institution_name": "Institution name is required for libraries and bookstores."
                    }
                )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        user = authenticate(
            request=self.context.get("request"), username=email, password=password
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.email_verified:
            raise serializers.ValidationError(
                "Email address not verified. Please check your inbox."
            )
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        attrs["user"] = user
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uid": "Invalid verification link."})

        if not email_verification_token.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired token."})

        attrs["user"] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        # Always return success even if email not found (security)
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    new_password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password": "Passwords do not match."}
            )
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uid": "Invalid reset link."})

        from django.contrib.auth.tokens import default_token_generator

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired token."})

        attrs["user"] = user
        return attrs


class UserPublicProfileSerializer(serializers.ModelSerializer):
    """Public profile — no address, no private fields."""

    offered_count = serializers.IntegerField(read_only=True)
    wanted_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "account_type",
            "is_verified",
            "institution_name",
            "institution_url",
            "total_trades",
            "offered_count",
            "wanted_count",
            "avg_recent_rating",
            "rating_count",
            "created_at",
        ]
        read_only_fields = fields


class UserMeSerializer(serializers.ModelSerializer):
    """Authenticated user's own profile — includes address."""

    max_active_matches = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "username",
            "account_type",
            "is_verified",
            "email_verified",
            "email_verified_at",
            "institution_name",
            "institution_url",
            "full_name",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "zip_code",
            "address_verification_status",
            "address_verified_at",
            "total_trades",
            "avg_recent_rating",
            "rating_count",
            "max_active_matches",
            "inactivity_warned_1m",
            "inactivity_warned_2m",
            "books_delisted_at",
            "created_at",
            "updated_at",
            "last_active_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "email_verified",
            "email_verified_at",
            "is_verified",
            "total_trades",
            "avg_recent_rating",
            "rating_count",
            "max_active_matches",
            "inactivity_warned_1m",
            "inactivity_warned_2m",
            "books_delisted_at",
            "created_at",
            "updated_at",
            "last_active_at",
            "address_verified_at",
        ]


class UserMeUpdateSerializer(serializers.ModelSerializer):
    """PATCH — only updatable fields."""

    class Meta:
        model = User
        fields = [
            "username",
            "institution_name",
            "institution_url",
            "full_name",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "zip_code",
        ]

    def validate_state(self, value):
        if value and value.upper() not in CONTINENTAL_US_STATES:
            raise serializers.ValidationError(
                f"{value} is not a valid continental US state code."
            )
        return value.upper() if value else value

    def validate_zip_code(self, value):
        import re

        if value and not re.match(r"^\d{5}(-\d{4})?$", value):
            raise serializers.ValidationError(
                "Enter a valid US ZIP code (e.g. 12345 or 12345-6789)."
            )
        return value


class AccountDeletionSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value


class AddressVerificationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    address_line_1 = serializers.CharField(max_length=255)
    address_line_2 = serializers.CharField(
        max_length=255, allow_blank=True, required=False
    )
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=2)
    zip_code = serializers.CharField(max_length=10)

    def validate_state(self, value):
        value = (value or "").upper()
        if value not in CONTINENTAL_US_STATES:
            raise serializers.ValidationError(
                f"{value} is not a valid continental US state code."
            )
        return value

    def validate_zip_code(self, value):
        import re

        if not re.match(r"^\d{5}(-\d{4})?$", value):
            raise serializers.ValidationError(
                "Enter a valid US ZIP code (e.g. 12345 or 12345-6789)."
            )
        return value
