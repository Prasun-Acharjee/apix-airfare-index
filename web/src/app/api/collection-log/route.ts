import { badRequest, logQuery, searchParamsToObject } from "@/lib/params";
import { getCollectionLog } from "@/lib/queries";
import { cacheHeaders } from "@/lib/cache";

// Rendered per request: a build must never require database access.
export const dynamic = "force-dynamic";

/** GET /api/collection-log?limit=200 — why a given day looks the way it does. */
export async function GET(request: Request): Promise<Response> {
  const query = logQuery.safeParse(searchParamsToObject(new URL(request.url)));
  if (!query.success) {
    return badRequest("invalid query parameters", query.error.issues);
  }
  const entries = await getCollectionLog(query.data.limit);
  return Response.json({ n: entries.length, entries }, { headers: cacheHeaders(60, 300) });
}
