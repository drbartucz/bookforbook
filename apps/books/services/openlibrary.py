"""
Open Library API service for ISBN lookups and book data enrichment.
"""

import logging
import re

import requests

logger = logging.getLogger(__name__)

OPEN_LIBRARY_ISBN_URL = "https://openlibrary.org/isbn/{isbn}.json"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_WORKS_URL = "https://openlibrary.org{key}.json"

REQUEST_TIMEOUT = 10  # seconds


def _response_json_object(resp: requests.Response, context: str) -> dict | None:
    """Return a JSON object payload or None for malformed/unexpected responses."""
    try:
        payload = resp.json()
    except ValueError as exc:
        logger.warning("Open Library %s returned invalid JSON: %s", context, exc)
        return None

    if not isinstance(payload, dict):
        logger.warning(
            "Open Library %s returned %s instead of an object",
            context,
            type(payload).__name__,
        )
        return None

    return payload


def get_or_create_book(isbn: str):
    """
    Normalize ISBN to ISBN-13, check the local cache (Book table),
    fetch from Open Library if not found, and return the Book instance.
    """
    from apps.books.models import Book

    isbn_13 = normalize_isbn(isbn)
    if not isbn_13:
        raise ValueError(f"Invalid ISBN: {isbn!r}")

    # Check cache first
    try:
        book = Book.objects.get(isbn_13=isbn_13)
        if _book_needs_enrichment(book):
            enriched = fetch_from_open_library(isbn_13)
            _update_book_from_data(book, enriched)
        return book
    except Book.DoesNotExist:
        pass

    # Fetch from Open Library
    data = fetch_from_open_library(isbn_13)
    isbn_10 = isbn13_to_isbn10(isbn_13)

    book = Book.objects.create(
        isbn_13=isbn_13,
        isbn_10=isbn_10 or None,
        title=data.get("title") or "Unknown Title",
        authors=data.get("authors", []),
        publisher=data.get("publisher"),
        publish_year=data.get("publish_year"),
        cover_image_url=data.get("cover_image_url"),
        page_count=data.get("page_count"),
        physical_format=data.get("physical_format"),
        subjects=data.get("subjects", []),
        description=data.get("description"),
        open_library_key=data.get("open_library_key"),
    )
    return book


def _book_needs_enrichment(book) -> bool:
    """Return True when cached book metadata is incomplete enough to re-fetch."""
    return not book.authors or not book.physical_format


def _update_book_from_data(book, data: dict) -> None:
    """Persist only missing book metadata from normalized Open Library data."""
    updated_fields = []

    if not book.title and data.get("title"):
        book.title = data["title"]
        updated_fields.append("title")
    if not book.authors and data.get("authors"):
        book.authors = data["authors"]
        updated_fields.append("authors")
    if not book.publisher and data.get("publisher"):
        book.publisher = data["publisher"]
        updated_fields.append("publisher")
    if not book.publish_year and data.get("publish_year"):
        book.publish_year = data["publish_year"]
        updated_fields.append("publish_year")
    if not book.cover_image_url and data.get("cover_image_url"):
        book.cover_image_url = data["cover_image_url"]
        updated_fields.append("cover_image_url")
    if not book.page_count and data.get("page_count"):
        book.page_count = data["page_count"]
        updated_fields.append("page_count")
    if not book.physical_format and data.get("physical_format"):
        book.physical_format = data["physical_format"]
        updated_fields.append("physical_format")
    if not book.subjects and data.get("subjects"):
        book.subjects = data["subjects"]
        updated_fields.append("subjects")
    if not book.description and data.get("description"):
        book.description = data["description"]
        updated_fields.append("description")
    if not book.open_library_key and data.get("open_library_key"):
        book.open_library_key = data["open_library_key"]
        updated_fields.append("open_library_key")

    if updated_fields:
        updated_fields.append("updated_at")
        book.save(update_fields=updated_fields)


def normalize_isbn(isbn: str) -> str | None:
    """
    Normalize an ISBN string to ISBN-13 format.
    Accepts ISBN-10 or ISBN-13, strips dashes/spaces.
    Returns None if invalid.
    """
    if not isbn:
        return None
    # Strip formatting characters
    cleaned = re.sub(r"[\s\-]", "", isbn.strip())

    if len(cleaned) == 10:
        return isbn10_to_isbn13(cleaned)
    elif len(cleaned) == 13:
        if _validate_isbn13(cleaned):
            return cleaned
        return None
    return None


