"""Upper-level aggregation: cell prices -> the published APIx series.

Construction
------------
The index is a *chained, weighted geometric* (Young) index. For consecutive
collection days t-1 and t:

    R_t = exp( sum_c  w~_c * ln( p_{c,t} / p_{c,t-1} ) )
    I_t = I_{t-1} * R_t

where c runs over cells present in BOTH periods (after imputation), and w~_c is
the basket weight of cell c renormalised over that matched set.

Why chained rather than a fixed-base Laspeyres against the base period:
airline route and carrier coverage churns constantly - a carrier drops a pair,
an OTA stops quoting a fare family, a new window opens. A fixed-base index has
to decide what the base-period price of a cell that did not exist then was. A
chained index never asks that question; a cell contributes from its second
observation onward and stops contributing when it disappears, and neither event
moves the index by itself.

The cost of chaining is drift: with volatile, oscillating prices - which
airfares emphatically are - repeated chaining of a geometric index can wander
away from a direct comparison of the endpoints. That is why the series is
computed at daily frequency but the *published* monthly figure is a direct
month-over-month comparison of monthly cell averages, not a product of thirty
daily links. See `chained_series` vs `direct_comparison`.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Callable, Iterable, Optional

from ..config import Basket
from ..models import Cell, CellPrice, IndexPoint
from .imputation import Imputer, carry_forward


def _renormalise(weights: dict[Cell, float]) -> dict[Cell, float]:
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {c: w / total for c, w in weights.items()}


def period_link(
    prev: dict[Cell, CellPrice],
    curr: dict[Cell, CellPrice],
    basket: Basket,
    impute: bool = True,
) -> tuple[float, dict]:
    """One chain link. Returns (relative, diagnostics).

    Diagnostics carry the coverage and imputation shares that decide whether the
    point is publishable, so a caller never has to recompute them.
    """
    w_of: Callable[[Cell], float] = basket.cell_weight

    matched: dict[Cell, float] = {}
    for cell, cp in curr.items():
        p0 = prev.get(cell)
        if p0 is None or p0.price <= 0 or cp.price <= 0:
            continue
        if w_of(cell) <= 0:
            continue
        matched[cell] = math.log(cp.price / p0.price)

    weights = {c: w_of(c) for c in matched}
    imputed: dict[Cell, float] = {}

    if impute and matched:
        imputer = Imputer(matched, weights)
        # Cells we saw last period but not this one: impute their movement so
        # their weight stays in the index rather than being reallocated by
        # accident to whatever happened to respond today.
        for cell, p0 in prev.items():
            if cell in matched or cell in curr:
                continue
            if w_of(cell) <= 0:
                continue
            res = imputer.impute(cell)
            if res is not None:
                imputed[cell] = res.log_relative
                weights[cell] = w_of(cell)

    combined = {**matched, **imputed}
    if not combined:
        return 1.0, {
            "n_matched": 0, "n_imputed": 0, "coverage": 0.0,
            "imputation_share": 0.0, "quality": "fail",
            "notes": ["no cells matched across the period pair; index carried forward flat"],
        }

    wn = _renormalise({c: weights[c] for c in combined})
    log_rel = sum(wn[c] * combined[c] for c in combined)

    basket_total = sum(w_of(c) for c in basket.cells())
    observed_w = sum(w_of(c) for c in matched)
    imputed_w = sum(w_of(c) for c in imputed)
    coverage = (observed_w + imputed_w) / basket_total if basket_total > 0 else 0.0
    imp_share = imputed_w / (observed_w + imputed_w) if (observed_w + imputed_w) > 0 else 0.0

    qc = basket.qc
    notes: list[str] = []
    quality = "ok"
    if imp_share >= float(qc.get("max_imputation_share_fail", 0.60)):
        quality = "fail"
        notes.append(f"imputation share {imp_share:.1%} at or above fail threshold")
    elif imp_share >= float(qc.get("max_imputation_share_warn", 0.35)):
        quality = "warn"
        notes.append(f"imputation share {imp_share:.1%} at or above warn threshold")
    if coverage < 0.5:
        quality = "fail" if quality != "fail" else quality
        notes.append(f"basket coverage {coverage:.1%} below 50%")

    return math.exp(log_rel), {
        "n_matched": len(matched), "n_imputed": len(imputed),
        "coverage": coverage, "imputation_share": imp_share,
        "quality": quality, "notes": notes,
    }


def chained_series(
    by_day: dict[date, dict[Cell, CellPrice]],
    basket: Basket,
    impute: bool = True,
) -> list[IndexPoint]:
    """Daily chained index over the observed days, anchored at the base period."""
    if not by_day:
        return []
    days = sorted(by_day)
    points: list[IndexPoint] = []

    level = basket.base_value
    first = days[0]
    points.append(IndexPoint(
        on_date=first, value=level, frequency="daily",
        n_cells_matched=len(by_day[first]), n_cells_imputed=0,
        coverage=sum(basket.cell_weight(c) for c in by_day[first]),
        imputation_share=0.0, quality="ok",
        notes=["base period" if first == basket.base_period else "series start (anchored)"],
    ))

    # Working state carries imputed prices forward so a cell that vanishes for a
    # few days can rejoin the matched sample when it returns, instead of
    # re-entering as a brand new item.
    state: dict[Cell, CellPrice] = dict(by_day[first])

    for prev_day, day in zip(days, days[1:]):
        curr = by_day[day]
        rel, diag = period_link(state, curr, basket, impute=impute)
        level *= rel

        new_state: dict[Cell, CellPrice] = dict(curr)
        if impute:
            imputer_matched = {
                c: math.log(curr[c].price / state[c].price)
                for c in curr if c in state and state[c].price > 0 and curr[c].price > 0
            }
            if imputer_matched:
                imp = Imputer(imputer_matched, {c: basket.cell_weight(c) for c in imputer_matched})
                for cell, cp in state.items():
                    if cell in new_state:
                        continue
                    res = imp.impute(cell)
                    if res is not None:
                        new_state[cell] = CellPrice(
                            cell=cell, on_date=day,
                            price=carry_forward(cp.price, res.log_relative),
                            n_quotes=0, imputed=True, imputation_source=res.method,
                        )
        state = new_state

        points.append(IndexPoint(
            on_date=day, value=level, frequency="daily",
            n_cells_matched=diag["n_matched"], n_cells_imputed=diag["n_imputed"],
            coverage=diag["coverage"], imputation_share=diag["imputation_share"],
            quality=diag["quality"], notes=list(diag["notes"]),
        ))
    return points


def direct_comparison(
    prev: dict[Cell, CellPrice],
    curr: dict[Cell, CellPrice],
    basket: Basket,
) -> tuple[float, dict]:
    """Endpoint-to-endpoint relative with no intermediate chaining.

    Used for the published monthly figure to avoid chain drift.
    """
    return period_link(prev, curr, basket, impute=True)


def period_average_prices(
    by_day: dict[date, dict[Cell, CellPrice]],
    key: Callable[[date], str],
) -> dict[str, dict[Cell, CellPrice]]:
    """Collapse daily cell prices into per-period (week/month) cell averages.

    Geometric mean again, for consistency with the elementary aggregate: the
    monthly price of a cell is the geometric mean of its daily prices.
    """
    buckets: dict[str, dict[Cell, list[float]]] = defaultdict(lambda: defaultdict(list))
    dates: dict[str, date] = {}
    for day, cells in by_day.items():
        k = key(day)
        dates.setdefault(k, day)
        dates[k] = min(dates[k], day)
        for cell, cp in cells.items():
            if cp.price > 0:
                buckets[k][cell].append(cp.price)

    out: dict[str, dict[Cell, CellPrice]] = {}
    for k, cellmap in buckets.items():
        out[k] = {
            cell: CellPrice(
                cell=cell, on_date=dates[k],
                price=math.exp(sum(math.log(p) for p in ps) / len(ps)),
                n_quotes=len(ps),
            )
            for cell, ps in cellmap.items()
        }
    return out


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def week_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]:04d}-W{iso[1]:02d}"


def lower_frequency_series(
    by_day: dict[date, dict[Cell, CellPrice]],
    basket: Basket,
    frequency: str,
) -> list[IndexPoint]:
    """Weekly or monthly series built from direct period-to-period comparisons."""
    key = month_key if frequency == "monthly" else week_key
    periods = period_average_prices(by_day, key)
    if not periods:
        return []
    ordered = sorted(periods, key=lambda k: min(cp.on_date for cp in periods[k].values()))
    points: list[IndexPoint] = []
    level = basket.base_value
    first = ordered[0]
    points.append(IndexPoint(
        on_date=min(cp.on_date for cp in periods[first].values()),
        value=level, frequency=frequency,
        n_cells_matched=len(periods[first]), n_cells_imputed=0,
        coverage=sum(basket.cell_weight(c) for c in periods[first]),
        imputation_share=0.0, quality="ok", notes=["series start (anchored)"],
    ))
    for a, b in zip(ordered, ordered[1:]):
        rel, diag = direct_comparison(periods[a], periods[b], basket)
        level *= rel
        points.append(IndexPoint(
            on_date=min(cp.on_date for cp in periods[b].values()),
            value=level, frequency=frequency,
            n_cells_matched=diag["n_matched"], n_cells_imputed=diag["n_imputed"],
            coverage=diag["coverage"], imputation_share=diag["imputation_share"],
            quality=diag["quality"], notes=list(diag["notes"]),
        ))
    return points
