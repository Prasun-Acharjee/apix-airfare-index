"""Builders for constructing index inputs with a KNOWN true price movement."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from apix.config import Basket, load_basket
from apix.models import Cell, CellPrice


def tiny_basket() -> Basket:
    """A 2 route x 2 carrier x 2 window basket with hand-checkable weights."""
    b = load_basket()
    return replace(
        b,
        route_weights={"DEL-BOM": 0.6, "DEL-BLR": 0.4},
        carrier_weights={"AI": 0.5, "6E": 0.5},
        window_weights={7: 0.5, 30: 0.5},
        cabins=("ECONOMY",),
    )


def all_cells(basket: Basket, source_ids=("air_india",)) -> list[Cell]:
    return [
        Cell(route=r, carrier=c, advance_days=d, source_id=s, cabin="ECONOMY")
        for r in basket.route_weights
        for c in basket.carrier_weights
        for d in basket.window_weights
        for s in source_ids
    ]


def flat_weight(basket: Basket, cells: list[Cell]):
    """Override cell_weight so tiny_basket weights apply regardless of sources.yaml."""
    def w(cell: Cell, source_ids=None) -> float:
        if cell not in cells:
            return 0.0
        return (
            basket.route_weights.get(cell.route, 0.0)
            * basket.carrier_weights.get(cell.carrier, 0.0)
            * basket.window_weights.get(cell.advance_days, 0.0)
        )
    return w


def make_day(cells: list[Cell], prices: dict[Cell, float], on: date) -> dict[Cell, CellPrice]:
    return {
        c: CellPrice(cell=c, on_date=on, price=prices[c], n_quotes=3)
        for c in cells if c in prices
    }


def uniform_prices(cells: list[Cell], value: float) -> dict[Cell, float]:
    return {c: value for c in cells}


def days_from(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]
