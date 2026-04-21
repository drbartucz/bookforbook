"""
Open Library API service for ISBN lookups and book data enrichment.
"""
import logging
import re

import requests

logger = logging.getLogger(__name__)

OPEN_LIBRARY_ISBN_URL = 'https://openlibrary.org/isbn/{isbn}.json'
OPEN_LIBRARY_COVER_URL = 'https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg'
OPEN_LIBRARY_SEARCH_URL = 'https://openlibrary.org/search.json'
OPEN_LIBRARY_WORKS_URL = 'https://openlibrary.org{key}.json'

REQUEST_TIMEOUT = 10  # seconds


def get_or_create_book(isbn: str):
    """
    Normalize ISBN to ISBN-13, check the local cache (Book table),
    fetch from Open Library if not found, and return the Book instance.
    """
    from apps.books.models import Book

    isbn_13 = normalize_isbn(isbn)
    if not isbn_13:
        raise ValueError(f'Invalid ISBN: {isbn!r}')

    # Check cache first
    try:
        return Book.objects.get(isbn_13=isbn_13)
    except Book.DoesNotExist:
        pass

    # Fetch from Open Library
    data = fetch_from_open_library(isbn_13)
    isbn_10 = isbn13_to_isbn10(isbn_13)

    book = Book.objects.create(
        isbn_13=isbn_13,
        isbn_10=isbn_10 or None,
        title=data.get('title') or 'Unknown Title',
        authors=data.get('authors', []),
        publisher=data.get('publisher'),
        publish_year=data.get('publish_year'),
        cover_image_url=data.get('cover_image_url'),
        page_count=data.get('page_count'),
        physical_format=data.get('physical_format'),
        subjects=data.get('subjects', []),
        description=data.get('description'),
        open_library_key=data.get('open_library_key'),
    )
    return book


def normalize_isbn(isbn: str) -> str | None:
    """
    Normalize an ISBN string to ISBN-13 format.
    Accepts ISBN-10 or ISBN-13, strips dashes/spaces.
    Returns None if invalid.
    """
    if not isbn:
        return None
    # Strip formatting characters
    cleaned = re.sub(r'[\s\-]', '', isbn.strip())

    if len(cleaned) == 10:
        return isbn10_to_isbn13(cleaned)
    elif len(cleaned) == 13:
        if _validate_isbn13(cleaned):
            return cleaned
        return None
    return None


def isbn10_to_isbn13(isbn10: str) -> str | None:
    """Convert an ISBN-10 string to ISBN-13."""
    cleaned = re.sub(r'[\s\-]', '', isbn10.strip())
    if len(cleaned) != 10:
        return None
    # Validate ISBN-10 check digit
    if not _validate_isbn10(cleaned):
        return None
    # Prepend '978' and recalculate check digit
    base = '978' + cleaned[:9]
    check = _isbn13_check_digit(base)
    return base + str(check)


def isbn13_to_isbn10(isbn13: str) -> str | None:
    """Convert an ISBN-13 (978-prefix) string to ISBN-10."""
    cleaned = re.sub(r'[\s\-]', '', isbn13.strip())
    if len(cleaned) != 13 or not cleaned.startswith('978'):
        return None
    base9 = cleaned[3:12]
    total = sum((10 - i) * int(d) for i, d in enumerate(base9))
    check = (11 - (total % 11)) % 11
    check_char = 'X' if check == 10 else str(check)
    return base9 + check_char


def _validate_isbn10(isbn10: str) -> bool:
    """Validate ISBN-10 check digit."""
    if not re.match(r'^\d{9}[\dX]$', isbn10, re.IGNORECASE):
        return False
    total = sum(
        (10 - i) * (10 if c.upper() == 'X' else int(c))
        for i, c in enumerate(isbn10)
    )
    return total % 11 == 0


def _validate_isbn13(isbn13: str) -> bool:
    """Validate ISBN-13 check digit."""
    if not re.match(r'^\d{13}$', isbn13):
        return False
    total = sum(
        int(d) * (1 if i % 2 == 0 else 3)
        for i, d in enumerate(isbn13[:12])
    )
    check = (10 - (total % 10)) % 10
    return check == int(isbn13[12])


