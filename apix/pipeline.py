"""End-to-end: raw quotes -> normalised -> QC -> cell prices -> index -> DB."""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional

from .config import Basket, load_basket
from .db import connect, load_cell_prices, upsert_cell_prices, upsert_index
from .index.aggregate import chained_series, lower_frequency_series
from .index.elementary import elementary_prices
from .models import RawQuote
from .normalize.fares import normalise_all
from .normalize.qc import run_qc


def scope_to_dataset(basket: Basket, observed_sources: tuple[str, ...]) -> Basket:
    """Decide which sources this basket is weighted over for this dataset.

    Three cases, in order:

    1. The config names a scope (basket.yaml `sources.active`) and the dataset
       contains at least one of those sources. The recorded decision stands:
       narrowing the basket is a statement about what the index measures, and a
       source being quiet today must not quietly widen or narrow it. Sources
       outside the scope carry zero weight and drop out of the index.

    2. The config names a scope and the dataset contains NONE of it. This is a
       replay of a different world - a synthetic run whose ids are `sim_*`, or a
       backfill from an archive predating the scope. Weighting over a scope that
       matches nothing would produce an index of zero cells, so weight over what
       is actually in hand instead.

    3. No scope configured: weight over the sources present in the dataset, so a
       replay matches the data rather than today's compliance posture.
    """
    if not observed_sources:
        return basket
    if basket.active_sources is None:
        return basket.with_sources(observed_sources)
    if set(basket.active_sources) & set(observed_sources):
        return basket
    return basket.with_sources(observed_sources)


def build_index(raws: Iterable[RawQuote], basket: Optional[Basket] = None,
                price_concept: str = "all_in") -> dict:
    basket = basket or load_basket()
    normalised = list(normalise_all(raws, price_concept))
    observed_sources = tuple(sorted({q.source_id for q in normalised}))
    basket = scope_to_dataset(basket, observed_sources)
    qc = run_qc(normalised, basket.qc)
    by_day = elementary_prices(qc.kept)
    return {
        "qc": qc.summary(),
        "cell_prices": by_day,
        "daily": chained_series(by_day, basket),
        "weekly": lower_frequency_series(by_day, basket, "weekly"),
        "monthly": lower_frequency_series(by_day, basket, "monthly"),
    }


def run_and_store(raws: Iterable[RawQuote], db_path: str = "data/apix.db",
                  basket: Optional[Basket] = None) -> dict:
    result = build_index(raws, basket)
    with connect(db_path) as conn:
        upsert_cell_prices(conn, result["cell_prices"])
        for freq in ("daily", "weekly", "monthly"):
            upsert_index(conn, result[freq])
    return {
        "qc": result["qc"],
        "points": {f: len(result[f]) for f in ("daily", "weekly", "monthly")},
        "latest": result["daily"][-1] if result["daily"] else None,
    }
