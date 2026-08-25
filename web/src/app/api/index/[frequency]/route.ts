import { badRequest, frequencyParam, searchParamsToObject, seriesQuery } from "@/lib/params";
import { getIndexMeta, getSeries } from "@/lib/queries";
import { withProvenance } from "@/lib/responses";
import { cacheHeaders } from "@/lib/cache";

// Rendered per request: a build must never require database access.
// Freshness is handled by CDN caching (see cacheHeaders / Cache-Control).
export const dynamic = "force-dynamic";

/** GET /api/index/{daily|weekly|monthly}?start=&end=&includeFailed= */
export async function GET(
  request: Request,
  context: { params: Promise<{ frequency: string }> },
): Promise<Response> {
  const { frequency: raw } = await context.params;
  const frequency = frequencyParam.safeParse(raw);
  if (!frequency.success) {
    return badRequest("frequency must be daily, weekly or monthly");
  }

  const query = seriesQuery.safeParse(searchParamsToObject(new URL(request.url)));
  if (!query.success) {
    return badRequest("invalid query parameters", query.error.issues);
  }

  const [series, meta] = await Promise.all([
    getSeries(frequency.data, query.data),
    getIndexMeta(),
  ]);

  return Response.json(
    await withProvenance({
      frequency: frequency.data,
      basePeriod: meta.basePeriod,
      baseValue: meta.baseValue,
      n: series.length,
      series,
    }),
    { headers: cacheHeaders() },
  );
}
