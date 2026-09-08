import "server-only";
import { sql } from "@/lib/db";
import { ALL_ROUTES } from "@/lib/types";
import type {
  BasketWeight,
  CollectionLogEntry,
  Frequency,
  IndexMeta,
  IndexPoint,
  InflationPoint,
  Provenance,
  Quality,
  RouteCell,
  SourceRecord,
} from "@/lib/types";

/**
 * Every read the site performs. Row shapes are declared explicitly rather than
 * inferred, so a schema change surfaces as a type error here instead of as
 * `undefined` on a page.
 */

const QUALITIES: readonly Quality[] = ["ok", "warn", "fail"];
const asQuality = (v: string): Quality =>
  (QUALITIES as readonly string[]).includes(v) ? (v as Quality) : "fail";

interface IndexPointRow {
  frequency: string;
  on_date: string;
  value: number;
  n_cells_matched: number;
  n_cells_imputed: number;
  coverage: number;
  imputation_share: number;
  quality: string;
  notes: unknown;
}

function toNotes(raw: unknown): readonly string[] {
  if (Array.isArray(raw)) return raw.filter((n): n is string => typeof n === "string");
  return [];
}

function toIndexPoint(r: IndexPointRow, frequency: Frequency): IndexPoint {
  return {
    onDate: r.on_date,
    value: r.value,
    frequency,
    nCellsMatched: r.n_cells_matched,
    nCellsImputed: r.n_cells_imputed,
    coverage: r.coverage,
    imputationShare: r.imputation_share,
    quality: asQuality(r.quality),
    notes: toNotes(r.notes),
  };
}

export interface SeriesOptions {
  readonly start?: string | undefined;
  readonly end?: string | undefined;
  /**
   * Points flagged `fail` are INCLUDED by default and badged in the UI, so the
   * series runs to the latest collection day rather than stopping silently at
   * the last clean one. Hiding them made an outage indistinguishable from a
   * quiet market: the site simply stopped advancing and said nothing.
   *
   * Pass `false` for the clean series — the one to use for any analysis where a
   * point resting on 90% imputation would be misleading.
   */
  readonly includeFailed?: boolean | undefined;
  /**
   * Which city pair's index to return. Defaults to ALL_ROUTES — the headline
   * series weighted across every pair, which is NOT the average of the route
   * series: each route is renormalised within itself, while the headline
   * weights routes by passenger share.
   */
  readonly route?: string | undefined;
}

export async function getSeries(
  frequency: Frequency,
  opts: SeriesOptions = {},
): Promise<readonly IndexPoint[]> {
  const rows = await sql<IndexPointRow[]>`
    SELECT frequency, on_date, value, n_cells_matched, n_cells_imputed,
           coverage, imputation_share, quality, notes
    FROM index_point
    WHERE frequency = ${frequency}
      AND route = ${opts.route ?? ALL_ROUTES}
      ${opts.start ? sql`AND on_date >= ${opts.start}` : sql``}
      ${opts.end ? sql`AND on_date <= ${opts.end}` : sql``}
      ${opts.includeFailed === false ? sql`AND quality <> 'fail'` : sql``}
    ORDER BY on_date
  `;
  return rows.map((r) => toIndexPoint(r, frequency));
}

/**
 * Period-over-period change — the number a policy user actually asks for.
 * Computed from the same series the site displays, so the percentage and the
 * chart can never disagree. Each point carries its own `quality`, so a change
 * computed across a provisional point can be identified as one.
 */
export async function getInflation(
  frequency: Frequency,
  periods = 1,
): Promise<readonly InflationPoint[]> {
  const series = await getSeries(frequency);
  const out: InflationPoint[] = [];
  for (let i = periods; i < series.length; i += 1) {
    const cur = series[i];
    const prev = series[i - periods];
    if (!cur || !prev || prev.value === 0) continue;
    out.push({
      onDate: cur.onDate,
      index: Number(cur.value.toFixed(3)),
      changePct: Number(((cur.value / prev.value - 1) * 100).toFixed(3)),
      quality: cur.quality,
    });
  }
  return out;
}

interface RouteCellRow {
  route: string;
  advance_days: number;
  price: number;
  n_quotes: number;
}

/**
 * The latest observed fare matrix. Imputed cells are excluded on purpose: this
 * view is "what did we actually see", not "what does the index assume".
 */
export async function getRouteMatrix(on?: string): Promise<{
  readonly on: string | null;
  readonly cells: readonly RouteCell[];
}> {
  const day =
    on ??
    (
      await sql<{ d: string | null }[]>`
        SELECT MAX(collected_on)::text AS d FROM cell_price WHERE imputed = FALSE
      `
    )[0]?.d ??
    null;

  if (!day) return { on: null, cells: [] };

  const rows = await sql<RouteCellRow[]>`
    SELECT route, advance_days, AVG(price)::float8 AS price, SUM(n_quotes)::int AS n_quotes
    FROM cell_price
    WHERE collected_on = ${day} AND imputed = FALSE
    GROUP BY route, advance_days
    ORDER BY route, advance_days
  `;
  return {
    on: day,
    cells: rows.map((r) => ({
      route: r.route,
      advanceDays: r.advance_days,
      price: r.price,
      nQuotes: r.n_quotes,
    })),
  };
}

