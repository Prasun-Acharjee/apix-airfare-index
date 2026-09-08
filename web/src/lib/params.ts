import { z } from "zod";
import { FREQUENCIES } from "@/lib/types";

/** Query/route parameter schemas. Every handler validates before touching the DB. */

export const frequencyParam = z.enum(FREQUENCIES);

const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "expected an ISO date, YYYY-MM-DD");

/** A city pair as the basket writes them, or the all-routes sentinel. */
const routeParam = z
  .string()
  .regex(/^(ALL|[A-Z]{3}(-[A-Z]{3})+)$/, "expected ALL or a city pair like DEL-BOM");

export const seriesQuery = z.object({
  start: isoDate.optional(),
  end: isoDate.optional(),
  route: routeParam.optional(),
  // Absent must stay undefined, NOT false. getSeries treats an explicit `false`
  // as "give me the clean series"; collapsing undefined to false here would make
  // every caller that omits the parameter silently get the filtered series,
  // which is the behaviour the site deliberately moved away from.
  includeFailed: z
    .enum(["true", "false"])
    .optional()
    .transform((v) => (v === undefined ? undefined : v === "true")),
});

export const inflationQuery = z.object({
  periods: z.coerce.number().int().min(1).max(365).default(1),
});

export const logQuery = z.object({
  limit: z.coerce.number().int().min(1).max(2000).default(200),
});

export const routesQuery = z.object({
  on: isoDate.optional(),
});

/** Turn a `URLSearchParams` into a plain record for zod. */
export const searchParamsToObject = (url: URL): Record<string, string> =>
  Object.fromEntries(url.searchParams.entries());

export function badRequest(message: string, issues?: unknown): Response {
  return Response.json({ error: message, issues }, { status: 400 });
}
