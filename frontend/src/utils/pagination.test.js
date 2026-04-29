import { describe, it, expect } from 'vitest';
import { parsePaginatedResponse } from './pagination.js';

describe('parsePaginatedResponse', () => {
    it('returns empty results when data is null', () => {
        expect(parsePaginatedResponse(null)).toEqual({ results: [], count: 0 });
    });

    it('returns empty results when data is undefined', () => {
        expect(parsePaginatedResponse(undefined)).toEqual({ results: [], count: 0 });
    });

    it('returns results and count for a valid paginated envelope', () => {
        const data = { results: [{ id: 1 }, { id: 2 }], count: 2 };
        expect(parsePaginatedResponse(data)).toEqual({ results: [{ id: 1 }, { id: 2 }], count: 2 });
    });

    it('returns results and count when count is 0 in envelope', () => {
        expect(parsePaginatedResponse({ results: [], count: 0 })).toEqual({ results: [], count: 0 });
    });

    it('normalises a plain array (APIView endpoints) into { results, count }', () => {
        const arr = [{ id: 1 }, { id: 2 }];
        expect(parsePaginatedResponse(arr)).toEqual({ results: arr, count: 2 });
    });

    it('normalises an empty plain array', () => {
        expect(parsePaginatedResponse([])).toEqual({ results: [], count: 0 });
    });

    it('throws when results is not an array', () => {
        expect(() => parsePaginatedResponse({ results: 'oops', count: 1 })).toThrow(
            /expected paginated response/i
        );
    });

    it('throws when count is not a number', () => {
        expect(() => parsePaginatedResponse({ results: [], count: '5' })).toThrow(
            /expected paginated response/i
        );
    });

    it('throws when results key is missing', () => {
        expect(() => parsePaginatedResponse({ items: [], count: 1 })).toThrow(
            /expected paginated response/i
        );
    });

    it('throws on a completely unrecognised scalar', () => {
        expect(() => parsePaginatedResponse(42)).toThrow(
            /expected paginated response/i
        );
    });
});
