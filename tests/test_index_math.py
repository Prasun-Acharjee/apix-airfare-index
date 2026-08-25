"""Ground-truth tests: construct a price path by hand, require the engine to recover it."""
from __future__ import annotations

import math
from dataclasses import replace
from datetime import date

import pytest

from apix.index.aggregate import (
    chained_series, direct_comparison, lower_frequency_series, period_link,
)
from apix.index.elementary import geometric_mean
from tests.helpers import all_cells, days_from, flat_weight, make_day, tiny_basket, uniform_prices

D0 = date(2026, 4, 1)


@pytest.fixture
def setup(monkeypatch):
    b = tiny_basket()
    cells = all_cells(b)
    monkeypatch.setattr(type(b), "cell_weight", lambda self, cell, source_ids=None: flat_weight(b, cells)(cell))
    monkeypatch.setattr(type(b), "cells", lambda self, source_ids=None: iter(cells))
    return b, cells


def test_weights_sum_to_one(setup):
    b, cells = setup
    assert sum(b.cell_weight(c) for c in cells) == pytest.approx(1.0)


def test_uniform_inflation_is_recovered_exactly(setup):
    """Every cell up 5% -> index up exactly 5%, whatever the weights are."""
    b, cells = setup
    d = days_from(D0, 2)
    by_day = {
        d[0]: make_day(cells, uniform_prices(cells, 5000.0), d[0]),
        d[1]: make_day(cells, uniform_prices(cells, 5250.0), d[1]),
    }
    pts = chained_series(by_day, b)
    assert pts[0].value == pytest.approx(100.0)
    assert pts[1].value == pytest.approx(105.0)
    assert pts[1].imputation_share == 0.0
    assert pts[1].coverage == pytest.approx(1.0)


def test_weighted_geometric_mean_matches_hand_calculation(setup):
    """One route up 20%, the other flat. Index must be exp(0.6*ln1.2)."""
    b, cells = setup
    d = days_from(D0, 2)
    p0 = uniform_prices(cells, 5000.0)
    p1 = {c: (6000.0 if c.route == "DEL-BOM" else 5000.0) for c in cells}
    by_day = {d[0]: make_day(cells, p0, d[0]), d[1]: make_day(cells, p1, d[1])}
    expected = 100.0 * math.exp(0.6 * math.log(1.2))
    assert chained_series(by_day, b)[1].value == pytest.approx(expected)


def test_cell_entry_does_not_move_the_index(setup):
    """A cell appearing for the first time contributes no movement."""
    b, cells = setup
    d = days_from(D0, 2)
    subset = cells[:-1]
    p0 = uniform_prices(subset, 5000.0)
    p1 = {c: 5500.0 for c in cells}          # newcomer priced far off the others
    p1[cells[-1]] = 90000.0
    by_day = {d[0]: make_day(subset, p0, d[0]), d[1]: make_day(cells, p1, d[1])}
    pts = chained_series(by_day, b)
    assert pts[1].value == pytest.approx(110.0), "new cell leaked into the movement"


def test_cell_exit_is_imputed_not_dropped(setup):
    """A cell vanishing must not move the index, and must be flagged as imputed."""
    b, cells = setup
    d = days_from(D0, 2)
    survivors = [c for c in cells if c != cells[0]]
    by_day = {
        d[0]: make_day(cells, uniform_prices(cells, 5000.0), d[0]),
        d[1]: make_day(survivors, uniform_prices(survivors, 5500.0), d[1]),
    }
    pts = chained_series(by_day, b)
    assert pts[1].value == pytest.approx(110.0)
    assert pts[1].n_cells_imputed == 1
    assert 0.0 < pts[1].imputation_share < 0.2


def test_imputation_uses_own_stratum_not_global_mean(setup):
    """The missing cell takes its own route/window movement, not the all-items one."""
    b, cells = setup
    d = days_from(D0, 2)
    # DEL-BOM cells +30%, DEL-BLR cells flat. Drop one DEL-BOM cell.
    dropped = next(c for c in cells if c.route == "DEL-BOM")
    present = [c for c in cells if c != dropped]
    p0 = uniform_prices(cells, 1000.0)
    p1 = {c: (1300.0 if c.route == "DEL-BOM" else 1000.0) for c in present}
    by_day = {d[0]: make_day(cells, p0, d[0]), d[1]: make_day(present, p1, d[1])}
    pts = chained_series(by_day, b)
    # If imputation were correct, the dropped cell gets +30% and the index is
    # identical to the full-coverage case: exp(0.6*ln 1.3).
    expected = 100.0 * math.exp(0.6 * math.log(1.3))
    assert pts[1].value == pytest.approx(expected), "imputation donor was not the cell's own stratum"


def test_chaining_is_drift_free_under_constant_coverage(setup):
    """With a stable matched set, chained daily links == direct endpoint comparison.

    This is the transitivity property that justifies publishing a chained series
    at all. If it fails, the daily index is not comparable to the monthly one.
    """
    b, cells = setup
    d = days_from(D0, 10)
    # A deliberately oscillating path - the case that breaks naive chaining.
    by_day = {}
    for i, day in enumerate(d):
        prices = {}
        for j, c in enumerate(cells):
            wobble = 1.0 + 0.18 * math.sin(i * 1.1 + j)
            trend = 1.004 ** i
            prices[c] = 4000.0 * wobble * trend
        by_day[day] = make_day(cells, prices, day)
    pts = chained_series(by_day, b)
    rel_direct, _ = direct_comparison(by_day[d[0]], by_day[d[-1]], b)
    assert pts[-1].value == pytest.approx(100.0 * rel_direct, rel=1e-9)


def test_total_non_response_carries_index_flat_and_fails_quality(setup):
    b, cells = setup
    d = days_from(D0, 2)
    by_day = {d[0]: make_day(cells, uniform_prices(cells, 5000.0), d[0]), d[1]: {}}
    pts = chained_series(by_day, b)
    assert pts[1].value == pytest.approx(100.0)
    assert pts[1].quality == "fail"


def test_geometric_mean_resists_a_last_seat_outlier():
    """The reason the elementary aggregate is geometric, stated as a test."""
    typical = [4800.0, 5000.0, 5200.0, 4900.0]
    with_outlier = typical + [48000.0]
    arithmetic = sum(with_outlier) / len(with_outlier)
    geo = geometric_mean(with_outlier)
    assert arithmetic > 13000, "sanity: the arithmetic mean is dragged badly"
    assert geo < 8000, "geometric mean should stay near the modal fare"


def test_monthly_series_uses_direct_comparison(setup):
    b, cells = setup
    d = days_from(date(2026, 4, 25), 12)   # spans April -> May
    by_day = {}
    for i, day in enumerate(d):
        mult = 1.0 if day.month == 4 else 1.10
        by_day[day] = make_day(cells, uniform_prices(cells, 5000.0 * mult), day)
    pts = lower_frequency_series(by_day, b, "monthly")
    assert len(pts) == 2
    assert pts[1].value == pytest.approx(110.0)
