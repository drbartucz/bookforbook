"""
Unit tests for the Open Library ISBN utilities.
"""

import pytest
from unittest.mock import patch

from apps.books.services.openlibrary import (
    get_or_create_book,
    isbn10_to_isbn13,
    isbn13_to_isbn10,
    normalize_isbn,
    _normalize_physical_format,
    _parse_isbn_response,
    _parse_search_result,
    _validate_isbn10,
    _validate_isbn13,
)


class TestISBNConversion:
    def test_isbn10_to_isbn13_valid(self):
        # "The Pragmatic Programmer" ISBN-10: 020161622X → ISBN-13: 9780201616224
        result = isbn10_to_isbn13("020161622X")
        assert result == "9780201616224"

    def test_isbn10_to_isbn13_numeric_check(self):
        # ISBN-10: 0596007647 → ISBN-13: 9780596007645
        result = isbn10_to_isbn13("0596007647")
        assert result == "9780596007645"

    def test_isbn13_to_isbn10_valid(self):
        result = isbn13_to_isbn10("9780201616224")
        assert result == "020161622X"

    def test_validate_isbn10_valid(self):
        assert _validate_isbn10("020161622X") is True
        assert _validate_isbn10("0596007647") is True

    def test_validate_isbn10_invalid(self):
        assert _validate_isbn10("0201616220") is False

    def test_validate_isbn13_valid(self):
        assert _validate_isbn13("9780201616224") is True
        assert _validate_isbn13("9780596007645") is True

    def test_validate_isbn13_invalid(self):
        assert _validate_isbn13("9780000000000") is False

    def test_normalize_isbn10(self):
        result = normalize_isbn("020161622X")
        assert result == "9780201616224"

    def test_normalize_isbn13(self):
        result = normalize_isbn("9780201616224")
        assert result == "9780201616224"

    def test_normalize_isbn_with_dashes(self):
        result = normalize_isbn("978-0-201-61622-4")
        assert result == "9780201616224"

    def test_normalize_invalid_isbn(self):
        result = normalize_isbn("12345")
        assert result is None

    def test_normalize_empty_isbn(self):
        result = normalize_isbn("")
        assert result is None


class TestOpenLibraryFormatParsing:
    def test_normalize_physical_format_list(self):
        assert _normalize_physical_format(["Paperback"]) == "Paperback"

    def test_normalize_physical_format_dict(self):
        assert _normalize_physical_format({"name": "Hardcover"}) == "Hardcover"

    def test_parse_isbn_response_extracts_physical_format(self):
        raw = {
            "title": "Example",
            "physical_format": "Mass Market Paperback",
            "authors": [],
        }
        parsed = _parse_isbn_response(raw, "9780201616224")
        assert parsed["physical_format"] == "Mass Market Paperback"

    def test_parse_search_result_extracts_physical_format(self):
        doc = {
            "title": "Example",
            "format": ["Hardcover"],
        }
        parsed = _parse_search_result(doc, "9780201616224")
        assert parsed["physical_format"] == "Hardcover"


@pytest.mark.django_db
def test_get_or_create_book_ignores_malformed_author_payload():
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    with patch(
        "apps.books.services.openlibrary.requests.get",
        side_effect=[
            FakeResponse(
                200,
                {
                    "title": "Example Book",
                    "authors": [{"key": "/authors/OL1A"}],
                },
            ),
            FakeResponse(200, ["unexpected"]),
        ],
    ):
        book = get_or_create_book("9780201616224")

    assert book.title == "Example Book"
    assert book.authors == []
