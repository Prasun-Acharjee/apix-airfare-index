"use client";

import { useMemo, useState } from "react";
import { inr } from "@/lib/format";
import type { RouteCell } from "@/lib/types";

const W = 620;
const H = 260;
const M = { top: 26, right: 16, bottom: 38, left: 64 } as const;

/**
 * Mean fare by advance-purchase window.
 *
 * One measure across an ordered dimension, so one hue — colouring the bars by
 * window would be encoding rank as identity. Every bar is direct-labelled, which
 * also discharges the contrast relief rule on the light surface.
 */
export function AdvanceWindowChart({ cells }: { cells: readonly RouteCell[] }) {
  const [hover, setHover] = useState<number | null>(null);

  const data = useMemo(() => {
    const byWindow = new Map<number, number[]>();
    for (const c of cells) {
      const list = byWindow.get(c.advanceDays);
      if (list) list.push(c.price);
      else byWindow.set(c.advanceDays, [c.price]);
    }
    return [...byWindow.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([days, prices]) => ({
        days,
        mean: prices.reduce((s, p) => s + p, 0) / prices.length,
        n: prices.length,
      }));
  }, [cells]);

  if (data.length === 0) {
    return <p className="text-[13.5px] text-[var(--critical)]">No observed cells.</p>;
  }

  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const yMax = Math.max(...data.map((d) => d.mean)) * 1.16;
  const barW = Math.min(74, iw / data.length - 14);
  const X = (i: number) => M.left + (i + 0.5) * (iw / data.length);
  const Y = (v: number) => M.top + ih - (v / yMax) * ih;
  const gridFractions = [0, 0.25, 0.5, 0.75, 1];

  return (
    <div className="relative w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="block max-w-full"
        role="img"
        aria-label="Mean fare by advance-purchase window"
      >
        {gridFractions.map((f) => (
          <line
            key={f}
            x1={M.left}
            x2={M.left + iw}
            y1={M.top + ih - f * ih}
            y2={M.top + ih - f * ih}
            stroke="var(--grid)"
            strokeWidth={1}
          />
        ))}
        {gridFractions.map((f) => (
          <text
            key={`t${f}`}
            x={M.left - 9}
            y={M.top + ih - f * ih + 4}
            textAnchor="end"
            fill="var(--text-muted)"
            fontSize={11}
          >
            {inr(f * yMax)}
          </text>
        ))}

        {data.map((d, i) => (
          <g key={d.days}>
            <rect
              x={X(i) - barW / 2}
              y={Y(d.mean)}
              width={barW}
              height={M.top + ih - Y(d.mean)}
              rx={4}
              fill="var(--s1)"
              opacity={hover === null || hover === i ? 1 : 0.55}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            />
            <text
              x={X(i)}
              y={Y(d.mean) - 8}
              textAnchor="middle"
              fill="var(--text-primary)"
              fontSize={12}
              fontWeight={600}
            >
              {inr(d.mean)}
            </text>
            <text
              x={X(i)}
              y={H - 12}
              textAnchor="middle"
              fill="var(--text-muted)"
              fontSize={11.5}
            >
              T+{d.days}
            </text>
          </g>
        ))}
      </svg>

      {hover !== null && data[hover] ? (
        <p className="mt-1 text-[12.5px] text-[var(--text-secondary)]">
          <span className="font-semibold">T+{data[hover].days} days</span> · mean{" "}
          {inr(data[hover].mean)} across {data[hover].n} observed cells
        </p>
      ) : (
        <p className="mt-1 text-[12.5px] text-[var(--text-muted)]">
          Fares fall steeply with lead time; the T+1 premium is what makes airfare
          inflation volatile relative to the rest of the Transport sub-group.
        </p>
      )}
    </div>
  );
}
