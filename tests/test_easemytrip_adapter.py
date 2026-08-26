"""Parser contract for the EaseMyTrip adapter.

The live page is ~60KB of AngularJS per row and carries a "Lock Price Rs 304"
upsell in every one, so the fare lookup is anchored on .txt-r6-n rather than
"first number in the row". That anchoring is what this test pins.
"""
from datetime import date

import pytest

from apix.collect.adapters.easemytrip import EaseMyTripAdapter, _extract_rows
from apix.collect.base import FetchOutcome, SearchRequest
from apix.config import load_sources
from apix.models import QuoteStatus
from tests.conftest import ROOT

FIXTURE = ROOT / "tests" / "fixtures" / "easemytrip_results.html"


@pytest.fixture
def html():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def adapter():
    cfg = next(s for s in load_sources() if s.id == "easemytrip")
    return EaseMyTripAdapter(cfg, gate=None, limiter=None)


@pytest.fixture
def req():
    return SearchRequest(route="DEL-BOM", origin="DEL", destination="BOM",
                         departure_date=date(2026, 9, 10), advance_days=15)


def test_extracts_every_row(html):
    rows = _extract_rows(html)
    assert len(rows) == 2


def test_fare_is_the_headline_price_not_the_lock_price_upsell(html):
    totals = [r["total"] for r in _extract_rows(html)]
    assert totals == [6079.0, 12450.0]
    assert 304.0 not in totals


def test_carrier_flight_and_stops(html):
    a, b = _extract_rows(html)
    assert (a["carrier"], a["flight_number"], a["stops"]) == ("IX", "IX1080", 0)
    assert (b["carrier"], b["flight_number"], b["stops"]) == ("6E", "6E6261", 1)
    assert a["cabin"] == b["cabin"] == "ECONOMY"


def test_parse_builds_quotes_carrying_the_request_context(adapter, req, html):
    quotes = adapter.parse(req, FetchOutcome("u", True, QuoteStatus.OK, html=html))
    assert len(quotes) == 2
    assert {q.route for q in quotes} == {"DEL-BOM"}
    assert {q.advance_days for q in quotes} == {15}
    assert {q.departure_date for q in quotes} == {date(2026, 9, 10)}
    assert all(q.status is QuoteStatus.OK and q.currency == "INR" for q in quotes)


def test_stale_selectors_raise_rather_than_returning_nothing(adapter, req):
    """A silent empty list would look like 'no flights' and be quietly imputed."""
    outcome = FetchOutcome("u", True, QuoteStatus.OK, html="<div>redesigned</div>")
    with pytest.raises(ValueError, match="selectors likely stale"):
        adapter.parse(req, outcome)


def test_url_uses_bare_iata_codes_and_day_first_date(adapter, req):
    url = adapter.build_url(req)
    assert "org=DEL" in url and "dept=BOM" in url
    assert "deptDT=10/09/2026" in url          # dd/mm/yyyy, not ISO
    assert url.startswith("https://flight.easemytrip.com/FlightList/Index")
