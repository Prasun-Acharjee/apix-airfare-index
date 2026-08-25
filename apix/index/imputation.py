"""Imputation for cells that were not observed on a given day.

A cell can go missing for reasons that carry no price signal at all: the site
declined our request, the collector hit an error, the route was not served that
day. If those cells simply drop out of the matched sample, the index silently
reweights toward whatever remains, and non-response starts to look like
inflation. Standard practice in official price statistics is to impute the
missing cell's movement from the movement of the cells around it, then report
how much of the index rests on imputation.

Hierarchy, most specific first:
  1. class-mean  - the cell's own stratum (route x advance window x cabin)
  2. route-mean  - all matched cells on the same route
  3. all-items   - the overall matched movement

A cell with no previous price cannot be imputed; it enters the index only when
it has been observed on two consecutive periods, which is what keeps the
chained relative well-defined.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from ..models import Cell


@dataclass
class ImputationResult:
    log_relative: float
    method: str


class Imputer:
    """Builds donor movements from the matched cells of a single period pair."""

    def __init__(self, matched: dict[Cell, float], weights: dict[Cell, float]):
        """`matched` maps cell -> ln(p_t / p_{t-1}) for cells seen in both periods."""
        self._by_stratum: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._by_route: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self._all: list[tuple[float, float]] = []
        for cell, lr in matched.items():
            w = max(weights.get(cell, 0.0), 0.0)
            if w <= 0:
                continue
            self._by_stratum[cell.stratum].append((lr, w))
            self._by_route[cell.route].append((lr, w))
            self._all.append((lr, w))

    @staticmethod
    def _wmean(pairs: list[tuple[float, float]]) -> Optional[float]:
        tw = sum(w for _, w in pairs)
        if tw <= 0:
            return None
        return sum(lr * w for lr, w in pairs) / tw

    def impute(self, cell: Cell) -> Optional[ImputationResult]:
        v = self._wmean(self._by_stratum.get(cell.stratum, []))
        if v is not None:
            return ImputationResult(v, "class_mean")
        v = self._wmean(self._by_route.get(cell.route, []))
        if v is not None:
            return ImputationResult(v, "route_mean")
        v = self._wmean(self._all)
        if v is not None:
            return ImputationResult(v, "all_items")
        return None


def carry_forward(previous_price: float, log_relative: float) -> float:
    """Imputed price for a missing cell, so it can be matched again next period."""
    return previous_price * math.exp(log_relative)