interface SourceRow {
  id: string;
  name: string;
  kind: string;
  carrier_codes: string[];
  base_url: string;
  status: string;
  collectable: boolean;
  reason: string;
  crawl_delay_s: number;
  audited_at: Date;
}

export async function getSources(): Promise<readonly SourceRecord[]> {
  const rows = await sql<SourceRow[]>`
    SELECT id, name, kind, carrier_codes, base_url, status, collectable,
           reason, crawl_delay_s, audited_at
    FROM source
    ORDER BY collectable DESC, name
  `;
  return rows.map((r) => ({
    id: r.id,
    name: r.name,
    kind: r.kind,
    carrierCodes: r.carrier_codes,
    baseUrl: r.base_url,
    status: r.status as SourceRecord["status"],
    collectable: r.collectable,
    reason: r.reason,
    crawlDelayS: r.crawl_delay_s,
    auditedAt: r.audited_at.toISOString(),
  }));
}

/**
 * Provenance for whatever is currently loaded.
 *
 * `synthetic` keys off the `sim_` source-id prefix written by
 * `apix/collect/simulator.py`. It is computed from the data, not configured, so
 * it cannot drift out of sync with what is actually being displayed.
 */
export async function getProvenance(): Promise<Provenance> {
  const rows = await sql<
    { source_id: string; cell_days: number; first: string; last: string }[]
  >`
    SELECT source_id,
           COUNT(*)::int        AS cell_days,
           MIN(collected_on)    AS first,
           MAX(collected_on)    AS last
    FROM cell_price
    GROUP BY source_id
    ORDER BY cell_days DESC
  `;
  return {
    synthetic: rows.some((r) => r.source_id.startsWith("sim_")),
    sources: rows.map((r) => ({
      sourceId: r.source_id,
      cellDays: r.cell_days,
      first: r.first,
      last: r.last,
    })),
  };
}

export async function getIndexMeta(): Promise<IndexMeta> {
  const rows = await sql<
    { base_period: string; base_value: number; weight_source: string; updated_at: Date }[]
  >`SELECT base_period, base_value, weight_source, updated_at FROM index_meta WHERE id = TRUE`;
  const r = rows[0];
  if (!r) {
    return {
      basePeriod: "—",
      baseValue: 100,
      weightSource: "not seeded",
      updatedAt: new Date(0).toISOString(),
    };
  }
  return {
    basePeriod: r.base_period,
    baseValue: r.base_value,
    weightSource: r.weight_source,
    updatedAt: r.updated_at.toISOString(),
  };
}

/**
 * City pairs that actually have an index series, newest-collection-day first by
 * name. A route only appears once it has been observed on two days — one day
 * gives no link to chain — so this is shorter than the configured basket
 * whenever a pair is new or has gone quiet.
 */
export async function getIndexedRoutes(frequency: Frequency): Promise<readonly string[]> {
  const rows = await sql<{ route: string }[]>`
    SELECT DISTINCT route FROM index_point
    WHERE frequency = ${frequency} AND route <> ${ALL_ROUTES}
    ORDER BY route
  `;
  return rows.map((r) => r.route);
}

export async function getBasketWeights(): Promise<readonly BasketWeight[]> {
  const rows = await sql<
    { kind: string; key: string; weight: number; label: string | null }[]
  >`SELECT kind, key, weight, label FROM basket_weight ORDER BY kind, weight DESC`;
  return rows.map((r) => ({
    kind: r.kind as BasketWeight["kind"],
    key: r.key,
    weight: r.weight,
    label: r.label,
  }));
}

export async function getCollectionLog(limit = 200): Promise<readonly CollectionLogEntry[]> {
  const rows = await sql<
    {
      id: string;
      run_at: Date;
      source_id: string;
      url: string | null;
      outcome: string;
      detail: string | null;
      n_quotes: number;
    }[]
  >`
    SELECT id::text, run_at, source_id, url, outcome, detail, n_quotes
    FROM collection_log ORDER BY run_at DESC, id DESC LIMIT ${limit}
  `;
  return rows.map((r) => ({
    id: r.id,
    runAt: r.run_at.toISOString(),
    sourceId: r.source_id,
    url: r.url,
    outcome: r.outcome,
    detail: r.detail,
    nQuotes: r.n_quotes,
  }));
}

export async function getHealth(): Promise<{
  readonly status: "ok" | "empty";
  readonly indexPoints: number;
  readonly provenance: Provenance;
}> {
  const [{ n } = { n: 0 }] = await sql<{ n: number }[]>`
    SELECT COUNT(*)::int AS n FROM index_point
  `;
  return {
    status: n > 0 ? "ok" : "empty",
    indexPoints: n,
    provenance: await getProvenance(),
  };
}
