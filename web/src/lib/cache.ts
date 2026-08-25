/**
 * CDN caching for dynamically rendered responses.
 *
 * Pages and API routes are rendered per request so that a build never needs
 * database access — a deploy must not fail because the database is asleep or
 * behind a VPN. Freshness comes from the edge cache instead: serve a cached copy
 * for `maxAge`, then serve it stale while revalidating in the background.
 *
 * The pipeline writes at most once a day, so five minutes is generous.
 */
export function cacheHeaders(maxAge = 300, staleWhileRevalidate = 3600): HeadersInit {
  return {
    "Cache-Control": `public, s-maxage=${maxAge}, stale-while-revalidate=${staleWhileRevalidate}`,
  };
}
