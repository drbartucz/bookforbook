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
    _fetch_work_data,
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

    def test_parse_isbn_response_extracts_cover_from_covers_field(self):
        raw = {
            "title": "Example",
            "authors": [],
            "covers": [12345678],
        }
        author_keys: list = []
        parsed = _parse_isbn_response_collect_keys(raw, "9780201616224", author_keys)
        assert parsed["cover_image_url"] == "https://covers.openlibrary.org/b/id/12345678-M.jpg"

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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    mocked_fetch.assert_called_once_with("9780393081084", minimal=False)
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
        description="The story of a massive financial fraud.",
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

    mocked_fetch.assert_called_once_with("9781549120169", minimal=False)
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
        description="A complete book with all metadata.",
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
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

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert data.get("physical_format") is None
    assert "cover_image_url" in data


# ---------------------------------------------------------------------------
# _fetch_work_data
# ---------------------------------------------------------------------------


class TestFetchWorkData:
    def _make_resp(self, status_code, payload):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = status_code
        r.json.return_value = payload
        return r

    def test_extracts_description_string(self):
        resp = self._make_resp(200, {"description": "A great book about things."})
        with patch("apps.books.services.openlibrary._session.get", return_value=resp):
            data = _fetch_work_data("/works/OL123W")
        assert data["description"] == "A great book about things."

    def test_extracts_description_dict_value(self):
        resp = self._make_resp(200, {
            "description": {"type": "/type/text", "value": "A dict-wrapped synopsis."}
        })
        with patch("apps.books.services.openlibrary._session.get", return_value=resp):
            data = _fetch_work_data("/works/OL123W")
        assert data["description"] == "A dict-wrapped synopsis."

    def test_extracts_subjects(self):
        subjects = ["Fiction", "Mystery", "Thriller"]
        resp = self._make_resp(200, {"subjects": subjects})
        with patch("apps.books.services.openlibrary._session.get", return_value=resp):
            data = _fetch_work_data("/works/OL123W")
        assert data["subjects"] == subjects

    def test_returns_empty_on_404(self):
        resp = self._make_resp(404, {})
        with patch("apps.books.services.openlibrary._session.get", return_value=resp):
            data = _fetch_work_data("/works/OL123W")
        assert data == {}

    def test_returns_empty_on_invalid_work_key(self):
        data = _fetch_work_data("/books/OL123M")
        assert data == {}

    def test_returns_empty_on_request_exception(self):
        import requests
        with patch(
            "apps.books.services.openlibrary._session.get",
            side_effect=requests.ConnectionError("no network"),
        ):
            data = _fetch_work_data("/works/OL123W")
        assert data == {}


def test_fetch_from_open_library_populates_description_from_work_endpoint():
    """Description must be fetched from the work record when absent from edition/search."""

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780201616224.json" in url:
            return FakeResponse(200, {
                "title": "The Pragmatic Programmer",
                "authors": [{"name": "David Thomas"}],
                "works": [{"key": "/works/OL123W"}],
            })
        if "search.json" in url:
            return FakeResponse(200, {"docs": []})
        if "/works/OL123W.json" in url:
            return FakeResponse(200, {
                "description": "A seminal guide to software craftsmanship.",
            })
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert data["description"] == "A seminal guide to software craftsmanship."


def test_fetch_from_open_library_uses_search_work_key_for_description():
    """work_key from search result is used as fallback when ISBN endpoint has no works."""

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780201616224.json" in url:
            return FakeResponse(200, {
                "title": "The Pragmatic Programmer",
                "authors": [{"name": "David Thomas"}],
            })
        if "search.json" in url:
            return FakeResponse(200, {
                "docs": [{
                    "title": "The Pragmatic Programmer",
                    "author_name": ["David Thomas"],
                    "key": "/works/OL456W",
                }]
            })
        if "/works/OL456W.json" in url:
            return FakeResponse(200, {
                "description": {"type": "/type/text", "value": "From search work key."},
            })
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert data["description"] == "From search work key."


def test_fetch_from_open_library_skips_work_fetch_when_description_already_present():
    """_fetch_work_data must not be called when description is already populated."""

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    work_fetched = []

    def mock_get(url, **kwargs):
        if "isbn/9780201616224.json" in url:
            return FakeResponse(200, {
                "title": "The Pragmatic Programmer",
                "authors": [{"name": "David Thomas"}],
                "description": "Already here.",
                "works": [{"key": "/works/OL123W"}],
            })
        if "search.json" in url:
            return FakeResponse(200, {"docs": []})
        if "/works/OL123W.json" in url:
            work_fetched.append(url)
            return FakeResponse(200, {"description": "Should not overwrite."})
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
        data = fetch_from_open_library("9780201616224")

    assert data["description"] == "Already here."
    assert work_fetched == []


def test_fetch_from_open_library_gets_cover_and_description_via_edition_work_key():
    """When ISBN endpoint has covers[] and its edition record has a works[] key,
    both cover and description should be populated even without a search work key."""

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780143136439.json" in url:
            return FakeResponse(200, {
                "title": "The Book",
                "authors": [{"name": "Some Author"}],
                "covers": [99887766],
                "works": [{"key": "/works/OL99887W"}],
            })
        if "search.json" in url:
            return FakeResponse(200, {"docs": []})
        if "/works/OL99887W.json" in url:
            return FakeResponse(200, {"description": "A synopsis from the work record."})
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
        data = fetch_from_open_library("9780143136439")

    assert data["cover_image_url"] == "https://covers.openlibrary.org/b/id/99887766-M.jpg"
    assert data["description"] == "A synopsis from the work record."


def test_fetch_from_open_library_gets_description_via_edition_data_work_key():
    """work_key extracted from edition-data fetch (covers/format fallback path)
    must be used to populate description when ISBN and search don't provide one."""

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def mock_get(url, **kwargs):
        if "isbn/9780143136439.json" in url:
            # No covers, no works — cover and work_key must come from edition fetch
            return FakeResponse(200, {
                "title": "The Book",
                "authors": [{"name": "Some Author"}],
            })
        if "search.json" in url:
            return FakeResponse(200, {
                "docs": [{"title": "The Book", "cover_edition_key": "OL55443M"}]
            })
        if "/books/OL55443M.json" in url:
            return FakeResponse(200, {
                "physical_format": "Paperback",
                "covers": [55443322],
                "works": [{"key": "/works/OL55443W"}],
            })
        if "/works/OL55443W.json" in url:
            return FakeResponse(200, {"description": "Description via edition work key."})
        return FakeResponse(404, {})

    with patch("apps.books.services.openlibrary._session.get", side_effect=mock_get):
        data = fetch_from_open_library("9780143136439")

    assert data["cover_image_url"] == "https://covers.openlibrary.org/b/id/55443322-M.jpg"
    assert data["description"] == "Description via edition work key."


def test_fetch_author_name_returns_none_on_non_200():
    """_fetch_author_name gracefully returns None for non-200 responses."""
    from unittest.mock import patch, MagicMock
    from apps.books.services.openlibrary import _fetch_author_name

    resp = MagicMock()
    resp.status_code = 404

    with patch("apps.books.services.openlibrary._session.get", return_value=resp):
        result = _fetch_author_name("/authors/OL999A")

    assert result is None


def test_fetch_author_name_returns_none_on_request_exception():
    """_fetch_author_name gracefully handles network failures."""
    import requests
    from unittest.mock import patch
    from apps.books.services.openlibrary import _fetch_author_name

    with patch(
        "apps.books.services.openlibrary._session.get",
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
