/**
 * Cloudflare Pages Function — Open Library cover image proxy.
 *
 * Sits at /covers/* and forwards requests to covers.openlibrary.org,
 * using Cloudflare's cf fetch options so the edge caches the upstream
 * response for 30 days.  The browser Service Worker then applies its own
 * CacheFirst layer on top.
 *
 * URL mapping:
 *   /covers/b/isbn/9780201616224-M.jpg
 *   → https://covers.openlibrary.org/b/isbn/9780201616224-M.jpg
 */
export async function onRequest(context) {
  // Strip the leading /covers segment to get the upstream path.
  const url = new URL(context.request.url);
  const upstreamPath = url.pathname.replace(/^\/covers/, '') || '/';
  const originUrl = `https://covers.openlibrary.org${upstreamPath}`;

  // Only allow GET / HEAD to prevent misuse.
  const method = context.request.method.toUpperCase();
  if (method !== 'GET' && method !== 'HEAD') {
    return new Response('Method Not Allowed', { status: 405 });
  }

  let upstream;
  try {
    upstream = await fetch(originUrl, {
      method,
      headers: { 'User-Agent': 'BookForBook/1.0 (+https://bookforbook.com)' },
      // Tell Cloudflare's edge to cache the upstream response for 30 days.
      cf: {
        cacheTtl: 2_592_000, // 30 days in seconds
        cacheEverything: true,
      },
    });
  } catch {
    return new Response('Failed to reach cover origin', { status: 502 });
  }

  if (!upstream.ok) {
    return new Response('Cover not found', { status: upstream.status });
  }

  const headers = new Headers({
    'Content-Type': upstream.headers.get('Content-Type') ?? 'image/jpeg',
    // Edge and browser both cache for 30 days.
    'Cache-Control': 'public, max-age=2592000, s-maxage=2592000, immutable',
    // Allow the frontend origin to load images (CORS).
    'Access-Control-Allow-Origin': '*',
    'Vary': 'Accept-Encoding',
  });

  return new Response(upstream.body, { status: 200, headers });
}
