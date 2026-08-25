import { badRequest, frequencyParam, inflationQuery, searchParamsToObject } from "@/lib/params";
import { getInflation } from "@/lib/queries";
import { withProvenance } from "@/lib/responses";
import { cacheHeaders } from "@/lib/cache";

// Rendered per request: a build must never require database access.
// Freshness is handled by CDN caching (see cacheHeaders / Cache-Control).
export const dynamic = "force-dynamic";

/** GET /api/inflation/{frequency}?periods=1 — period-over-period percent change. */
export async function GET(
  request: Request,
  context: { params: Promise<{ frequency: string }> },
): Promise<Response> {
  const { frequency: raw } = await context.params;
  const frequency = frequencyParam.safeParse(raw);
  if (!frequency.success) {
    return badRequest("frequency must be daily, weekly or monthly");
  }
  const query = inflationQuery.safeParse(searchParamsToObject(new URL(request.url)));
  if (!query.success) {
    return badRequest("invalid query parameters", query.error.issues);
  }

  const series = await getInflation(frequency.data, query.data.periods);
  return Response.json(
    await withProvenance({ frequency: frequency.data, periods: query.data.periods, series }),
    { headers: cacheHeaders() },
  );
}
