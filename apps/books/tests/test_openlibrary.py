"""
Unit tests for the Open Library ISBN utilities.
"""

import pytest
from unittest.mock import patch

from apps.books.services.openlibrary import (
    fetch_from_open_library,
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
from apps.tests.factories import BookFactory


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


def test_fetch_from_open_library_enriches_missing_author_and_format_from_search_and_edition():
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
                    "title": "The Food Lab: Better Home Cooking Through Science",
                    "authors": [],
                    "works": [],
                },
            ),
            FakeResponse(
                200,
                {
                    "docs": [
                        {
                            "title": "The Food Lab",
                            "author_name": ["J. Kenji L\u00f3pez-Alt"],
                            "cover_edition_key": "OL26629978M",
                        }
                    ]
                },
            ),
            FakeResponse(
                200,
                {
                    "physical_format": "Hardcover",
                    "authors": [{"key": "/authors/OL7442728A"}],
                },
            ),
            FakeResponse(200, {"name": "J. Kenji L\u00f3pez-Alt"}),
        ],
    ):
        data = fetch_from_open_library("9780393081084")

    assert data["authors"] == ["J. Kenji L\u00f3pez-Alt"]
    assert data["physical_format"] == "Hardcover"


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
            FakeResponse(200, {"docs": []}),
        ],
    ):
        book = get_or_create_book("9780201616224")

    assert book.title == "Example Book"
    assert book.authors == []


@pytest.mark.django_db
def test_get_or_create_book_refreshes_cached_book_with_missing_metadata():
    cached = BookFactory(
        isbn_13="9780393081084",
        isbn_10="0393081087",
        title="The Food Lab: Better Home Cooking Through Science",
        authors=[],
        physical_format=None,
    )

    with patch(
        "apps.books.services.openlibrary.fetch_from_open_library",
        return_value={
            "title": cached.title,
            "authors": ["J. Kenji L\u00f3pez-Alt"],
            "physical_format": "Hardcover",
        },
    ) as mocked_fetch:
        book = get_or_create_book("9780393081084")

    mocked_fetch.assert_called_once_with("9780393081084")
    cached.refresh_from_db()
    assert book.id == cached.id
    assert cached.authors == ["J. Kenji L\u00f3pez-Alt"]
    assert cached.physical_format == "Hardcover"
