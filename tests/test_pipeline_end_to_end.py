"""Full pipeline against a synthetic stream whose true price path is known."""
from __future__ import annotations

from datetime import date

import pytest

from apix.collect.simulator import generate, true_index_path
from apix.config import load_basket
from apix.pipeline import build_index

START = date(2026, 4, 1)
DAYS = 90
SHOCK = date(2026, 5, 20)


@pytest.fixture(scope="module")
def run():
    quotes = list(generate(load_basket(), start=START, days=DAYS,
                           fuel_shock_on=SHOCK, shock_size=0.12, seed=7))
    return build_index(quotes), dict(true_index_path(START, DAYS, 100.0, SHOCK, 0.12))


def test_index_recovers_the_true_price_path(run):
    result, truth = run
    daily = result["daily"]
    assert len(daily) == DAYS
    final = daily[-1]
    expected = truth[final.on_date]
    err = abs(final.value / expected - 1)
    assert err < 0.01, f"endpoint off by {err:.2%} (index {final.value:.2f} vs true {expected:.2f})"


def test_no_systematic_drift_across_the_series(run):
    """Chained links must not accumulate a one-directional error."""
    result, truth = run
    errs = [p.value / truth[p.on_date] - 1 for p in result["daily"]]
    assert max(abs(e) for e in errs) < 0.05
    assert abs(sum(errs) / len(errs)) < 0.02, "mean error suggests chain drift, not noise"


def test_the_shock_lands_on_the_right_day(run):
    result, _ = run
    by_date = {p.on_date: p.value for p in result["daily"]}
    day_before = SHOCK.toordinal() - 1
    jump = by_date[SHOCK] / by_date[date.fromordinal(day_before)]
    assert 1.08 < jump < 1.16, f"12% shock showed up as {jump:.3f}x"


def test_non_response_is_imputed_and_reported(run):
    result, _ = run
    shares = [p.imputation_share for p in result["daily"][1:]]
    assert all(s > 0 for s in shares), "simulated non-response should produce imputation"
    assert max(shares) < 0.25, "imputation share far above the simulated non-response rate"
    assert all(p.quality == "ok" for p in result["daily"][1:])


def test_coverage_warms_up_then_stays_complete(run):
    """Coverage starts below 100% and climbs over the first few days.

    A cell missing on day 1 has no previous price, so it cannot be imputed and
    contributes nothing until it is observed twice. Once the carried-forward
    state has filled in - about three days at a 6% non-response rate - coverage
    is complete and stays there. This warm-up is a property of the construction,
    not a defect, and it is why the published series should start a few days
    after collection begins.
    """
    result, _ = run
    cov = [p.coverage for p in result["daily"]]
    assert cov[0] < 0.99, "day 1 cannot have full coverage with non-response present"
    assert cov[3] > 0.99, "coverage should be complete by day 4"
    assert min(cov[3:]) > 0.99, "coverage regressed after warm-up"
    assert cov[1] >= cov[0]


def test_qc_rejects_only_genuine_outliers(run):
    result, _ = run
    assert result["qc"]["rejection_rate"] < 0.10
    assert set(result["qc"]["reasons"]) <= {"within_cell_outlier"}


def test_monthly_series_is_not_a_product_of_daily_links(run):
    """Monthly must come from direct month-to-month comparison (drift control)."""
    result, _ = run
    monthly = result["monthly"]
    assert len(monthly) >= 3
    assert all(p.frequency == "monthly" for p in monthly)
    assert monthly[-1].value > monthly[0].value
