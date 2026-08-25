"""Elementary aggregation: many quotes in a cell -> one price for that cell/day."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Iterable, Sequence

from ..models import Cell, CellPrice, NormalisedQuote


def geometric_mean(values: Sequence[float]) -> float:
    """Geometric mean via logs. Guards against overflow and non-positive input."""
    vals = [v for v in values if v is not None and v > 0]
    if not vals:
        raise ValueError("geometric_mean requires at least one positive value")
    return math.exp(sum(math.log(v) for v in vals) / len(vals))


def elementary_prices(quotes: Iterable[NormalisedQuote]) -> dict[date, dict[Cell, CellPrice]]:
    """Collapse quotes to one price per (cell, day).

    The geometric mean is used rather than the arithmetic mean for the standard
    reason it is used in elementary aggregates everywhere: airfare distributions
    within a cell are strongly right-skewed (a handful of last-seat fares many
    multiples of the modal fare). An arithmetic mean lets one such quote drag the
    cell, and the resulting index would overstate inflation whenever fare
    dispersion widens, even with no change in the fare a typical passenger pays.
    The geometric mean is also the form that makes the index transitive in the
    chained construction used in `aggregate.py`.
    """
    buckets: dict[tuple[date, Cell], list[float]] = defaultdict(list)
    for q in quotes:
        buckets[(q.collected_on, q.cell)].append(q.price_inr)

    out: dict[date, dict[Cell, CellPrice]] = defaultdict(dict)
    for (on_date, cell), prices in buckets.items():
        out[on_date][cell] = CellPrice(
            cell=cell,
            on_date=on_date,
            price=geometric_mean(prices),
            n_quotes=len(prices),
        )
    return dict(out)