def _isbn13_check_digit(first12: str) -> int:
    """Compute the check digit for the first 12 digits of an ISBN-13."""
    total = sum(
        int(d) * (1 if i % 2 == 0 else 3)
        for i, d in enumerate(first12)
    )
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
            raw = resp.json()
            data = _parse_isbn_response(raw, isbn_13)
            # If we got works key, try to enrich with work data
            if raw.get('works'):
                work_key = raw['works'][0]['key']
                data.update(_fetch_work_data(work_key))
    except requests.RequestException as e:
        logger.warning('Open Library ISBN request failed for %s: %s', isbn_13, e)

    if not data.get('title'):
        # Fallback: search API
        try:
            resp = requests.get(
                OPEN_LIBRARY_SEARCH_URL,
                params={'isbn': isbn_13, 'limit': 1},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                results = resp.json().get('docs', [])
                if results:
                    data.update(_parse_search_result(results[0], isbn_13))
        except requests.RequestException as e:
            logger.warning('Open Library search fallback failed for %s: %s', isbn_13, e)

    # Always set the cover URL (may not exist, but that's okay)
    if not data.get('cover_image_url'):
        data['cover_image_url'] = OPEN_LIBRARY_COVER_URL.format(isbn=isbn_13)

    return data


def _parse_isbn_response(raw: dict, isbn_13: str) -> dict:
    """Parse the raw response from Open Library ISBN endpoint."""
    data = {}

    data['title'] = raw.get('title', '')
    data['open_library_key'] = raw.get('key', '')

    # Authors: dereference if needed
    authors = []
    for author_ref in raw.get('authors', []):
        if isinstance(author_ref, dict) and 'key' in author_ref:
            name = _fetch_author_name(author_ref['key'])
            if name:
                authors.append(name)
        elif isinstance(author_ref, dict) and 'name' in author_ref:
            authors.append(author_ref['name'])
    data['authors'] = authors

    data['publisher'] = raw.get('publishers', [None])[0] if raw.get('publishers') else None
    data['page_count'] = raw.get('number_of_pages')
    data['physical_format'] = _normalize_physical_format(raw.get('physical_format') or raw.get('format'))

    # Publish year
    publish_date = raw.get('publish_date', '')
    if publish_date:
        year_match = re.search(r'\d{4}', publish_date)
        data['publish_year'] = int(year_match.group()) if year_match else None

    subjects = raw.get('subjects', [])
    data['subjects'] = subjects[:20] if subjects else []

    # Description
    desc = raw.get('description')
    if isinstance(desc, dict):
        data['description'] = desc.get('value', '')
    elif isinstance(desc, str):
        data['description'] = desc

    return data


def _parse_search_result(doc: dict, isbn_13: str) -> dict:
    """Parse a search result doc from Open Library search API."""
    data = {}
    data['title'] = doc.get('title', '')
    data['authors'] = doc.get('author_name', [])
    data['publisher'] = doc.get('publisher', [None])[0] if doc.get('publisher') else None
    data['publish_year'] = doc.get('first_publish_year')
    data['page_count'] = doc.get('number_of_pages_median')
    data['physical_format'] = _normalize_physical_format(doc.get('format'))
    subjects = doc.get('subject', [])
    data['subjects'] = subjects[:20] if subjects else []
    return data


def _normalize_physical_format(value) -> str | None:
    """Normalize Open Library format values to a compact display string."""
    if not value:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get('name') or value.get('value')
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
            raw = resp.json()
            desc = raw.get('description')
            if isinstance(desc, dict):
                data['description'] = desc.get('value', '')
            elif isinstance(desc, str):
                data['description'] = desc
            subjects = raw.get('subjects', [])
            if subjects:
                data['subjects'] = subjects[:20]
    except requests.RequestException as e:
        logger.debug('Work data fetch failed for %s: %s', work_key, e)
    return data


def _fetch_author_name(author_key: str) -> str | None:
    """Fetch an author's name from the Open Library Authors endpoint."""
    try:
        resp = requests.get(
            f'https://openlibrary.org{author_key}.json',
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get('name')
    except requests.RequestException:
        pass
    return None
