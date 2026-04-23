export function getBookPrimaryAuthor(book) {
  if (!book) {
    return null;
  }

  if (Array.isArray(book.authors)) {
    const firstAuthor = book.authors.find(
      (author) => typeof author === 'string' && author.trim()
    );
    if (firstAuthor) {
      return firstAuthor;
    }
  }

  if (typeof book.authors === 'string' && book.authors.trim()) {
    return book.authors;
  }

  if (typeof book.author === 'string' && book.author.trim()) {
    return book.author;
  }

  return null;
}

/**
 * Rewrite an Open Library cover URL to go through our Cloudflare Pages proxy
 * (/covers/*) so images are served from the edge cache instead of hitting
 * covers.openlibrary.org on every cold load.
 *
 * Any other URL (e.g. S3, Google Books) is returned unchanged.
 */
function proxyCoverUrl(url) {
  if (!import.meta.env.PROD) {
    return url;
  }

  try {
    const parsed = new URL(url);
    if (parsed.hostname === 'covers.openlibrary.org') {
      // e.g. /b/isbn/9780201616224-M.jpg
      return `/covers${parsed.pathname}`;
    }
  } catch {
    // Not a valid absolute URL — return as-is.
  }
  return url;
}

export function getBookCoverUrl(book) {
  if (!book) {
    return null;
  }

  const raw = book.cover_image_url ?? book.cover_url ?? book.thumbnail ?? null;
  return raw ? proxyCoverUrl(raw) : null;
}

export function getBookIsbn(book) {
  if (!book) {
    return null;
  }

  return book.isbn_13 ?? book.isbn ?? book.isbn_10 ?? null;
}

export function getBookPublishYear(book) {
  if (!book) {
    return null;
  }

  return book.publish_year ?? book.published_year ?? null;
}