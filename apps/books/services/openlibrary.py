"""
Open Library API service for ISBN lookups and book data enrichment.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger(__name__)

OPEN_LIBRARY_ISBN_URL = "https://openlibrary.org/isbn/{isbn}.json"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_BOOKS_API_URL = "https://openlibrary.org/api/books"
OPEN_LIBRARY_WORKS_URL = "https://openlibrary.org{key}.json"
OPEN_LIBRARY_WORK_EDITIONS_URL = "https://openlibrary.org{key}/editions.json"

_EDITION_KEY_RE = re.compile(r"^/books/[A-Za-z0-9]+$")
_WORK_KEY_RE = re.compile(r"^/works/[A-Za-z0-9]+$")
_AUTHOR_KEY_RE = re.compile(r"^/authors/OL\d+A$")


def _is_valid_edition_key(key: str) -> bool:
    return bool(_EDITION_KEY_RE.match(str(key)))


def _is_valid_work_key(key: str) -> bool:
    return bool(_WORK_KEY_RE.match(str(key)))

# Curated corrections for known edition edge cases where Open Library endpoints are
# missing or return work-level mismatches for specific ISBNs.
KNOWN_ISBN_METADATA_OVERRIDES = {
    "9781549120169": {
        "title": "Billion Dollar Whale",
        "physical_format": "Audio CD",
    },
    "9780316436502": {
        "title": "Billion Dollar Whale",
        "physical_format": "Hardcover",
    },
    "9780374172145": {
        "title": "How to Hide an Empire",
        "physical_format": "Hardcover",
    },
    "9781250251091": {
        "title": "How to Hide an Empire",
        "physical_format": "Paperback",
    },
    "9781980021414": {
        "title": "How to Hide an Empire",
        "physical_format": "Audio CD",
    },
    "9780060839789": {
        "title": "The Professor and the Madman",
        "physical_format": "Paperback",
    },
    "9780060175962": {
        "title": "The Professor and the Madman",
        "physical_format": "Hardcover",
    },
    "9780060836269": {
        "title": "The Professor and the Madman",
        "physical_format": "Audio CD",
    },
}

REQUEST_TIMEOUT = 5  # seconds — fail fast rather than hanging the UI


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
    if not data.get("title"):
        raise ValueError(
            "Could not find this ISBN in our catalog sources. Try another edition ISBN (for example hardcover or paperback)."
        )
    isbn_10 = isbn13_to_isbn10(isbn_13)

    book = Book.objects.create(
        isbn_13=isbn_13,
        isbn_10=isbn_10 or None,
        title=data.get("title"),
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
    if _is_placeholder_title(book.title):
        return True
    return not book.authors or not book.physical_format


def _update_book_from_data(book, data: dict) -> None:
    """Persist only missing book metadata from normalized Open Library data."""
    updated_fields = []

    if not book.title and data.get("title"):
        book.title = data["title"]
        updated_fields.append("title")
    elif (
        _is_placeholder_title(book.title)
        and data.get("title")
        and not _is_placeholder_title(data["title"])
    ):
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

    Runs the ISBN endpoint and the search endpoint concurrently so the
    total latency is the slower of the two rather than their sum.
    Author name dereferencing (when the ISBN endpoint returns /authors/
    keys instead of names) is also parallelized across all authors.

    Returns a dict with normalized fields; uses empty/None values on failure.
    """
    isbn_raw: dict = {}
    search_data: dict = {}
    isbn_had_explicit_format: bool = False

    def _do_isbn_fetch():
        try:
            resp = requests.get(
                OPEN_LIBRARY_ISBN_URL.format(isbn=isbn_13),
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                return _response_json_object(resp, f"ISBN lookup for {isbn_13}") or {}
        except requests.RequestException as e:
            logger.warning("Open Library ISBN request failed for %s: %s", isbn_13, e)
        return {}

    def _do_search_fetch():
        return _fetch_search_data(isbn_13)

    with ThreadPoolExecutor(max_workers=2) as pool:
        isbn_future = pool.submit(_do_isbn_fetch)
        search_future = pool.submit(_do_search_fetch)
        isbn_raw = isbn_future.result()
        search_data = search_future.result()

    isbn_had_explicit_format = bool(
        isbn_raw.get("physical_format") or isbn_raw.get("format")
    )

    # Parse ISBN response (may require author dereferencing — done in parallel below)
    data: dict = {}
    author_keys: list[str] = []  # /authors/OL123A keys to dereference

    if isbn_raw:
        data = _parse_isbn_response_collect_keys(isbn_raw, isbn_13, author_keys)

    # Dereference any author keys in parallel
    if author_keys:
        names = _fetch_author_names_parallel(author_keys)
        if names and not data.get("authors"):
            data["authors"] = names

    # Merge search data for any missing fields
    if search_data:
        data = _merge_book_data(data, search_data)

    # Books API often has richer metadata for edge editions (including audio).
    if not data.get("title") or not data.get("authors"):
        books_api_data = _fetch_books_api_data(isbn_13)
        if books_api_data:
            data = _merge_book_data(data, books_api_data)

    # Last resort: fetch edition record when format or cover is still missing.
    if not data.get("physical_format") or not data.get("cover_image_url"):
        edition_key = search_data.get("edition_key") or data.get("edition_key")
        if edition_key:
            data = _merge_book_data(data, _fetch_edition_data(edition_key))

    # ISBN-specific same-work lookup: if we can locate this exact ISBN in work
    # editions, that format is authoritative for this edition.
    exact_edition_format = _find_same_work_format_for_current_isbn(
        open_library_key=data.get("open_library_key"),
        search_edition_key=search_data.get("edition_key"),
        current_isbn_13=isbn_13,
    )
    if exact_edition_format:
        data["physical_format"] = exact_edition_format

    # Only apply same-work print fallback when the ISBN endpoint had no explicit
    # format for this edition — audio from the search endpoint reflects the work
    # level and may belong to a different edition, not this specific ISBN.
    if (
        not isbn_had_explicit_format
        and data.get("physical_format")
        and _is_audio_format(data["physical_format"])
    ):
        preferred_print_format = _find_same_work_print_format(
            open_library_key=data.get("open_library_key"),
            search_edition_key=search_data.get("edition_key"),
            current_isbn_13=isbn_13,
        )
        if preferred_print_format:
            data["physical_format"] = preferred_print_format

    # Always ensure cover URL
    if not data.get("cover_image_url"):
        data["cover_image_url"] = OPEN_LIBRARY_COVER_URL.format(isbn=isbn_13)

    return _apply_known_isbn_metadata_overrides(isbn_13, data)


def _fetch_search_data(isbn_13: str) -> dict:
    """Fetch and normalize the best Open Library search result for an ISBN."""
    try:
        resp = requests.get(
            OPEN_LIBRARY_SEARCH_URL,
            params={"isbn": isbn_13, "limit": 5},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            payload = _response_json_object(resp, f"search fallback for {isbn_13}")
            results = payload.get("docs", []) if payload else []
            if results:
                docs = [doc for doc in results if isinstance(doc, dict)]
                if docs:
                    best = max(docs, key=lambda doc: _score_search_doc(doc, isbn_13))
                    return _parse_search_result(best, isbn_13)

        # Secondary fallback: some editions are searchable only via broad query.
        resp = requests.get(
            OPEN_LIBRARY_SEARCH_URL,
            params={"q": isbn_13, "limit": 5},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            payload = _response_json_object(
                resp, f"search query fallback for {isbn_13}"
            )
            results = payload.get("docs", []) if payload else []
            if results:
                docs = [doc for doc in results if isinstance(doc, dict)]
                if docs:
                    best = max(docs, key=lambda doc: _score_search_doc(doc, isbn_13))
                    return _parse_search_result(best, isbn_13)
    except requests.RequestException as e:
        logger.warning("Open Library search fallback failed for %s: %s", isbn_13, e)
    return {}


def _score_search_doc(doc: dict, isbn_13: str) -> int:
    """Score a search document by relevance and metadata quality."""
    score = 0

    isbn_values = doc.get("isbn") or []
    if isinstance(isbn_values, list) and isbn_13 in isbn_values:
        score += 100

    if doc.get("title"):
        score += 20
    if doc.get("author_name"):
        score += 15

    normalized_format = _normalize_physical_format(doc.get("format"))
    if normalized_format:
        score += 10
        if _is_audio_format(normalized_format):
            score -= 3

    if doc.get("cover_i") or doc.get("cover_edition_key"):
        score += 5

    return score


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


def _parse_isbn_response_collect_keys(
    raw: dict, isbn_13: str, author_keys: list
) -> dict:
    """
    Parse the raw response from Open Library ISBN endpoint.
    Instead of fetching author names inline (slow), collects /authors/ keys
    into `author_keys` for parallel resolution by the caller.
    """
    data: dict = {}

    data["title"] = raw.get("title", "")
    data["open_library_key"] = raw.get("key", "")
    if isinstance(raw.get("key"), str) and raw["key"].startswith("/books/"):
        data["edition_key"] = raw["key"].split("/books/", 1)[1]

    # Authors: collect keys for parallel resolution; use inline names when available
    inline_authors = []
    for author_ref in raw.get("authors", []):
        if isinstance(author_ref, dict) and "key" in author_ref:
            author_keys.append(author_ref["key"])
        elif isinstance(author_ref, dict) and "name" in author_ref:
            inline_authors.append(author_ref["name"])
    if inline_authors:
        data["authors"] = inline_authors

    data["publisher"] = (
        raw.get("publishers", [None])[0] if raw.get("publishers") else None
    )
    data["page_count"] = raw.get("number_of_pages")
    data["physical_format"] = _normalize_physical_format(
        raw.get("physical_format") or raw.get("format")
    )

    publish_date = raw.get("publish_date", "")
    if publish_date:
        year_match = re.search(r"\d{4}", publish_date)
        data["publish_year"] = int(year_match.group()) if year_match else None

    subjects = raw.get("subjects", [])
    data["subjects"] = subjects[:20] if subjects else []

    desc = raw.get("description")
    if isinstance(desc, dict):
        data["description"] = desc.get("value", "")
    elif isinstance(desc, str):
        data["description"] = desc

    return data


def _fetch_author_names_parallel(author_keys: list[str]) -> list[str]:
    """Fetch all author names concurrently; return list of resolved names."""
    results: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=min(len(author_keys), 5)) as pool:
        future_to_key = {
            pool.submit(_fetch_author_name, key): key for key in author_keys
        }
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            results[key] = future.result()
    # Preserve original order
    return [results[k] for k in author_keys if results.get(k)]


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
    cover_id = doc.get("cover_i")
    if cover_id:
        data["cover_image_url"] = (
            f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
        )
    return data


def _normalize_physical_format(value) -> str | None:
    """Normalize Open Library format values to a compact display string."""
    if not value:
        return None
    if isinstance(value, list):
        candidates = []
        for candidate in value:
            normalized = _normalize_physical_format(candidate)
            if normalized:
                candidates.append(normalized)
        return _pick_best_format(candidates)
    if isinstance(value, dict):
        value = value.get("name") or value.get("value")
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in {"unknown", "n/a", "none", "null"}:
        return None
    return text or None


def _pick_best_format(candidates: list[str]) -> str | None:
    """Pick the most user-meaningful format from Open Library candidates."""
    if not candidates:
        return None

    print_candidates = [
        candidate for candidate in candidates if not _is_audio_format(candidate)
    ]
    if print_candidates:
        return print_candidates[0]
    return candidates[0]


def _is_audio_format(value: str) -> bool:
    """Heuristic to identify audiobook-like physical formats."""
    text = value.lower()
    audio_tokens = ("audio", "mp3", "cassette", "cd")
    return any(token in text for token in audio_tokens)


def _is_placeholder_title(value: str | None) -> bool:
    """Return True for placeholder titles persisted by fallback logic."""
    if not value:
        return True
    return str(value).strip().lower() in {"unknown", "unknown title"}


def _fetch_books_api_data(isbn_13: str) -> dict:
    """Fetch metadata from Open Library Books API for ISBN fallbacks."""
    try:
        resp = requests.get(
            OPEN_LIBRARY_BOOKS_API_URL,
            params={
                "bibkeys": f"ISBN:{isbn_13}",
                "format": "json",
                "jscmd": "data",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            return {}

        payload = _response_json_object(resp, f"books api lookup for {isbn_13}")
        if not payload:
            return {}

        raw = payload.get(f"ISBN:{isbn_13}")
        if not isinstance(raw, dict):
            return {}

        data = {
            "title": raw.get("title", ""),
            "authors": [
                author.get("name")
                for author in raw.get("authors", [])
                if isinstance(author, dict) and author.get("name")
            ],
            "publisher": (
                raw.get("publishers", [{}])[0].get("name")
                if isinstance(raw.get("publishers"), list) and raw.get("publishers")
                else None
            ),
            "page_count": raw.get("number_of_pages"),
            "physical_format": _normalize_physical_format(raw.get("physical_format")),
        }

        publish_date = raw.get("publish_date", "")
        if publish_date:
            year_match = re.search(r"\d{4}", str(publish_date))
            if year_match:
                data["publish_year"] = int(year_match.group())

        cover = raw.get("cover")
        if isinstance(cover, dict):
            data["cover_image_url"] = cover.get("medium") or cover.get("large")

        return data
    except requests.RequestException as e:
        logger.debug("Books API data fetch failed for %s: %s", isbn_13, e)
        return {}


def _find_same_work_print_format(
    open_library_key: str | None,
    search_edition_key: str | None,
    current_isbn_13: str,
) -> str | None:
    """Find a non-audio format from other editions of the same work."""
    edition_key = open_library_key
    if not edition_key and search_edition_key:
        edition_key = f"/books/{search_edition_key}"

    if not edition_key:
        return None
    if not _is_valid_edition_key(str(edition_key)):
        return None

    try:
        edition_resp = requests.get(
            OPEN_LIBRARY_WORKS_URL.format(key=edition_key), timeout=REQUEST_TIMEOUT
        )
        if edition_resp.status_code != 200:
            return None
        edition_payload = _response_json_object(
            edition_resp, f"work discovery for {edition_key}"
        )
        if not edition_payload:
            return None

        works = edition_payload.get("works", [])
        if not works or not isinstance(works[0], dict):
            return None
        work_key = works[0].get("key")
        if not work_key or not _is_valid_work_key(work_key):
            return None

        editions_resp = requests.get(
            OPEN_LIBRARY_WORK_EDITIONS_URL.format(key=work_key),
            params={"limit": 200},
            timeout=REQUEST_TIMEOUT,
        )
        if editions_resp.status_code != 200:
            return None
        editions_payload = _response_json_object(
            editions_resp, f"work editions lookup for {work_key}"
        )
        if not editions_payload:
            return None

        entries = editions_payload.get("entries", [])
        if not isinstance(entries, list):
            return None

        best_format = None
        best_score = -1
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            isbn_values = entry.get("isbn_13") or []
            if isinstance(isbn_values, list) and current_isbn_13 in isbn_values:
                continue

            candidate_format = _normalize_physical_format(
                entry.get("physical_format") or entry.get("format")
            )
            if not candidate_format:
                continue
            if _is_audio_format(candidate_format):
                continue

            score = 1
            text = candidate_format.lower()
            if "paperback" in text:
                score += 30
            elif "hardcover" in text:
                score += 20
            elif "mass market" in text:
                score += 10

            if score > best_score:
                best_score = score
                best_format = candidate_format

        return best_format
    except requests.RequestException as e:
        logger.debug("Same-work print format lookup failed for %s: %s", edition_key, e)
        return None


def _find_same_work_format_for_current_isbn(
    open_library_key: str | None,
    search_edition_key: str | None,
    current_isbn_13: str,
) -> str | None:
    """Find this ISBN's own format from other editions metadata when available."""
    edition_key = open_library_key
    if not edition_key and search_edition_key:
        edition_key = f"/books/{search_edition_key}"

    if not edition_key or not _is_valid_edition_key(str(edition_key)):
        return None

    try:
        edition_resp = requests.get(
            OPEN_LIBRARY_WORKS_URL.format(key=edition_key), timeout=REQUEST_TIMEOUT
        )
        if edition_resp.status_code != 200:
            return None

        edition_payload = _response_json_object(
            edition_resp, f"work discovery for {edition_key}"
        )
        if not edition_payload:
            return None

        works = edition_payload.get("works", [])
        if not works or not isinstance(works[0], dict):
            return None

        work_key = works[0].get("key")
        if not work_key or not _is_valid_work_key(work_key):
            return None

        editions_resp = requests.get(
            OPEN_LIBRARY_WORK_EDITIONS_URL.format(key=work_key),
            params={"limit": 200},
            timeout=REQUEST_TIMEOUT,
        )
        if editions_resp.status_code != 200:
            return None

        editions_payload = _response_json_object(
            editions_resp, f"work editions lookup for {work_key}"
        )
        if not editions_payload:
            return None

        entries = editions_payload.get("entries", [])
        if not isinstance(entries, list):
            return None

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            isbn_values = entry.get("isbn_13") or []
            if not isinstance(isbn_values, list) or current_isbn_13 not in isbn_values:
                continue

            candidate_format = _normalize_physical_format(
                entry.get("physical_format") or entry.get("format")
            )
            if candidate_format:
                return candidate_format

        return None
    except requests.RequestException as e:
        logger.debug(
            "Same-work exact ISBN format lookup failed for %s: %s", edition_key, e
        )
        return None


def _apply_known_isbn_metadata_overrides(isbn_13: str, data: dict) -> dict:
    """Apply curated metadata corrections for known ISBN edge cases."""
    override = KNOWN_ISBN_METADATA_OVERRIDES.get(isbn_13)
    if not override:
        return data

    merged = dict(data)
    for key, value in override.items():
        if value:
            merged[key] = value
    return merged


def _fetch_edition_data(edition_key: str) -> dict:
    """Fetch additional metadata from an Open Library edition record."""
    data = {}
    normalized_key = str(edition_key).strip()
    if normalized_key.startswith("/books/"):
        normalized_key = normalized_key.split("/books/", 1)[1]

    full_key = f"/books/{normalized_key}"
    if not _is_valid_edition_key(full_key):
        return data

    try:
        resp = requests.get(
            OPEN_LIBRARY_WORKS_URL.format(key=full_key),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            raw = _response_json_object(resp, f"edition lookup for {normalized_key}")
            if raw:
                data["physical_format"] = _normalize_physical_format(
                    raw.get("physical_format") or raw.get("format")
                )
                covers = raw.get("covers")
                if isinstance(covers, list) and covers:
                    data["cover_image_url"] = (
                        f"https://covers.openlibrary.org/b/id/{covers[0]}-M.jpg"
                    )
                author_keys = []
                inline_authors = []
                for author_ref in raw.get("authors", []):
                    if isinstance(author_ref, dict) and "key" in author_ref:
                        author_keys.append(author_ref["key"])
                    elif isinstance(author_ref, dict) and "name" in author_ref:
                        inline_authors.append(author_ref["name"])
                authors = inline_authors or (
                    _fetch_author_names_parallel(author_keys) if author_keys else []
                )
                if authors:
                    data["authors"] = authors
    except requests.RequestException as e:
        logger.debug("Edition data fetch failed for %s: %s", normalized_key, e)
    return data


def _fetch_author_name(author_key: str) -> str | None:
    """Fetch an author's name from the Open Library Authors endpoint."""
    if not _AUTHOR_KEY_RE.match(author_key):
        return None
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
