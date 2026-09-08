"""Per-route index series: same maths, one route's basket.

The site could not answer "which route is this?" because the headline index has
no route — it is every city pair weighted by passenger share. These build the
per-route series that lets it answer with a route instead of a footnote.
"""
from __future__ import annotations

from datetime import date

import pytest

from apix.collect.simulator import generate
from apix.config import load_basket
from apix.models import ALL_ROUTES
from apix.pipeline import build_index


@pytest.fixture(scope="module")
def result() -> dict:
    basket = load_basket()
    raws = list(generate(basket, start=date(2026, 4, 1), days=8, fuel_shock_on=None))
    return build_index(raws, basket)


def test_the_headline_series_is_tagged_as_all_routes(result):
    # Otherwise a route filter would silently return the headline number.
    assert {p.route for p in result["daily"]} == {ALL_ROUTES}


def test_every_basket_route_gets_its_own_series(result):
    assert set(result["by_route"]) == set(load_basket().route_weights)


def test_route_points_carry_their_route(result):
    for route, freqs in result["by_route"].items():
        for points in freqs.values():
            assert {p.route for p in points} == {route}


def test_a_route_series_starts_at_the_same_base_value(result):
    """Routes are anchored alike so two routes can be read on one axis."""
    base = load_basket().base_value
    for freqs in result["by_route"].values():
        assert freqs["daily"][0].value == pytest.approx(base)
    assert result["daily"][0].value == pytest.approx(base)


def test_coverage_is_measured_against_the_route_not_the_nation(result):
    """The bug this guards: DEL-SXR carries 2.6% of national traffic, so a
    route index weighted against the whole basket would report 2.6% coverage on
    a day every one of its cells was observed."""
    for route, freqs in result["by_route"].items():
        last = freqs["daily"][-1]
        assert last.coverage > 0.5, f"{route} coverage {last.coverage:.1%} looks nation-weighted"
        assert last.coverage <= 1.0 + 1e-9


def test_the_headline_is_not_the_mean_of_the_routes(result):
    """A real risk of misreading, so it is pinned. Each route renormalises within
    itself; the headline weights routes by passenger share. They differ."""
    import statistics
    last_by_route = [f["daily"][-1].value for f in result["by_route"].values()]
    assert result["daily"][-1].value != pytest.approx(statistics.fmean(last_by_route), rel=1e-9)


def test_a_route_never_seen_twice_is_skipped_not_published_flat():
    """One collection day gives no link. Emitting the base value would read as
    'no price change' when it means 'no data'."""
    basket = load_basket()
    raws = list(generate(basket, start=date(2026, 4, 1), days=4, fuel_shock_on=None))
    keep = sorted(basket.route_weights)[0]
    thin = [q for q in raws if q.route == keep or q.collected_at.date() == date(2026, 4, 1)]
    got = build_index(thin, basket)["by_route"]
    assert keep in got
    for route, freqs in got.items():
        assert len(freqs["daily"]) >= 2, f"{route} published a series with no link"


def test_a_route_outside_the_basket_is_refused():
    with pytest.raises(KeyError):
        load_basket().for_route("XXX-YYY")


def test_restricting_to_a_route_keeps_the_weights_normalised():
    basket = load_basket()
    for route in list(basket.route_weights)[:4]:
        rb = basket.for_route(route)
        cells = list(rb.cells())
        assert {c.route for c in cells} == {route}
        assert sum(rb.cell_weight(c) for c in cells) == pytest.approx(1.0)


# --- readers must not blend the route series into the headline one -----------

def test_the_local_api_loader_returns_one_series_not_sixteen():
    """Every reader of index_point has to filter on route now. This one is the
    easiest to forget: it used to be `SELECT * WHERE frequency=?`, which after
    the route column returns the headline series interleaved with all fifteen
    route series — one index apparently taking several values on the same day.
    """
    import os
    import tempfile
    from apix.db import connect, load_index, upsert_index
    from apix.models import ALL_ROUTES

    basket = load_basket()
    raws = list(generate(basket, start=date(2026, 4, 1), days=5, fuel_shock_on=None))
    res = build_index(raws, basket)

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.db")
        with connect(path) as conn:
            upsert_index(conn, res["daily"])
            for freqs in res["by_route"].values():
                upsert_index(conn, freqs["daily"])

            headline = load_index(conn, "daily")
            assert {r["route"] for r in headline} == {ALL_ROUTES}
            assert len({r["on_date"] for r in headline}) == len(headline), \
                "one point per day, or the series is blended"

            pair = sorted(basket.route_weights)[0]
            one = load_index(conn, "daily", route=pair)
            assert one and {r["route"] for r in one} == {pair}
            assert [r["value"] for r in one] != [r["value"] for r in headline]
