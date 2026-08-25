import { badRequest, routesQuery, searchParamsToObject } from "@/lib/params";
import { getRouteMatrix } from "@/lib/queries";
import { withProvenance } from "@/lib/responses";
import { cacheHeaders } from "@/lib/cache";

// Rendered per request: a build must never require database access.
// Freshness is handled by CDN caching (see cacheHeaders / Cache-Control).
export const dynamic = "force-dynamic";

/** GET /api/routes?on=YYYY-MM-DD — observed fare matrix for a collection day. */
export async function GET(request: Request): Promise<Response> {
  const query = routesQuery.safeParse(searchParamsToObject(new URL(request.url)));
  if (!query.success) {
    return badRequest("invalid query parameters", query.error.issues);
  }
  const matrix = await getRouteMatrix(query.data.on);
  return Response.json(await withProvenance(matrix), { headers: cacheHeaders() });
}
