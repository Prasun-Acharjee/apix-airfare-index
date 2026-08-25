"use client";

import { useMemo, useRef, useState } from "react";
import { dayNumber, num, pct, shortDay } from "@/lib/format";
import type { IndexPoint } from "@/lib/types";

const W = 760;
const H = 300;
const M = { top: 14, right: 20, bottom: 30, left: 58 } as const;
const IW = W - M.left - M.right;
const IH = H - M.top - M.bottom;

interface Hover {
  readonly point: IndexPoint;
  readonly cx: number;
  readonly cy: number;
}

/**
 * The index level over time. One series, so no legend — the card title names it.
 * A crosshair plus tooltip is the default interaction for a line chart; the
 * tooltip carries coverage and imputation share because a level without its
 * provenance invites over-reading.
 */
export function IndexChart({ series }: { series: readonly IndexPoint[] }) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);

  const geom = useMemo(() => {
    if (series.length === 0) return null;
    const xs = series.map((p) => dayNumber(p.onDate));
    const ys = series.map((p) => p.value);
    const x0 = Math.min(...xs);
    const x1 = Math.max(...xs);
    let y0 = Math.min(...ys);
    let y1 = Math.max(...ys);
    const pad = (y1 - y0) * 0.12 || 2;
    y0 -= pad;
    y1 += pad;

    const X = (v: number) => M.left + (x1 === x0 ? IW / 2 : ((v - x0) / (x1 - x0)) * IW);
    const Y = (v: number) => M.top + IH - ((v - y0) / (y1 - y0)) * IH;

    const path = series
      .map((p, i) => `${i === 0 ? "M" : "L"}${X(xs[i] ?? 0).toFixed(1)} ${Y(p.value).toFixed(1)}`)
      .join(" ");
    const area = `${path} L${X(x1).toFixed(1)} ${M.top + IH} L${X(x0).toFixed(1)} ${M.top + IH} Z`;
    const yTicks = Array.from({ length: 5 }, (_, i) => y0 + ((y1 - y0) * i) / 4);
    const tickCount = Math.min(6, series.length);
    const xTickIdx = Array.from({ length: tickCount }, (_, i) =>
      Math.round((i * (series.length - 1)) / Math.max(tickCount - 1, 1)),
    );
    return { xs, X, Y, path, area, yTicks, xTickIdx };
  }, [series]);

  if (!geom) {
    return <p className="text-[13.5px] text-[var(--critical)]">No publishable points.</p>;
  }

  const onMove = (e: React.MouseEvent<SVGRectElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const box = svg.getBoundingClientRect();
    const sx = (e.clientX - box.left) * (W / box.width);
    let best = 0;
    let bestDist = Infinity;
    geom.xs.forEach((x, i) => {
      const d = Math.abs(geom.X(x) - sx);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    });
    const point = series[best];
    const x = geom.xs[best];
    if (!point || x === undefined) return;
    setHover({ point, cx: geom.X(x), cy: geom.Y(point.value) });
  };

  return (
    <div className="relative w-full overflow-x-auto">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="block max-w-full"
        role="img"
        aria-label="APIx index level over time"
      >
        <defs>
          <linearGradient id="apix-area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--s1)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="var(--s1)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {geom.yTicks.map((v) => (
          <line
            key={`g${v}`}
            x1={M.left}
            x2={M.left + IW}
            y1={geom.Y(v)}
            y2={geom.Y(v)}
            stroke="var(--grid)"
            strokeWidth={1}
          />
        ))}
        {geom.yTicks.map((v) => (
          <text
            key={`y${v}`}
            x={M.left - 9}
            y={geom.Y(v) + 4}
            textAnchor="end"
            fill="var(--text-muted)"
            fontSize={11}
          >
            {num(v)}
          </text>
        ))}
        {geom.xTickIdx.map((i) => {
          const p = series[i];
          const x = geom.xs[i];
          if (!p || x === undefined) return null;
          return (
            <text
              key={`x${i}`}
              x={geom.X(x)}
              y={H - 10}
              textAnchor="middle"
              fill="var(--text-muted)"
              fontSize={11}
            >
              {shortDay(p.onDate)}
            </text>
          );
        })}

        <path d={geom.area} fill="url(#apix-area)" />
        <path
          d={geom.path}
          fill="none"
          stroke="var(--s1)"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {hover ? (
          <>
            <line
              x1={hover.cx}
              x2={hover.cx}
              y1={M.top}
              y2={M.top + IH}
              stroke="var(--border)"
              strokeWidth={1}
            />
            <circle
              cx={hover.cx}
              cy={hover.cy}
              r={5}
              fill="var(--s1)"
              stroke="var(--surface-1)"
              strokeWidth={2}
            />
          </>
        ) : null}

        <rect
          x={M.left}
          y={M.top}
          width={IW}
          height={IH}
          fill="transparent"
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
        />
      </svg>

      {hover ? (
        <div
          className="pointer-events-none absolute z-10 rounded-[7px] border border-[var(--border)] bg-[var(--surface-1)] px-2.5 py-2 text-[12.5px] shadow-lg"
          style={{
            left: `min(${(hover.cx / W) * 100}%, calc(100% - 190px))`,
            top: 0,
          }}
        >
          <div className="mb-1 font-semibold">{hover.point.onDate}</div>
          <Row label="Index" value={num(hover.point.value)} strong />
          <Row label="Coverage" value={pct(hover.point.coverage)} />
          <Row label="Imputed" value={pct(hover.point.imputationShare)} />
          <Row label="Cells" value={String(hover.point.nCellsMatched)} />
        </div>
      ) : null}
    </div>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="tabular flex justify-between gap-3.5">
      <span className="text-[var(--text-secondary)]">{label}</span>
      <span className={strong ? "font-semibold" : ""}>{value}</span>
    </div>
  );
}
