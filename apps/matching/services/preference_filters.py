import re
import unicodedata

from apps.inventory.models import WishlistItem


ABRIDGED_PATTERN = re.compile(r"\babridg(?:ed|ement)\b", re.IGNORECASE)


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    base = value.split(":", 1)[0]
    decomposed = unicodedata.normalize("NFKD", base)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9\s]", "", ascii_only.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def extract_author_tokens(authors) -> set[str]:
    if isinstance(authors, str):
        names = [authors]
    elif isinstance(authors, list):
        names = [a for a in authors if isinstance(a, str)]
    else:
        names = []
    return {name.strip().lower() for name in names if name and name.strip()}


def normalize_format(format_value: str | None) -> str | None:
    if not format_value:
        return None
    text = format_value.lower()
    if "hard" in text:
        return "hardcover"
    if "mass" in text:
        return "mass_market"
    if "large" in text:
        return "large_print"
    if "audio" in text:
        return "audiobook"
    if "paper" in text or "soft" in text:
        return "paperback"
    return None


def is_abridged(book) -> bool:
    text = " ".join(
        [
            str(book.title or ""),
            str(book.description or ""),
            str(book.physical_format or ""),
        ]
    )
    return bool(ABRIDGED_PATTERN.search(text))


def wishlist_allows_book(wish: WishlistItem, offered_book) -> bool:
    """Return True if the offered book satisfies the wishlist edition preferences."""
    preference = wish.edition_preference

    if preference == WishlistItem.EditionPreference.EXACT:
        return offered_book.id == wish.book_id

    # Related-edition heuristic:
    # same normalized base title, with optional author overlap depending on preference.
    wanted_title = normalize_title(wish.book.title)
    offered_title = normalize_title(offered_book.title)
    if not wanted_title or wanted_title != offered_title:
        return False

    allow_translations = wish.allow_translations or (
        preference == WishlistItem.EditionPreference.ANY_LANGUAGE
    )
    if not allow_translations:
        wanted_authors = extract_author_tokens(wish.book.authors)
        offered_authors = extract_author_tokens(offered_book.authors)
        if (
            wanted_authors
            and offered_authors
            and wanted_authors.isdisjoint(offered_authors)
        ):
            return False

    if wish.exclude_abridged and is_abridged(offered_book):
        return False

    if wish.format_preferences:
        offered_format = normalize_format(offered_book.physical_format)
        if offered_format not in set(wish.format_preferences):
            return False

    return True
