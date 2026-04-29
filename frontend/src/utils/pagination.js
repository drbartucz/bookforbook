/**
 * parsePaginatedResponse
 *
 * Normalises two response shapes produced by the backend:
 *   - Plain array  (APIView endpoints that skip DRF pagination)
 *   - Paginated envelope { results: [...], count: N }  (GenericAPIView endpoints)
 *
 * Returns { results, count } on success, { results: [], count: 0 } while the
 * query is still loading (data is null/undefined), and throws on any other
 * shape so contract violations are caught early rather than silently rendering
 * an empty list.
 */
export function parsePaginatedResponse(data) {
    if (data == null) {
        return { results: [], count: 0 };
    }
    if (Array.isArray(data)) {
        return { results: data, count: data.length };
    }
    if (Array.isArray(data.results) && typeof data.count === 'number') {
        return { results: data.results, count: data.count };
    }
    throw new Error(
        `Expected paginated response { results: [], count: N } or a plain array, but received: ${JSON.stringify(data)?.slice(0, 200)}`
    );
}
