"""Quality control. Rejections are recorded, never silently dropped."""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ..models import Cell, NormalisedQuote


@dataclass
class QCReport:
    kept: list[NormalisedQuote] = field(default_factory=list)
    rejected: list[tuple[NormalisedQuote, str]] = field(default_factory=list)

    @property
    def rejection_rate(self) -> float:
        n = len(self.kept) + len(self.rejected)
        return len(self.rejected) / n if n else 0.0

    def summary(self) -> dict:
        reasons: dict[str, int] = defaultdict(int)
        for _, why in self.rejected:
            reasons[why] += 1
        return {
            "kept": len(self.kept),
            "rejected": len(self.rejected),
            "rejection_rate": round(self.rejection_rate, 4),
            "reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        }


def modified_zscores(values: Sequence[float]) -> list[float]:
    """Median-absolute-deviation z-scores. Robust where mean/sd are not.

    Applied to LOG fares, because fare dispersion is multiplicative: a 2x fare
    on a cheap route and a 2x fare on an expensive one are the same anomaly.
    """
    if len(values) < 3:
        return [0.0] * len(values)
    logs = [math.log(v) for v in values]
    med = statistics.median(logs)
    devs = [abs(x - med) for x in logs]
    mad = statistics.median(devs)
    if mad == 0:
        return [0.0] * len(values)
    return [0.6745 * (x - med) / mad for x in logs]


def run_qc(quotes: Iterable[NormalisedQuote], qc_config: dict) -> QCReport:
    rep = QCReport()
    lo = float(qc_config.get("min_fare_inr", 800))
    hi = float(qc_config.get("max_fare_inr", 120000))
    thresh = float(qc_config.get("mad_outlier_threshold", 4.0))

    staged: list[NormalisedQuote] = []
    for q in quotes:
        if not math.isfinite(q.price_inr) or q.price_inr <= 0:
            rep.rejected.append((q, "non_positive_or_nan_price")); continue
        if q.price_inr < lo:
            rep.rejected.append((q, "below_min_fare")); continue
        if q.price_inr > hi:
            rep.rejected.append((q, "above_max_fare")); continue
        if q.departure_date < q.collected_on:
            rep.rejected.append((q, "departure_before_collection")); continue
        if q.total_inr + 1e-6 < q.base_inr:
            rep.rejected.append((q, "total_below_base")); continue
        staged.append(q)

    # Within-cell outlier detection, per collection day.
    by_cell: dict[tuple, list[NormalisedQuote]] = defaultdict(list)
    for q in staged:
        by_cell[(q.collected_on, q.cell)].append(q)

    for group in by_cell.values():
        zs = modified_zscores([q.price_inr for q in group])
        for q, z in zip(group, zs):
            if abs(z) > thresh:
                q.qc_flags.append(f"mad_outlier(z={z:.1f})")
                rep.rejected.append((q, "within_cell_outlier"))
            else:
                rep.kept.append(q)
    return rep


def day_over_day_flags(
    today: dict[Cell, float], yesterday: dict[Cell, float], qc_config: dict
) -> dict[Cell, str]:
    """Flag implausible one-day moves for review. Flagged, not deleted -
    airfares genuinely do move enormously, and deleting the large true moves
    would bias the index toward stability."""
    cap = float(qc_config.get("max_log_move_per_day", 1.10))
    out: dict[Cell, str] = {}
    for cell, p in today.items():
        p0 = yesterday.get(cell)
        if not p0 or p0 <= 0 or p <= 0:
            continue
        move = abs(math.log(p / p0))
        if move > cap:
            out[cell] = f"day_move_{math.exp(move):.2f}x_exceeds_cap"
    return out
