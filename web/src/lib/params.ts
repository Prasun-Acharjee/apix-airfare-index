import { z } from "zod";
import { FREQUENCIES } from "@/lib/types";

/** Query/route parameter schemas. Every handler validates before touching the DB. */

export const frequencyParam = z.enum(FREQUENCIES);

const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "expected an ISO date, YYYY-MM-DD");

export const seriesQuery = z.object({
  start: isoDate.optional(),
  end: isoDate.optional(),
  includeFailed: z
    .enum(["true", "false"])
    .optional()
    .transform((v) => v === "true"),
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
