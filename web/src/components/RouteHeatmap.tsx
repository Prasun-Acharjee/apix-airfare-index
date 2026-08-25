"use client";

import { useMemo, useState } from "react";
import { inr } from "@/lib/format";
import type { RouteCell } from "@/lib/types";

const RAMP = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6"] as const;

/**
 * Route × advance-window fare matrix, sequential single-hue.
 *
 * The ramp runs light→dark on the light surface and dark→light on the dark one,
 * so the label colour is chosen from the resolved fill's luminance rather than
 * from the value's position in the ramp — otherwise every high-value cell in
 * dark mode would print white text on a pale blue fill.
 */
export function RouteHeatmap({ cells }: { cells: readonly RouteCell[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const [luminance, setLuminance] = useState<readonly number[]>([]);

  const { routes, windows, index, lo, hi } = useMemo(() => {
    const r = [...new Set(cells.map((c) => c.route))].sort();
    const w = [...new Set(cells.map((c) => c.advanceDays))].sort((a, b) => a - b);
    const idx = new Map<string, RouteCell>();
    for (const c of cells) idx.set(`${c.route}|${c.advanceDays}`, c);
    const prices = cells.map((c) => c.price);
    return {
      routes: r,
      windows: w,
      index: idx,
      lo: prices.length ? Math.min(...prices) : 0,
      hi: prices.length ? Math.max(...prices) : 1,
    };
  }, [cells]);

  // Resolve the ramp's computed colours once mounted so ink can follow the fill.
  const measure = (node: SVGSVGElement | null) => {
    if (!node || luminance.length > 0) return;
    const style = getComputedStyle(node);
    setLuminance(
      RAMP.map((token) => relativeLuminance(style.getPropertyValue(token).trim())),
    );
  };

  if (cells.length === 0) {
    return <p className="text-[13.5px] text-[var(--critical)]">No observed cells.</p>;
  }

  const cw = 96;
  const ch = 34;
  const left = 112;
  const top = 26;
  const W = left + windows.length * cw + 16;
  const H = top + routes.length * ch + 10;
  const frac = (v: number) => (hi === lo ? 0.5 : (v - lo) / (hi - lo));
  const step = (v: number) => Math.min(RAMP.length - 1, Math.floor(frac(v) * RAMP.length));
  const ink = (v: number) => {
    const l = luminance[step(v)];
    if (l === undefined) return "var(--text-primary)";
    return betterInk(l);
  };

  return (
    <div className="w-full overflow-x-auto">
      <svg
        ref={measure}
        viewBox={`0 0 ${W} ${H}`}
        width={W}
        height={H}
        className="block max-w-full"
        role="img"
        aria-label="Observed fare by route and advance-purchase window"
      >
        {windows.map((w, j) => (
          <text
            key={w}
            x={left + j * cw + cw / 2}
            y={top - 9}
            textAnchor="middle"
            fill="var(--text-muted)"
            fontSize={11.5}
          >
            T+{w}
          </text>
        ))}
        {routes.map((r, i) => (
          <text
            key={r}
            x={left - 10}
            y={top + i * ch + ch / 2 + 4}
            textAnchor="end"
            fill="var(--text-secondary)"
            fontSize={12}
          >
            {r}
          </text>
        ))}
        {routes.map((r, i) =>
          windows.map((w, j) => {
            const cell = index.get(`${r}|${w}`);
            if (!cell) return null;
            const key = `${r}|${w}`;
            return (
              <g
                key={key}
                onMouseEnter={() => setHover(key)}
                onMouseLeave={() => setHover(null)}
              >
                <rect
                  x={left + j * cw + 1}
                  y={top + i * ch + 1}
                  width={cw - 2}
                  height={ch - 2}
                  rx={4}
                  fill={`var(${RAMP[step(cell.price)]})`}
                  stroke={hover === key ? "var(--text-primary)" : "transparent"}
                  strokeWidth={hover === key ? 1.5 : 0}
                />
                <text
                  x={left + j * cw + cw / 2}
                  y={top + i * ch + ch / 2 + 4}
                  textAnchor="middle"
                  fontSize={11.5}
                  fill={ink(cell.price)}
                >
                  {inr(cell.price)}
                </text>
              </g>
            );
          }),
        )}
      </svg>
      <p className="mt-1 text-[12.5px] text-[var(--text-muted)]">
        {hover
          ? `${hover.replace("|", " · T+")} — ${inr(index.get(hover)?.price ?? 0)} across ${
              index.get(hover)?.nQuotes ?? 0
            } quotes`
          : `${routes.length} routes × ${windows.length} windows, observed cells only (imputed cells excluded).`}
      </p>
    </div>
  );
}

/**
 * Pick whichever of white or black actually contrasts better against a fill,
 * rather than guessing a lightness cutoff. WCAG contrast is
 * (Ll + 0.05) / (Ld + 0.05), so white wins exactly when the fill's luminance is
 * below ~0.179 — computing it is both correct and self-explaining, and it keeps
 * working if the ramp is ever re-stepped.
 */
function betterInk(luminance: number): string {
  const againstWhite = 1.05 / (luminance + 0.05);
  const againstBlack = (luminance + 0.05) / 0.05;
  return againstWhite >= againstBlack ? "#ffffff" : "#0b0b0b";
}

function relativeLuminance(hex: string): number {
  const clean = hex.replace("#", "").trim();
  if (clean.length !== 6) return 1;
  const channel = (offset: number): number => {
    const v = parseInt(clean.slice(offset, offset + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
}
