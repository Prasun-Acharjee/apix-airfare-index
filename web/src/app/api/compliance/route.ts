import { getSources } from "@/lib/queries";
import { cacheHeaders } from "@/lib/cache";

// Rendered per request: a build must never require database access.
// Freshness is handled by CDN caching (see cacheHeaders / Cache-Control).
export const dynamic = "force-dynamic";

const POLICY =
  "Collection is gated on robots.txt at request time and fails closed. No CAPTCHA " +
  "solving, no proxy rotation, no fingerprint spoofing. A 403, 429 or bot challenge " +
  "is recorded as a non-response and handled by imputation, never evaded.";

/** GET /api/compliance — the robots.txt audit, served. */
export async function GET(): Promise<Response> {
  const sources = await getSources();
  return Response.json(
    {
      policy: POLICY,
      collected: sources.filter((s) => s.collectable).length,
      total: sources.length,
      sources,
    },
    { headers: cacheHeaders() },
  );
}
