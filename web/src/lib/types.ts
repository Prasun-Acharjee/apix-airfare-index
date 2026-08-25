/**
 * Domain types for APIx.
 *
 * These mirror the Python dataclasses in `apix/models.py` and the SQL schema in
 * `db/migrations/001_init.sql`. The database is the contract between the two
 * runtimes; these types are the TypeScript half of it.
 */

export const FREQUENCIES = ["daily", "weekly", "monthly"] as const;
export type Frequency = (typeof FREQUENCIES)[number];

export function isFrequency(value: string): value is Frequency {
  return (FREQUENCIES as readonly string[]).includes(value);
}

/** Publication quality of an index point, driven by imputation share and coverage. */
export type Quality = "ok" | "warn" | "fail";

/** How a source's crawl policy was assessed. See METHODOLOGY.md §6. */
export type ComplianceStatus =
  | "permitted"
  | "permitted_with_delay"
  | "blocked"
  | "blocked_partial"
  | "blocked_unverifiable";

export interface IndexPoint {
  /** ISO date, `YYYY-MM-DD`. */
  readonly onDate: string;
  readonly value: number;
  readonly frequency: Frequency;
  readonly nCellsMatched: number;
  readonly nCellsImputed: number;
  /** Weight-share of the basket actually observed or imputed, 0–1. */
  readonly coverage: number;
  /** Weight-share carried by imputation rather than observation, 0–1. */
  readonly imputationShare: number;
  readonly quality: Quality;
  readonly notes: readonly string[];
}

export interface InflationPoint {
  readonly onDate: string;
  readonly index: number;
  /** Percent change against the point `periods` earlier. */
  readonly changePct: number;
  readonly quality: Quality;
}

/** One (route × advance-window) cell of the latest observed fare matrix. */
export interface RouteCell {
  readonly route: string;
  readonly advanceDays: number;
  readonly price: number;
  readonly nQuotes: number;
}

export interface SourceRecord {
  readonly id: string;
  readonly name: string;
  readonly kind: "airline" | "ota" | string;
  readonly carrierCodes: readonly string[];
  readonly baseUrl: string;
  readonly status: ComplianceStatus;
  readonly collectable: boolean;
  /** Why this verdict — quoted from the robots.txt audit. */
  readonly reason: string;
  readonly crawlDelayS: number;
  readonly auditedAt: string;
}

export interface CollectionLogEntry {
  readonly id: string;
  readonly runAt: string;
  readonly sourceId: string;
  readonly url: string | null;
  readonly outcome: string;
  readonly detail: string | null;
  readonly nQuotes: number;
}

export interface BasketWeight {
  readonly kind: "route" | "carrier" | "window";
  readonly key: string;
  readonly weight: number;
  readonly label: string | null;
}

export interface IndexMeta {
  readonly basePeriod: string;
  readonly baseValue: number;
  readonly weightSource: string;
  readonly updatedAt: string;
}

/**
 * Where the numbers came from.
 *
 * `synthetic` is true when any cell price was produced by the simulator rather
 * than collected. Every surface that shows a number must show this too — there
 * is no way to turn the disclosure off.
 */
export interface Provenance {
  readonly synthetic: boolean;
  readonly sources: readonly {
    readonly sourceId: string;
    readonly cellDays: number;
    readonly first: string;
    readonly last: string;
  }[];
}

export interface SeriesResponse {
  readonly frequency: Frequency;
  readonly basePeriod: string;
  readonly baseValue: number;
  readonly n: number;
  readonly provenance: Provenance;
  readonly series: readonly IndexPoint[];
  readonly warning?: string;
}
