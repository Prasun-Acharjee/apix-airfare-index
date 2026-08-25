import { Suspense } from "react";
import { AdvanceWindowChart } from "@/components/AdvanceWindowChart";
import { FrequencyTabs } from "@/components/FrequencyTabs";
import { IndexChart } from "@/components/IndexChart";
import { RouteHeatmap } from "@/components/RouteHeatmap";
import { SeriesTable } from "@/components/SeriesTable";
import { Banner, Card, QualityPill, Tile } from "@/components/Ui";
import { formatDay, num, pct, qualityLabel, signedPct } from "@/lib/format";
import {
  getIndexMeta,
  getProvenance,
  getRouteMatrix,
  getSeries,
} from "@/lib/queries";
import { isFrequency, type Frequency } from "@/lib/types";

// Rendered per request: a build must never require database access.
// Freshness is handled by CDN caching (see cacheHeaders / Cache-Control).
export const dynamic = "force-dynamic";

const PERIOD_WORD: Record<Frequency, string> = {
  daily: "day",
  weekly: "week",
  monthly: "month",
};

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const raw = typeof params.frequency === "string" ? params.frequency : "daily";
  const frequency: Frequency = isFrequency(raw) ? raw : "daily";

  const [series, meta, provenance, matrix] = await Promise.all([
    getSeries(frequency),
    getIndexMeta(),
    getProvenance(),
    getRouteMatrix(),
  ]);

  if (series.length === 0) {
    return (
      <main>
        <Banner>
          <b>No index data.</b> Run{" "}
          <code className="rounded bg-[var(--surface-0)] px-1">
            python scripts/seed_postgres.py
          </code>{" "}
          against this <code>DATABASE_URL</code> to populate it.
        </Banner>
      </main>
    );
  }

  const last = series[series.length - 1];
  const prev = series[series.length - 2];
  if (!last) return null;
  const change = prev ? (last.value / prev.value - 1) * 100 : 0;

  return (
    <main>
      <p className="text-[14px] text-[var(--text-secondary)]">
        Prototype index for the CPI Transport &amp; Communication sub-group · base{" "}
        {formatDay(meta.basePeriod)} = {meta.baseValue}
      </p>

      {provenance.synthetic ? (
        <Banner>
          <b>Synthetic data.</b> This series is computed from simulated quotes to
          demonstrate the pipeline. It is not a measurement of airfare inflation and
          must not be cited as one.
        </Banner>
      ) : null}

      <div className="my-[18px] grid grid-cols-[repeat(auto-fit,minmax(178px,1fr))] gap-3">
        <Tile label="Index level" value={num(last.value)} sub={formatDay(last.onDate)} />
        <Tile
          label={`Change (${PERIOD_WORD[frequency]})`}
          value={signedPct(change)}
          sub="vs previous period"
        />
        <Tile
          label="Basket coverage"
          value={pct(last.coverage)}
          sub={`${last.nCellsMatched} cells observed`}
        />
        <Tile
          label="Carried by imputation"
          value={pct(last.imputationShare)}
          sub={<QualityPill quality={last.quality}>{qualityLabel[last.quality]}</QualityPill>}
        />
      </div>

      <Card
        title="Index level"
        note="Chained weighted geometric index. Points flagged not-publishable are excluded."
        actions={
          <Suspense fallback={null}>
            <FrequencyTabs active={frequency} />
          </Suspense>
        }
      >
        <IndexChart series={series} />
        <SeriesTable series={series} />
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card
          title="Fare by advance-purchase window"
          note={`Mean observed fare per booking window${
            matrix.on ? `, ${formatDay(matrix.on)}` : ""
          }. One measure across an ordered dimension, so one hue.`}
        >
          <AdvanceWindowChart cells={matrix.cells} />
        </Card>

        <Card
          title="Where the numbers come from"
          note="Every index point ships with its own coverage and imputation share."
        >
          <dl className="text-[13.5px]">
            {provenance.sources.map((s) => (
              <div
                key={s.sourceId}
                className="flex items-baseline justify-between gap-3 border-b border-[var(--border)] py-2 last:border-0"
              >
                <dt className="font-medium">
                  {s.sourceId}
                  {s.sourceId.startsWith("sim_") ? (
                    <span className="ml-2 text-[11.5px] text-[var(--warning)]">synthetic</span>
                  ) : null}
                </dt>
                <dd className="tabular text-right text-[var(--text-secondary)]">
                  {s.cellDays.toLocaleString("en-IN")} cell-days
                  <span className="block text-[11.5px] text-[var(--text-muted)]">
                    {s.first} → {s.last}
                  </span>
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-[12.5px] text-[var(--text-muted)]">
            Weights: {meta.weightSource}
          </p>
        </Card>
      </div>

      <Card
        title="Route × window fare matrix"
        note="Latest observed fare, ₹. Stronger colour = higher fare; the value is printed on every cell."
      >
        <RouteHeatmap cells={matrix.cells} />
      </Card>
    </main>
  );
}
