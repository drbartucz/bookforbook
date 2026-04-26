"""
Unit tests for the Open Library ISBN utilities.
"""

import re
import pytest
from unittest.mock import patch

from apps.books.services.openlibrary import (
    fetch_from_open_library,
    get_or_create_book,
    isbn10_to_isbn13,
    isbn13_to_isbn10,
    normalize_isbn,
    _normalize_physical_format,
    _parse_isbn_response_collect_keys,
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

    def test_normalize_physical_format_unknown_placeholder(self):
        assert _normalize_physical_format("unknown") is None

    def test_normalize_physical_format_prefers_print_over_audio(self):
        assert _normalize_physical_format(["Audio CD", "Hardcover"]) == "Hardcover"

    def test_parse_isbn_response_extracts_physical_format(self):
        raw = {
            "title": "Example",
            "physical_format": "Mass Market Paperback",
            "authors": [],
        }
        author_keys: list = []
        parsed = _parse_isbn_response_collect_keys(raw, "9780201616224", author_keys)
        assert parsed["physical_format"] == "Mass Market Paperback"
        assert author_keys == []

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

    def mock_get(url, **kwargs):
        if "isbn/9780393081084.json" in url:
            return FakeResponse(
                200,
                {
                    "title": "The Food Lab: Better Home Cooking Through Science",
                    "authors": [],
                },
            )
        if "search.json" in url:
            return FakeResponse(
                200,
                {
                    "docs": [
                        {
                            "title": "The Food Lab",
                            "author_name": ["J. Kenji López-Alt"],
                            "cover_edition_key": "OL26629978M",
                        }
                    ]
                },
            )
        if "/books/OL26629978M.json" in url:
            return FakeResponse(
                200,
                {
                    "physical_format": "Hardcover",
                    "authors": [{"key": "/authors/OL7442728A"}],
                },
            )
        if "/authors/OL7442728A.json" in url:
            return FakeResponse(200, {"name": "J. Kenji López-Alt"})
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780393081084")

    assert data["authors"] == ["J. Kenji López-Alt"]
    assert data["physical_format"] == "Hardcover"


def test_fetch_from_open_library_ignores_unknown_format_and_uses_edition_fallback():
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780393081084.json" in url:
            return FakeResponse(
                200,
                {
                    "title": "The Food Lab: Better Home Cooking Through Science",
                    "physical_format": "unknown",
                    "authors": [],
                },
            )
        if "search.json" in url:
            return FakeResponse(
                200,
                {
                    "docs": [
                        {
                            "title": "The Food Lab",
                            "author_name": ["J. Kenji López-Alt"],
                            "cover_edition_key": "OL26629978M",
                        }
                    ]
                },
            )
        if "/books/OL26629978M.json" in url:
            return FakeResponse(
                200,
                {
                    "physical_format": "Hardcover",
                    "authors": [{"key": "/authors/OL7442728A"}],
                },
            )
        if "/authors/OL7442728A.json" in url:
            return FakeResponse(200, {"name": "J. Kenji López-Alt"})
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780393081084")

    assert data["physical_format"] == "Hardcover"


def test_fetch_from_open_library_prefers_print_format_when_isbn_is_audio():
    """When the ISBN endpoint has no format and the search returns a mixed
    format list, _pick_best_format should prefer the print edition."""

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780063341906.json" in url:
            # ISBN endpoint returns no physical_format — format info comes from search
            return FakeResponse(
                200,
                {
                    "title": "The Professor and the Madman",
                    "authors": [{"name": "Simon Winchester"}],
                },
            )
        if "search.json" in url:
            return FakeResponse(
                200,
                {
                    "docs": [
                        {
                            "title": "The Professor and the Madman",
                            "author_name": ["Simon Winchester"],
                            "isbn": ["9780063341906"],
                            "format": ["Paperback", "Audio CD"],
                        }
                    ]
                },
            )
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780063341906")

    assert data["physical_format"] == "Paperback"


def test_fetch_from_open_library_uses_same_work_paperback_fallback_for_audio_isbn():
    """When the ISBN endpoint has no format and the search returns audio-only,
    the same-work edition scan should find and use the print format."""

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780063341906.json" in url:
            # No physical_format in the ISBN endpoint response
            return FakeResponse(
                200,
                {
                    "title": "Professor and the Madman",
                    "key": "/books/OL46829382M",
                    "authors": [{"name": "Simon Winchester"}],
                },
            )
        if "search.json" in url:
            # Search returns audio-only format for this work
            return FakeResponse(
                200,
                {
                    "docs": [
                        {
                            "title": "The Professor and the Madman CD",
                            "author_name": ["Simon Winchester"],
                            "isbn": ["9780063341906"],
                            "format": ["Audio CD"],
                            "cover_edition_key": "OL9237439M",
                        }
                    ]
                },
            )
        if "/books/OL46829382M.json" in url:
            return FakeResponse(200, {"works": [{"key": "/works/OL1840019W"}]})
        if "/works/OL1840019W/editions.json" in url:
            return FakeResponse(
                200,
                {
                    "entries": [
                        {
                            "physical_format": "Audio CD",
                            "isbn_13": ["9780063341906"],
                        },
                        {
                            "physical_format": "Paperback",
                            "isbn_13": ["9780060839789"],
                        },
                    ]
                },
            )
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780063341906")

    assert data["physical_format"] == "Paperback"


def test_fetch_from_open_library_uses_books_api_when_isbn_and_search_are_sparse():
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780201616224.json" in url:
            return FakeResponse(404, {})
        if "search.json" in url:
            return FakeResponse(200, {"docs": []})
        if "api/books" in url:
            return FakeResponse(
                200,
                {
                    "ISBN:9780201616224": {
                        "title": "Recovered From Books API",
                        "authors": [{"name": "Author Example"}],
                        "publishers": [{"name": "Publisher Example"}],
                        "publish_date": "2001",
                        "number_of_pages": 321,
                        "cover": {"medium": "https://example.com/cover.jpg"},
                    }
                },
            )
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert data["title"] == "Recovered From Books API"
    assert data["authors"] == ["Author Example"]
    assert data["publisher"] == "Publisher Example"
    assert data["publish_year"] == 2001
    assert data["page_count"] == 321
    assert data["cover_image_url"] == "https://example.com/cover.jpg"


@pytest.mark.django_db
def test_get_or_create_book_ignores_malformed_author_payload():
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780201616224.json" in url:
            return FakeResponse(
                200,
                {
                    "title": "Example Book",
                    "authors": [{"key": "/authors/OL1A"}],
                },
            )
        if "search.json" in url:
            return FakeResponse(200, {"docs": []})
        if "/authors/OL1A.json" in url:
            return FakeResponse(200, ["unexpected"])
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
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


@pytest.mark.django_db
def test_get_or_create_book_does_not_refetch_cached_audio_edition():
    """A cached audiobook with full metadata should NOT be re-fetched;
    its audio format must be preserved as-is."""
    cached = BookFactory(
        isbn_13="9781549120169",
        isbn_10="1549120166",
        title="Billion Dollar Whale",
        authors=["Bradley Hope", "Tom Wright"],
        physical_format="Audio CD",
    )

    with patch(
        "apps.books.services.openlibrary.fetch_from_open_library",
    ) as mocked_fetch:
        book = get_or_create_book("9781549120169")

    mocked_fetch.assert_not_called()
    cached.refresh_from_db()
    assert book.id == cached.id
    assert cached.physical_format == "Audio CD"


@pytest.mark.django_db
def test_get_or_create_book_refreshes_cached_unknown_title():
    cached = BookFactory(
        isbn_13="9781549120169",
        isbn_10="1549120167",
        title="Unknown Title",
        authors=["Bradley Hope", "Tom Wright"],
        physical_format="Paperback",
    )

    with patch(
        "apps.books.services.openlibrary.fetch_from_open_library",
        return_value={
            "title": "Billion Dollar Whale",
            "authors": ["Bradley Hope", "Tom Wright"],
            "physical_format": "Paperback",
        },
    ) as mocked_fetch:
        book = get_or_create_book("9781549120169")

    mocked_fetch.assert_called_once_with("9781549120169")
    cached.refresh_from_db()
    assert book.id == cached.id
    assert cached.title == "Billion Dollar Whale"


# ---------------------------------------------------------------------------
# _response_json_object
# ---------------------------------------------------------------------------


class TestResponseJsonObject:
    def _make_resp(self, status_code, body):
        from unittest.mock import MagicMock

        r = MagicMock()
        r.status_code = status_code
        r.json.return_value = body
        return r

    def test_returns_dict_payload(self):
        from apps.books.services.openlibrary import _response_json_object

        r = self._make_resp(200, {"title": "Hi"})
        assert _response_json_object(r, "ctx") == {"title": "Hi"}

    def test_returns_none_for_list_payload(self):
        from apps.books.services.openlibrary import _response_json_object

        r = self._make_resp(200, [1, 2, 3])
        assert _response_json_object(r, "ctx") is None

    def test_returns_none_for_invalid_json(self):
        from unittest.mock import MagicMock
        from apps.books.services.openlibrary import _response_json_object

        r = MagicMock()
        r.json.side_effect = ValueError("bad json")
        assert _response_json_object(r, "ctx") is None


# ---------------------------------------------------------------------------
# _merge_book_data
# ---------------------------------------------------------------------------


class TestMergeBookData:
    def test_fills_missing_fields_from_fallback(self):
        from apps.books.services.openlibrary import _merge_book_data

        primary = {"title": "Book A", "authors": []}
        fallback = {"authors": ["Alice"], "page_count": 300}
        merged = _merge_book_data(primary, fallback)
        assert merged["title"] == "Book A"
        assert merged["authors"] == ["Alice"]
        assert merged["page_count"] == 300

    def test_does_not_overwrite_existing_values(self):
        from apps.books.services.openlibrary import _merge_book_data

        primary = {"title": "Book A", "authors": ["Alice"]}
        fallback = {"title": "Book B", "authors": ["Bob"]}
        merged = _merge_book_data(primary, fallback)
        assert merged["title"] == "Book A"
        assert merged["authors"] == ["Alice"]

    def test_skips_empty_fallback_values(self):
        from apps.books.services.openlibrary import _merge_book_data

        primary = {"title": ""}
        fallback = {"title": "", "authors": []}
        merged = _merge_book_data(primary, fallback)
        assert "authors" not in merged  # empty list not backfilled


# ---------------------------------------------------------------------------
# get_or_create_book — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_or_create_book_raises_for_invalid_isbn():
    from apps.books.services.openlibrary import get_or_create_book

    with pytest.raises(ValueError, match="Invalid ISBN"):
        get_or_create_book("not-an-isbn")


@pytest.mark.django_db
def test_get_or_create_book_raises_when_metadata_is_unavailable():
    from apps.books.services.openlibrary import get_or_create_book

    with patch(
        "apps.books.services.openlibrary.fetch_from_open_library",
        return_value={},
    ):
        with pytest.raises(ValueError, match="Could not find this ISBN"):
            get_or_create_book("9780201616224")


@pytest.mark.django_db
def test_get_or_create_book_skips_enrichment_when_complete():
    """A cached book with authors AND physical_format should not trigger a fetch."""
    from unittest.mock import patch
    from apps.books.services.openlibrary import get_or_create_book
    from apps.tests.factories import BookFactory

    cached = BookFactory(
        isbn_13="9780201616224",
        authors=["Author One"],
        physical_format="Paperback",
    )

    with patch("apps.books.services.openlibrary.fetch_from_open_library") as mock_fetch:
        book = get_or_create_book("9780201616224")

    mock_fetch.assert_not_called()
    assert book.id == cached.id


# ---------------------------------------------------------------------------
# fetch_from_open_library — network error / non-200 paths
# ---------------------------------------------------------------------------


def test_fetch_from_open_library_handles_isbn_endpoint_timeout():
    """A timeout on the ISBN endpoint must not raise — falls back to search data."""
    import requests
    from unittest.mock import patch, MagicMock

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {
        "docs": [
            {"title": "Some Book", "author_name": ["Author"], "format": ["Paperback"]}
        ]
    }

    def mock_get(url, **kwargs):
        if "isbn/" in url:
            raise requests.Timeout("timed out")
        return search_resp

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert data["title"] == "Some Book"


def test_fetch_from_open_library_handles_503_on_isbn_endpoint():
    """A 503 on the ISBN endpoint is silently ignored; cover URL is guaranteed."""
    from unittest.mock import patch, MagicMock

    error_resp = MagicMock()
    error_resp.status_code = 503

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {"docs": []}

    def mock_get(url, **kwargs):
        if "isbn/" in url:
            return error_resp
        return search_resp

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert "cover_image_url" in data
    assert "9780201616224" in data["cover_image_url"]


def test_fetch_from_open_library_handles_malformed_search_json():
    """Malformed JSON from the search endpoint must not raise."""
    from unittest.mock import patch, MagicMock

    isbn_resp = MagicMock()
    isbn_resp.status_code = 200
    isbn_resp.json.return_value = {"title": "Some Book", "authors": []}

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.side_effect = ValueError("not json")

    def mock_get(url, **kwargs):
        if "isbn/" in url:
            return isbn_resp
        return search_resp

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert data["title"] == "Some Book"


def test_fetch_from_open_library_handles_edition_404():
    """A 404 on the edition endpoint must not raise; physical_format stays None."""
    from unittest.mock import patch, MagicMock

    isbn_resp = MagicMock()
    isbn_resp.status_code = 200
    isbn_resp.json.return_value = {"title": "Book", "authors": []}

    search_resp = MagicMock()
    search_resp.status_code = 200
    search_resp.json.return_value = {
        "docs": [{"title": "Book", "cover_edition_key": "OL123M"}]
    }

    edition_resp = MagicMock()
    edition_resp.status_code = 404

    def mock_get(url, **kwargs):
        if "isbn/" in url:
            return isbn_resp
        if "search.json" in url:
            return search_resp
        if "/books/OL123M" in url:
            return edition_resp
        return MagicMock(status_code=404)

    with patch("apps.books.services.openlibrary.requests.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert data.get("physical_format") is None
    assert "cover_image_url" in data


def test_fetch_author_name_returns_none_on_non_200():
    """_fetch_author_name gracefully returns None for non-200 responses."""
    from unittest.mock import patch, MagicMock
    from apps.books.services.openlibrary import _fetch_author_name

    resp = MagicMock()
    resp.status_code = 404

    with patch("apps.books.services.openlibrary.requests.get", return_value=resp):
        result = _fetch_author_name("/authors/OL999A")

    assert result is None


def test_fetch_author_name_returns_none_on_request_exception():
    """_fetch_author_name gracefully handles network failures."""
    import requests
    from unittest.mock import patch
    from apps.books.services.openlibrary import _fetch_author_name

    with patch(
        "apps.books.services.openlibrary.requests.get",
        side_effect=requests.ConnectionError("no network"),
    ):
        result = _fetch_author_name("/authors/OL999A")

    assert result is None


# ---------------------------------------------------------------------------
# Live ISBN regression matrix
# ---------------------------------------------------------------------------


def _normalize_title_for_assert(value: str | None) -> str:
    """Normalize title strings for resilient comparisons across API casing/punctuation."""
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _format_bucket(value: str | None) -> str:
    """Map Open Library physical formats to stable buckets used by tests."""
    text = (value or "").lower()
    if any(token in text for token in ("audio", "cd", "cassette", "mp3", "digital")):
        return "audio"
    if "hardcover" in text:
        return "hardcover"
    if any(token in text for token in ("paperback", "mass market", "trade paperback")):
        return "paperback"
    return "other"


@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.parametrize(
    "isbn,expected_title_fragment,expected_format_bucket",
    [
        ("9781549120169", "Billion Dollar Whale", "audio"),
        ("9780316436502", "Billion Dollar Whale", "hardcover"),
        ("9780374172145", "How To Hide An Empire", "hardcover"),
        ("9781250251091", "How To Hide An Empire", "paperback"),
        ("9781980021414", "How To Hide An Empire", "audio"),
        ("9780060839789", "The Professor and the Madman", "paperback"),
        ("9780060175962", "The Professor and the Madman", "hardcover"),
        ("9780060836269", "The Professor and the Madman", "audio"),
    ],
)
def test_get_or_create_book_live_isbn_regression_matrix(
    isbn, expected_title_fragment, expected_format_bucket
):
    """Regression matrix for known ISBN/title/format expectations."""
    from apps.books.models import Book

    # Remove any stale cached row so this test validates current lookup behavior.
    Book.objects.filter(isbn_13=isbn).delete()

    book = get_or_create_book(isbn)

    actual_title = _normalize_title_for_assert(book.title)
    expected_title = _normalize_title_for_assert(expected_title_fragment)
    assert expected_title in actual_title

    assert _format_bucket(book.physical_format) == expected_format_bucket
