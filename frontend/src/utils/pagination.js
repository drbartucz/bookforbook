/**
 * parsePaginatedResponse
 *
 * Enforces the DRF paginated envelope: { results: [...], count: N }.
 * Returns { results, count } on success, { results: [], count: 0 } when
 * data is null/undefined (query still loading), and throws on any other shape
 * so we catch API contract violations early rather than silently rendering
 * an empty list.
 */
export function parsePaginatedResponse(data) {
    if (data == null) {
        return { results: [], count: 0 };
    }
    if (!Array.isArray(data.results) || typeof data.count !== 'number') {
        throw new Error(
            `Expected paginated response { results: [], count: N } but received: ${JSON.stringify(data)?.slice(0, 200)}`
        );
    }
    return { results: data.results, count: data.count };
}
