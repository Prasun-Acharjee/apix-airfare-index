"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { ALL_ROUTES } from "@/lib/types";

/**
 * Chooses which city pair the index chart shows.
 *
 * "All routes" is the headline series — the basket weighted by passenger share.
 * Picking a pair swaps in that pair's own index, which is the same chained
 * calculation over a one-route basket, anchored at the same base value. The two
 * are read the same way, but the headline is NOT the average of the route
 * series: each route renormalises within itself.
 *
 * A <select> rather than chips: fifteen pairs is too many to sit in a row
 * without wrapping into something you have to scan rather than read.
 */
export function RoutePicker({
  active,
  routes,
}: {
  active: string;
  routes: readonly string[];
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [pending, startTransition] = useTransition();

  const select = (route: string) => {
    const next = new URLSearchParams(params.toString());
    if (route === ALL_ROUTES) next.delete("route");
    else next.set("route", route);
    startTransition(() => router.push(`/?${next.toString()}`, { scroll: false }));
  };

  return (
    <label className="flex items-center gap-2 text-[13px] text-[var(--text-secondary)]">
      <span className="shrink-0">Route</span>
      <select
        value={active}
        disabled={pending}
        onChange={(e) => select(e.target.value)}
        aria-label="City pair shown in the index chart"
        className="cursor-pointer rounded-full border border-[var(--border)] bg-[var(--surface-0)] px-3 py-1 text-[13px] text-[var(--text-primary)] transition-opacity disabled:opacity-60"
      >
        <option value={ALL_ROUTES}>All routes (weighted)</option>
        {routes.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </select>
    </label>
  );
}
