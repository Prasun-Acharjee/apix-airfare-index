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


def build_index(raws: Iterable[RawQuote], basket: Optional[Basket] = None,
                price_concept: str = "all_in") -> dict:
    basket = basket or load_basket()
    normalised = list(normalise_all(raws, price_concept))
    # Weight the basket over the sources actually present in this dataset.
    observed_sources = tuple(sorted({q.source_id for q in normalised}))
    if observed_sources and basket.active_sources is None:
        basket = basket.with_sources(observed_sources)
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
