import "server-only";
import { getProvenance } from "@/lib/queries";
import type { Provenance } from "@/lib/types";

/**
 * The disclosure that travels with every number the API serves.
 *
 * A consumer of this API must always be able to tell a statistic from a
 * demonstration. There is no parameter that suppresses it.
 */
export const SYNTHETIC_WARNING =
  "This series is computed from SYNTHETIC quotes produced by apix/collect/simulator.py. " +
  "It demonstrates the pipeline and must not be cited as a measurement of airfare inflation.";

export async function withProvenance<T extends object>(
  body: T,
): Promise<T & { provenance: Provenance; warning?: string }> {
  const provenance = await getProvenance();
  return provenance.synthetic
    ? { ...body, provenance, warning: SYNTHETIC_WARNING }
    : { ...body, provenance };
}

/** Cache reads briefly: the pipeline writes at most once a day. */
export const REVALIDATE_SECONDS = 300;
