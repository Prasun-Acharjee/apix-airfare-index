/** Presentation helpers, shared by server and client components. */

const INR = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const NUM = new Intl.NumberFormat("en-IN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export const inr = (n: number): string => `₹${INR.format(Math.round(n))}`;
export const num = (n: number): string => NUM.format(n);
export const pct = (fraction: number, dp = 1): string => `${(fraction * 100).toFixed(dp)}%`;
export const signedPct = (p: number, dp = 2): string => `${p >= 0 ? "+" : ""}${p.toFixed(dp)}%`;

/**
 * Format an ISO `YYYY-MM-DD` without constructing a Date.
 *
 * `new Date("2026-04-01")` parses as UTC midnight and then renders in the
 * viewer's local zone, which shows 31 March to anyone west of UTC. Every date
 * in this app is a calendar date, not an instant, so it is formatted as text.
 */
export function formatDay(iso: string): string {
  const [y, m, d] = iso.split("-");
  if (!y || !m || !d) return iso;
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const month = months[Number(m) - 1] ?? m;
  return `${Number(d)} ${month} ${y}`;
}

export const shortDay = (iso: string): string => iso.slice(5);

/** Days since the epoch — a monotone x-axis for calendar dates, no Date object. */
export function dayNumber(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  if (y === undefined || m === undefined || d === undefined) return 0;
  return Math.floor(Date.UTC(y, m - 1, d) / 86_400_000);
}

export const qualityLabel: Record<string, string> = {
  ok: "ok",
  warn: "high imputation",
  fail: "not publishable",
};
