"""SYNTHETIC fare generator. Not a data source - a test harness.

Nothing in this module ever touches the network. Its only purpose is to
exercise the normalisation, QC, index and API layers with a quote stream whose
TRUE price path is known, so the pipeline can be demonstrated and validated
without waiting on live collection.

Every quote it emits carries source_id prefixed "sim_" and
raw_payload["synthetic"] = True. `apix.api` refuses to serve a series built
from synthetic quotes without an explicit `synthetic=true` flag in the
response, so a demo run can never be mistaken for a published statistic.
"""
from __future__ import annotations

import math
import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterator, Optional

from ..config import Basket, load_basket
from ..models import QuoteStatus, RawQuote

# Rough real-world levels so the numbers look sane on a dashboard.
ROUTE_BASE_INR = {
    "DEL-BOM": 5200, "DEL-BLR": 5600, "BOM-BLR": 4300, "DEL-CCU": 5400,
    "DEL-HYD": 5100, "MAA-DEL": 6100, "BLR-HYD": 3200, "BOM-DEL-GOI": 3900,
    "DEL-PNQ": 5300, "BOM-CCU": 5900, "DEL-AMD": 4200, "BLR-MAA": 3100,
    "DEL-GAU": 6800, "BOM-HYD": 4000, "DEL-SXR": 6500,
}
CARRIER_MULT = {"6E": 1.00, "AI": 1.12, "QP": 0.97, "IX": 0.88, "SG": 0.94, "UK": 1.15}
SOURCE_MARKUP = {"sim_air_india": 1.00, "sim_yatra": 1.035}


def advance_curve(days: int) -> float:
    """Fares fall then flatten as you book earlier; T+1 carries a steep premium."""
    return 1.0 + 1.05 * math.exp(-days / 9.0)


def seasonality(d: date) -> float:
    dow = 1.0 + 0.07 * math.sin((d.weekday() - 3) / 7.0 * 2 * math.pi)
    yearly = 1.0 + 0.09 * math.sin((d.timetuple().tm_yday - 100) / 365.0 * 2 * math.pi)
    return dow * yearly


def generate(
    basket: Optional[Basket] = None,
    start: date = date(2026, 4, 1),
    days: int = 120,
    quotes_per_cell: int = 4,
    seed: int = 20260825,
    fuel_shock_on: Optional[date] = None,
    shock_size: float = 0.12,
    nonresponse_rate: float = 0.06,
    sources: tuple[str, ...] = ("sim_air_india", "sim_yatra"),
) -> Iterator[RawQuote]:
    """Emit a synthetic quote stream with a known underlying price path."""
    basket = basket or load_basket()
    rng = random.Random(seed)

    for i in range(days):
        day = start + timedelta(days=i)
        collected_at = datetime.combine(day, time(6, 0), tzinfo=timezone.utc)
        drift = 1.0028 ** i                      # slow underlying trend
        shock = shock_size if (fuel_shock_on and day >= fuel_shock_on) else 0.0

        for route in basket.route_weights:
            parts = route.split("-")
            origin, dest = parts[0], parts[-1]
            base = ROUTE_BASE_INR.get(route, 5000)
            for carrier in basket.carrier_weights:
                for adv in basket.window_weights:
                    for src in sources:
                        if rng.random() < nonresponse_rate:
                            yield RawQuote(
                                source_id=src, collected_at=collected_at, route=route,
                                origin=origin, destination=dest,
                                departure_date=day + timedelta(days=adv), advance_days=adv,
                                carrier=carrier, status=QuoteStatus.FETCH_FAILED,
                                raw_payload={"synthetic": True, "reason": "simulated non-response"},
                            )
                            continue
                        centre = (
                            base * CARRIER_MULT.get(carrier, 1.0)
                            * SOURCE_MARKUP.get(src, 1.0)
                            * advance_curve(adv) * seasonality(day) * drift * (1.0 + shock)
                        )
                        for k in range(quotes_per_cell):
                            # Within-cell dispersion: several flights and fare
                            # buckets on the same day, right-skewed.
                            fare = centre * math.exp(rng.gauss(0.0, 0.11)) * (1.0 + 0.35 * (rng.random() ** 6))
                            total = round(fare, 0)
                            taxes = round(total * 0.16, 0)
                            yield RawQuote(
                                source_id=src, collected_at=collected_at, route=route,
                                origin=origin, destination=dest,
                                departure_date=day + timedelta(days=adv), advance_days=adv,
                                carrier=carrier, flight_number=f"{carrier}{rng.randint(100, 999)}",
                                cabin="ECONOMY", fare_family="STANDARD",
                                total_inr=total, base_inr=total - taxes, taxes_inr=taxes,
                                currency="INR", stops=0, status=QuoteStatus.OK,
                                raw_payload={"synthetic": True},
                            )


def true_index_path(start: date, days: int, base_value: float = 100.0,
                    fuel_shock_on: Optional[date] = None, shock_size: float = 0.12) -> list[tuple[date, float]]:
    """The index the generator's parameters imply, ignoring noise and seasonality
    of the *cell mix*. Used by tests to check the engine recovers the truth."""
    out = []
    for i in range(days):
        day = start + timedelta(days=i)
        drift = 1.0028 ** i
        shock = shock_size if (fuel_shock_on and day >= fuel_shock_on) else 0.0
        out.append((day, base_value * drift * seasonality(day) / seasonality(start) * (1.0 + shock)))
    return out
