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

export function getBookCoverUrl(book) {
  if (!book) {
    return null;
  }

  return book.cover_image_url ?? book.cover_url ?? book.thumbnail ?? null;
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