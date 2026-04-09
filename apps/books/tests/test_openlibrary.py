"""
Unit tests for the Open Library ISBN utilities.
"""
import pytest

from apps.books.services.openlibrary import (
    isbn10_to_isbn13,
    isbn13_to_isbn10,
    normalize_isbn,
    _validate_isbn10,
    _validate_isbn13,
)


class TestISBNConversion:
    def test_isbn10_to_isbn13_valid(self):
        # "The Pragmatic Programmer" ISBN-10: 020161622X → ISBN-13: 9780201616224
        result = isbn10_to_isbn13('020161622X')
        assert result == '9780201616224'

    def test_isbn10_to_isbn13_numeric_check(self):
        # ISBN-10: 0596007647 → ISBN-13: 9780596007645
        result = isbn10_to_isbn13('0596007647')
        assert result == '9780596007645'

    def test_isbn13_to_isbn10_valid(self):
        result = isbn13_to_isbn10('9780201616224')
        assert result == '020161622X'

    def test_validate_isbn10_valid(self):
        assert _validate_isbn10('020161622X') is True
        assert _validate_isbn10('0596007647') is True

    def test_validate_isbn10_invalid(self):
        assert _validate_isbn10('0201616220') is False

    def test_validate_isbn13_valid(self):
        assert _validate_isbn13('9780201616224') is True
        assert _validate_isbn13('9780596007645') is True

    def test_validate_isbn13_invalid(self):
        assert _validate_isbn13('9780000000000') is False

    def test_normalize_isbn10(self):
        result = normalize_isbn('020161622X')
        assert result == '9780201616224'

    def test_normalize_isbn13(self):
        result = normalize_isbn('9780201616224')
        assert result == '9780201616224'

    def test_normalize_isbn_with_dashes(self):
        result = normalize_isbn('978-0-201-61622-4')
        assert result == '9780201616224'

    def test_normalize_invalid_isbn(self):
        result = normalize_isbn('12345')
        assert result is None

    def test_normalize_empty_isbn(self):
        result = normalize_isbn('')
        assert result is None
