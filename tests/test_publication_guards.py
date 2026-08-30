"""What the pipeline refuses to publish, and why one timeout must not cost a source.

Both guards here exist because of the same three-day outage: the nightly job
reported success every night while the published series sat frozen. Air India
and Yatra returned no quotes, their basket weight was imputed instead, every
new point came out `fail`-quality, and the website — which hides `fail` points —
went on serving the last good day. Nothing anywhere exited non-zero.
"""
from __future__ import annotations

import importlib.util
import urllib.error
from datetime import date
from pathlib import Path

import pytest

import apix.compliance.robots as robots_mod
from apix.compliance.robots import ROBOTS_TRANSIENT_ATTEMPTS, RobotsGate
from apix.models import Cell, CellPrice, IndexPoint

ROOT = Path(__file__).resolve().parent.parent
UA = "APIx-ResearchBot/0.1"


def _load_seed_script():
    spec = importlib.util.spec_from_file_location(
        "seed_postgres", ROOT / "scripts" / "seed_postgres.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


seed = _load_seed_script()


# --- the robots gate: a timeout is not a policy ------------------------------

@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(robots_mod.time, "sleep", lambda _s: None)


def test_a_timed_out_robots_fetch_is_retried_before_failing_closed(no_sleep, monkeypatch):
    attempts = []

    def boom(req, timeout=0):
        attempts.append(timeout)
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(robots_mod.urllib.request, "urlopen", boom)
    d = RobotsGate(user_agent=UA).check("https://www.airindia.com/in/en/book/x")
    assert d.allowed is False           # still fails closed
    assert d.readable is False
    assert len(attempts) == ROBOTS_TRANSIENT_ATTEMPTS


def test_a_transient_failure_is_not_cached_for_the_whole_run(no_sleep, monkeypatch):
    # One slow response used to poison the cache for a full hour, so all 75 of a
    # source's requests were refused from a single timeout at the top of the run.
    calls = {"n": 0}
    body = "User-agent: *\nAllow: /\n"

    def flaky(req, timeout=0):
        calls["n"] += 1
        if calls["n"] <= ROBOTS_TRANSIENT_ATTEMPTS:
            raise TimeoutError("The read operation timed out")
        class R:
            def read(self): return body.encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()

    monkeypatch.setattr(robots_mod.urllib.request, "urlopen", flaky)
    g = RobotsGate(user_agent=UA)
    assert g.check("https://www.yatra.com/flights/search").allowed is False
    entry = g._cache["https://www.yatra.com"]
    assert entry.ttl_s == robots_mod.ROBOTS_TRANSIENT_TTL_S
    assert entry.ttl_s < robots_mod.ROBOTS_TTL_S

    # Expire the short-lived entry; the next request gets a real answer.
    entry.fetched_at -= robots_mod.ROBOTS_TRANSIENT_TTL_S + 1
    assert g.check("https://www.yatra.com/flights/search").allowed is True


@pytest.mark.parametrize("status", [403, 429, 401, 404])
def test_an_http_refusal_is_answered_once_and_never_retried(status, no_sleep, monkeypatch):
    """Retrying a 403 is exactly the evasion this project refuses to do."""
    attempts = []

    def refuse(req, timeout=0):
        attempts.append(status)
        raise urllib.error.HTTPError(req.full_url, status, "no", {}, None)

    monkeypatch.setattr(robots_mod.urllib.request, "urlopen", refuse)
    g = RobotsGate(user_agent=UA)
    assert g.check("https://www.akasaair.com/search").allowed is False
    assert len(attempts) == 1
    # And it is remembered for the full TTL: the operator has answered.
    assert g._cache["https://www.akasaair.com"].ttl_s == robots_mod.ROBOTS_TTL_S


# --- the publication guard: a fail-quality point is not published ------------

def _cell(source_id: str) -> Cell:
    return Cell(route="DEL-BOM", carrier="AI", advance_days=7, source_id=source_id)


def _price(source_id: str, day: date) -> CellPrice:
    return CellPrice(cell=_cell(source_id), on_date=day, price=5000.0, n_quotes=3)


def _point(day: date, quality: str) -> IndexPoint:
    return IndexPoint(
        on_date=day, value=109.68, frequency="daily", n_cells_matched=4,
        n_cells_imputed=30, coverage=0.946, imputation_share=0.849, quality=quality,
        notes=["imputation share 84.9% at or above fail threshold"],
    )


class FakeStore:
    def __init__(self): self.closed = False
    def close(self): self.closed = True


def _result(qualities: list[str], cell_prices=None) -> dict:
    days = [date(2026, 8, 26 + i) for i in range(len(qualities))]
    return {
        "daily": [_point(d, q) for d, q in zip(days, qualities)],
        "cell_prices": cell_prices if cell_prices is not None else {},
    }


def test_a_publishable_series_is_not_blocked():
    assert seed.refuse_unpublishable(_result(["ok", "ok", "warn"]), FakeStore()) == 0


def test_a_fail_quality_newest_point_stops_the_publish():
    store = FakeStore()
    assert seed.refuse_unpublishable(_result(["ok", "ok", "fail"]), store) == 4
    assert store.closed is True


def test_an_older_failure_does_not_block_a_recovered_series():
    # The newest point is what gets published. An old bad day already withheld
    # must not keep the index frozen once collection recovers.
    assert seed.refuse_unpublishable(_result(["ok", "fail", "ok"]), FakeStore()) == 0


def test_an_empty_series_is_left_to_the_existing_guards():
    assert seed.refuse_unpublishable({"daily": [], "cell_prices": {}}, FakeStore()) == 0


def test_the_source_that_stopped_returning_quotes_is_named():
    yesterday, today = date(2026, 8, 29), date(2026, 8, 30)
    prices = {
        yesterday: {_cell(s): _price(s, yesterday)
                    for s in ("air_india", "yatra", "easemytrip")},
        today: {_cell("easemytrip"): _price("easemytrip", today)},
    }
    result = _result(["ok", "fail"], cell_prices=prices)
    assert seed.missing_sources(result) == ["air_india", "yatra"]
    assert seed.refuse_unpublishable(result, FakeStore()) == 4
