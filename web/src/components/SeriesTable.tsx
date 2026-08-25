import { num, pct, qualityLabel } from "@/lib/format";
import { QualityPill } from "@/components/Ui";
import type { IndexPoint } from "@/lib/types";

/**
 * The table view. Present on purpose: it is the accessible equivalent of the
 * chart, and the relief for colour-only encoding.
 */
export function SeriesTable({ series }: { series: readonly IndexPoint[] }) {
  return (
    <details className="mt-2">
      <summary className="cursor-pointer py-1.5 text-[13px] text-[var(--text-secondary)]">
        Table view ({series.length} points)
      </summary>
      <div className="mt-2 max-h-[420px] overflow-auto">
        <table className="tabular w-full border-collapse text-[13px]">
          <thead className="sticky top-0 bg-[var(--surface-1)]">
            <tr>
              {["Date", "Index", "Coverage", "Imputed", "Cells", "Quality"].map((h, i) => (
                <th
                  key={h}
                  className={
                    "border-b border-[var(--border)] px-2.5 py-1.5 text-[11.5px] font-medium uppercase tracking-[0.04em] text-[var(--text-muted)] " +
                    (i === 0 || i === 5 ? "text-left" : "text-right")
                  }
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {series.map((p) => (
              <tr key={p.onDate}>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5">{p.onDate}</td>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5 text-right">
                  {num(p.value)}
                </td>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5 text-right">
                  {pct(p.coverage)}
                </td>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5 text-right">
                  {pct(p.imputationShare)}
                </td>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5 text-right">
                  {p.nCellsMatched}
                </td>
                <td className="border-b border-[var(--border)] px-2.5 py-1.5">
                  <QualityPill quality={p.quality}>{qualityLabel[p.quality]}</QualityPill>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
