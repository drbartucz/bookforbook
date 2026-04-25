import { describe, expect, it } from 'vitest';
import { getBookCoverUrl, getBookIsbn, getBookPrimaryAuthor, getBookPublishYear } from './book.js';

describe('getBookPrimaryAuthor — branch coverage', () => {
    it('returns null when book is null', () => {
        expect(getBookPrimaryAuthor(null)).toBeNull();
    });

    it('returns null when book is undefined', () => {
        expect(getBookPrimaryAuthor(undefined)).toBeNull();
    });

    it('returns first string element from authors array', () => {
        expect(getBookPrimaryAuthor({ authors: ['Alice', 'Bob'] })).toBe('Alice');
    });

    it('skips empty strings in authors array and returns first non-empty', () => {
        expect(getBookPrimaryAuthor({ authors: ['', '  ', 'Charlie'] })).toBe('Charlie');
    });

    it('returns null when authors is an empty array', () => {
        expect(getBookPrimaryAuthor({ authors: [] })).toBeNull();
    });

    it('returns null when all array elements are empty strings', () => {
        expect(getBookPrimaryAuthor({ authors: ['', '   '] })).toBeNull();
    });

    it('returns authors when it is a non-empty string', () => {
        expect(getBookPrimaryAuthor({ authors: 'Diane' })).toBe('Diane');
    });

    it('returns null when authors is a whitespace-only string', () => {
        expect(getBookPrimaryAuthor({ authors: '   ' })).toBeNull();
    });

    it('falls back to book.author string when authors is absent', () => {
        expect(getBookPrimaryAuthor({ author: 'Eve' })).toBe('Eve');
    });

    it('returns null when book.author is a whitespace-only string', () => {
        expect(getBookPrimaryAuthor({ author: '   ' })).toBeNull();
    });

    it('returns null when book has no author fields', () => {
        expect(getBookPrimaryAuthor({ title: 'No Author Book' })).toBeNull();
    });
});

describe('getBookCoverUrl — branch coverage', () => {
    it('returns null when book is null', () => {
        expect(getBookCoverUrl(null)).toBeNull();
    });

    it('returns null when no cover fields are present', () => {
        expect(getBookCoverUrl({ title: 'No Cover' })).toBeNull();
    });

    it('returns cover_image_url when present', () => {
        expect(getBookCoverUrl({ cover_image_url: 'https://example.com/a.jpg' }))
            .toBe('https://example.com/a.jpg');
    });

    it('falls back to cover_url when no cover_image_url', () => {
        expect(getBookCoverUrl({ cover_url: 'https://example.com/b.jpg' }))
            .toBe('https://example.com/b.jpg');
    });

    it('falls back to thumbnail when no cover_image_url or cover_url', () => {
        expect(getBookCoverUrl({ thumbnail: 'https://example.com/c.jpg' }))
            .toBe('https://example.com/c.jpg');
    });

    it('returns null when raw url is null', () => {
        expect(getBookCoverUrl({ cover_image_url: null })).toBeNull();
    });
});

describe('getBookIsbn — branch coverage', () => {
    it('returns null when book is null', () => {
        expect(getBookIsbn(null)).toBeNull();
    });

    it('returns isbn_13 when present', () => {
        expect(getBookIsbn({ isbn_13: '9780000000001' })).toBe('9780000000001');
    });

    it('falls back to isbn when no isbn_13', () => {
        expect(getBookIsbn({ isbn: '0000000001' })).toBe('0000000001');
    });

    it('falls back to isbn_10 when no isbn or isbn_13', () => {
        expect(getBookIsbn({ isbn_10: '0000000002' })).toBe('0000000002');
    });

    it('returns null when no isbn fields present', () => {
        expect(getBookIsbn({ title: 'No ISBN' })).toBeNull();
    });
});

describe('getBookPublishYear — branch coverage', () => {
    it('returns null when book is null', () => {
        expect(getBookPublishYear(null)).toBeNull();
    });

    it('returns publish_year when present', () => {
        expect(getBookPublishYear({ publish_year: 2001 })).toBe(2001);
    });

    it('falls back to published_year when no publish_year', () => {
        expect(getBookPublishYear({ published_year: 1999 })).toBe(1999);
    });

    it('returns null when no year fields present', () => {
        expect(getBookPublishYear({ title: 'No Year' })).toBeNull();
    });
});
