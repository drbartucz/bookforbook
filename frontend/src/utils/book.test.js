import { describe, expect, it } from 'vitest';

import { getBookCoverUrl } from './book.js';

describe('getBookCoverUrl', () => {
  it('rewrites Open Library cover URLs through the local covers proxy in production only', () => {
    const book = {
      cover_image_url: 'https://covers.openlibrary.org/b/isbn/9780201616224-M.jpg',
    };

    const expected = import.meta.env?.PROD
      ? '/covers/b/isbn/9780201616224-M.jpg'
      : 'https://covers.openlibrary.org/b/isbn/9780201616224-M.jpg';
    expect(getBookCoverUrl(book)).toBe(expected);
  });

  it('leaves non-Open Library URLs unchanged', () => {
    const book = {
      cover_image_url: 'https://example.com/covers/clean-code.jpg',
    };

    expect(getBookCoverUrl(book)).toBe('https://example.com/covers/clean-code.jpg');
  });

  it('falls back across supported cover fields before rewriting', () => {
    const book = {
      cover_url: 'https://covers.openlibrary.org/b/isbn/9780132350884-M.jpg',
    };

    const expected = import.meta.env?.PROD
      ? '/covers/b/isbn/9780132350884-M.jpg'
      : 'https://covers.openlibrary.org/b/isbn/9780132350884-M.jpg';
    expect(getBookCoverUrl(book)).toBe(expected);
  });
});