def isbn10_to_isbn13(isbn10: str) -> str | None:
    """Convert an ISBN-10 string to ISBN-13."""
    cleaned = re.sub(r"[\s\-]", "", isbn10.strip())
    if len(cleaned) != 10:
        return None
    # Validate ISBN-10 check digit
    if not _validate_isbn10(cleaned):
        return None
    # Prepend '978' and recalculate check digit
    base = "978" + cleaned[:9]
    check = _isbn13_check_digit(base)
    return base + str(check)


def isbn13_to_isbn10(isbn13: str) -> str | None:
    """Convert an ISBN-13 (978-prefix) string to ISBN-10."""
    cleaned = re.sub(r"[\s\-]", "", isbn13.strip())
    if len(cleaned) != 13 or not cleaned.startswith("978"):
        return None
    base9 = cleaned[3:12]
    total = sum((10 - i) * int(d) for i, d in enumerate(base9))
    check = (11 - (total % 11)) % 11
    check_char = "X" if check == 10 else str(check)
    return base9 + check_char


def _validate_isbn10(isbn10: str) -> bool:
    """Validate ISBN-10 check digit."""
    if not re.match(r"^\d{9}[\dX]$", isbn10, re.IGNORECASE):
        return False
    total = sum(
        (10 - i) * (10 if c.upper() == "X" else int(c)) for i, c in enumerate(isbn10)
    )
    return total % 11 == 0


def _validate_isbn13(isbn13: str) -> bool:
    """Validate ISBN-13 check digit."""
    if not re.match(r"^\d{13}$", isbn13):
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(isbn13[:12]))
    check = (10 - (total % 10)) % 10
    return check == int(isbn13[12])


def _isbn13_check_digit(first12: str) -> int:
    """Compute the check digit for the first 12 digits of an ISBN-13."""
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(first12))
    return (10 - (total % 10)) % 10


