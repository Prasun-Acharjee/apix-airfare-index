"""Which sources the basket is weighted over, and when that may change.

Narrowing the basket is a statement about what the index MEASURES, so it is a
recorded decision in config/basket.yaml — never something a quiet source does by
itself. These tests pin that distinction, because getting it wrong in either
direction is a bias: an automatic narrowing lets non-response reshape the
basket, and a scope that cannot be overridden makes every replay unbuildable.
"""
from __future__ import annotations

from datetime import date

import pytest
import yaml

from apix.config import CONFIG_DIR, Basket, load_basket, load_sources
from apix.pipeline import scope_to_dataset

ALL_COLLECTABLE = tuple(s.id for s in load_sources() if s.collectable)


@pytest.fixture
def unscoped() -> Basket:
    import dataclasses
    return dataclasses.replace(load_basket(), active_sources=None)


@pytest.fixture
def scoped() -> Basket:
    return load_basket().with_sources(("easemytrip",))


# --- the configured scope ----------------------------------------------------

def test_the_shipped_config_declares_its_scope():
    raw = yaml.safe_load((CONFIG_DIR / "basket.yaml").read_text())
    declared = (raw.get("sources") or {}).get("active")
    assert declared, "basket.yaml must record the source scope it is weighted over"
    assert load_basket().active_sources == tuple(sorted(declared))


def test_narrowing_keeps_every_carrier_and_still_sums_to_one(scoped, unscoped):
    """The cost of narrowing is the channel dimension, not carrier coverage.

    EaseMyTrip quotes all six carriers, so dropping the two airline-direct
    sources loses the direct-vs-OTA split and nothing else. If that ever stops
    holding, the published index quietly stops covering part of the market.
    """
    wide, narrow = list(unscoped.cells()), list(scoped.cells())
    assert {c.carrier for c in narrow} == {c.carrier for c in wide}
    assert {c.route for c in narrow} == {c.route for c in wide}
    assert len(narrow) < len(wide)
    assert sum(scoped.cell_weight(c) for c in narrow) == pytest.approx(1.0)


def test_a_source_outside_the_scope_carries_no_weight(scoped):
    from apix.models import Cell
    outside = Cell(route="DEL-BOM", carrier="AI", advance_days=7, source_id="air_india")
    inside = Cell(route="DEL-BOM", carrier="AI", advance_days=7, source_id="easemytrip")
    assert scoped.cell_weight(outside) == 0.0
    assert scoped.cell_weight(inside) > 0.0


# --- scope_to_dataset: the three cases ---------------------------------------

def test_a_configured_scope_survives_a_source_going_quiet(scoped):
    """The whole point. air_india returning nothing today must not re-widen the
    basket tomorrow when it returns one quote, nor narrow it further today."""
    assert scope_to_dataset(scoped, ("easemytrip",)).active_sources == ("easemytrip",)
    # Even when a descoped source shows up in the data, the decision stands.
    assert scope_to_dataset(scoped, ("air_india", "easemytrip")).active_sources == ("easemytrip",)


def test_a_scope_matching_nothing_falls_back_to_the_dataset(scoped):
    """A synthetic run's ids are `sim_*`. Weighting over a scope that matches no
    quote would yield an index of zero cells rather than an error."""
    got = scope_to_dataset(scoped, ("sim_air_india", "sim_yatra"))
    assert got.active_sources == ("sim_air_india", "sim_yatra")


def test_without_a_configured_scope_the_dataset_decides(unscoped):
    got = scope_to_dataset(unscoped, ("air_india", "yatra"))
    assert got.active_sources == ("air_india", "yatra")


def test_an_empty_dataset_leaves_the_basket_alone(scoped, unscoped):
    assert scope_to_dataset(scoped, ()).active_sources == ("easemytrip",)
    assert scope_to_dataset(unscoped, ()).active_sources is None


# --- the config is validated, not trusted ------------------------------------

def _basket_from(mapping: dict):
    from apix.config import _active_sources
    return _active_sources(mapping)


def test_an_empty_scope_is_rejected():
    with pytest.raises(ValueError, match="it is no index"):
        _basket_from({"sources": {"active": []}})


def test_a_scope_naming_an_unknown_source_is_rejected():
    # Silently dropping that weight would understate coverage forever.
    with pytest.raises(ValueError, match="not.*in sources.yaml"):
        _basket_from({"sources": {"active": ["easemytrip", "kayak"]}})


def test_no_sources_key_means_span_everything_collectable():
    assert _basket_from({}) is None
    assert _basket_from({"sources": None}) is None


# --- the end-to-end effect ---------------------------------------------------

def test_narrowing_makes_a_single_source_day_publishable():
    """The reason for the change: with air_india and yatra in the basket and
    silent, imputation share ran 85-95% and every point was withheld."""
    from apix.collect.simulator import generate
    from apix.pipeline import build_index

    # One source, standing in for the live single-source case. The id does not
    # matter — scope_to_dataset falls back to the dataset for a `sim_*` replay,
    # so what is under test is a basket weighted over exactly one source.
    basket = load_basket()
    raws = list(generate(basket, start=date(2026, 4, 1), days=6,
                         fuel_shock_on=None, sources=("sim_yatra",)))
    assert raws
    daily = build_index(raws, basket)["daily"]
    assert daily[-1].quality != "fail"
    assert daily[-1].imputation_share < 0.60
