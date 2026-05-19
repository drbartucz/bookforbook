import pytest
from apps.trading.utils import is_valid_tracking_number


class TestIsValidTrackingNumber:
    def test_empty_string(self):
        assert is_valid_tracking_number("") is False

    def test_none_like_empty(self):
        assert is_valid_tracking_number("   ") is False

    def test_phone_number_rejected(self):
        assert is_valid_tracking_number("5551234567") is False

    def test_short_digits_rejected(self):
        assert is_valid_tracking_number("12345") is False

    def test_usps_valid(self):
        # 9 prefix + 22 digits total
        assert is_valid_tracking_number("9400100000000000000000") is True

    def test_ups_valid(self):
        assert is_valid_tracking_number("1Z999AA10123456784") is True

    def test_ups_lowercase(self):
        assert is_valid_tracking_number("1z999aa10123456784") is True

    def test_fedex_15_digit(self):
        assert is_valid_tracking_number("123456789012345") is True

    def test_fedex_prefix_96(self):
        assert is_valid_tracking_number("96" + "1" * 16) is True

    def test_garbage_string_rejected(self):
        assert is_valid_tracking_number("HELLO-WORLD") is False

    def test_usps_with_internal_spaces(self):
        # Copy-pasted with spaces between digit groups
        assert is_valid_tracking_number("9400 1000 0000 0000 0000 00") is True

    def test_ups_with_spaces(self):
        assert is_valid_tracking_number("1Z999 AA1 0123 456784") is True

    def test_trailing_whitespace(self):
        assert is_valid_tracking_number("1Z999AA10123456784   ") is True

    def test_leading_whitespace(self):
        assert is_valid_tracking_number("   1Z999AA10123456784") is True