def fetch_from_open_library(isbn_13: str) -> dict:
    """
    Fetch book data from the Open Library API.
    Returns a dict with normalized fields; uses empty/None values on failure.
    """
    data = {}

    # Try the ISBN endpoint first
    try:
        resp = requests.get(
            OPEN_LIBRARY_ISBN_URL.format(isbn=isbn_13),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            raw = _response_json_object(resp, f"ISBN lookup for {isbn_13}")
            if raw:
                data = _parse_isbn_response(raw, isbn_13)
                # If we got works key, try to enrich with work data
                works = raw.get("works")
                if isinstance(works, list) and works:
                    first_work = works[0]
                    if isinstance(first_work, dict) and first_work.get("key"):
                        data.update(_fetch_work_data(first_work["key"]))
    except requests.RequestException as e:
        logger.warning("Open Library ISBN request failed for %s: %s", isbn_13, e)

    if not data.get("title") or not data.get("authors") or not data.get("physical_format"):
        search_data = _fetch_search_data(isbn_13)
        if search_data:
            data = _merge_book_data(data, search_data)

            edition_key = search_data.get("edition_key")
            if edition_key and not data.get("physical_format"):
                data = _merge_book_data(data, _fetch_edition_data(edition_key))

    # Always set the cover URL (may not exist, but that's okay)
    if not data.get("cover_image_url"):
        data["cover_image_url"] = OPEN_LIBRARY_COVER_URL.format(isbn=isbn_13)

    return data


def _fetch_search_data(isbn_13: str) -> dict:
    """Fetch and normalize the first Open Library search result for an ISBN."""
    try:
        resp = requests.get(
            OPEN_LIBRARY_SEARCH_URL,
            params={"isbn": isbn_13, "limit": 1},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            payload = _response_json_object(resp, f"search fallback for {isbn_13}")
            results = payload.get("docs", []) if payload else []
            if results and isinstance(results[0], dict):
                return _parse_search_result(results[0], isbn_13)
    except requests.RequestException as e:
        logger.warning("Open Library search fallback failed for %s: %s", isbn_13, e)
    return {}


def _merge_book_data(primary: dict, fallback: dict) -> dict:
    """Fill missing normalized fields in primary from fallback data."""
    merged = dict(primary)
    for key, value in fallback.items():
        if merged.get(key):
            continue
        if value in (None, "", []):
            continue
        merged[key] = value
    return merged


def _parse_isbn_response(raw: dict, isbn_13: str) -> dict:
    """Parse the raw response from Open Library ISBN endpoint."""
    data = {}

    data["title"] = raw.get("title", "")
    data["open_library_key"] = raw.get("key", "")

    # Authors: dereference if needed
    authors = []
    for author_ref in raw.get("authors", []):
        if isinstance(author_ref, dict) and "key" in author_ref:
            name = _fetch_author_name(author_ref["key"])
            if name:
                authors.append(name)
        elif isinstance(author_ref, dict) and "name" in author_ref:
            authors.append(author_ref["name"])
    data["authors"] = authors

    data["publisher"] = (
        raw.get("publishers", [None])[0] if raw.get("publishers") else None
    )
    data["page_count"] = raw.get("number_of_pages")
    data["physical_format"] = _normalize_physical_format(
        raw.get("physical_format") or raw.get("format")
    )

    # Publish year
    publish_date = raw.get("publish_date", "")
    if publish_date:
        year_match = re.search(r"\d{4}", publish_date)
        data["publish_year"] = int(year_match.group()) if year_match else None

    subjects = raw.get("subjects", [])
    data["subjects"] = subjects[:20] if subjects else []

    # Description
    desc = raw.get("description")
    if isinstance(desc, dict):
        data["description"] = desc.get("value", "")
    elif isinstance(desc, str):
        data["description"] = desc

    return data


def _parse_search_result(doc: dict, isbn_13: str) -> dict:
    """Parse a search result doc from Open Library search API."""
    data = {}
    data["title"] = doc.get("title", "")
    data["authors"] = doc.get("author_name", [])
    data["publisher"] = (
        doc.get("publisher", [None])[0] if doc.get("publisher") else None
    )
    data["publish_year"] = doc.get("first_publish_year")
    data["page_count"] = doc.get("number_of_pages_median")
    data["physical_format"] = _normalize_physical_format(doc.get("format"))
    data["edition_key"] = doc.get("cover_edition_key") or (
        doc.get("edition_key", [None])[0] if doc.get("edition_key") else None
    )
    subjects = doc.get("subject", [])
    data["subjects"] = subjects[:20] if subjects else []
    return data


def _normalize_physical_format(value) -> str | None:
    """Normalize Open Library format values to a compact display string."""
    if not value:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("name") or value.get("value")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _fetch_work_data(work_key: str) -> dict:
    """Fetch additional data from the Open Library Works endpoint."""
    data = {}
    try:
        resp = requests.get(
            OPEN_LIBRARY_WORKS_URL.format(key=work_key),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            raw = _response_json_object(resp, f"work lookup for {work_key}")
            if raw:
                desc = raw.get("description")
                if isinstance(desc, dict):
                    data["description"] = desc.get("value", "")
                elif isinstance(desc, str):
                    data["description"] = desc
                subjects = raw.get("subjects", [])
                if subjects:
                    data["subjects"] = subjects[:20]
    except requests.RequestException as e:
        logger.debug("Work data fetch failed for %s: %s", work_key, e)
    return data


def _fetch_edition_data(edition_key: str) -> dict:
    """Fetch additional metadata from an Open Library edition record."""
    data = {}
    try:
        resp = requests.get(
            OPEN_LIBRARY_WORKS_URL.format(key=f"/books/{edition_key}"),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            raw = _response_json_object(resp, f"edition lookup for {edition_key}")
            if raw:
                data["physical_format"] = _normalize_physical_format(
                    raw.get("physical_format") or raw.get("format")
                )
                authors = []
                for author_ref in raw.get("authors", []):
                    if isinstance(author_ref, dict) and "key" in author_ref:
                        name = _fetch_author_name(author_ref["key"])
                        if name:
                            authors.append(name)
                    elif isinstance(author_ref, dict) and "name" in author_ref:
                        authors.append(author_ref["name"])
                if authors:
                    data["authors"] = authors
    except requests.RequestException as e:
        logger.debug("Edition data fetch failed for %s: %s", edition_key, e)
    return data


def _fetch_author_name(author_key: str) -> str | None:
    """Fetch an author's name from the Open Library Authors endpoint."""
    try:
        resp = requests.get(
            f"https://openlibrary.org{author_key}.json",
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            raw = _response_json_object(resp, f"author lookup for {author_key}")
            if raw:
                return raw.get("name")
    except requests.RequestException:
        pass
    return None
