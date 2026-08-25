"""Normalisation: heterogeneous scraped quotes -> comparable cell observations.

Price concept
-------------
The index price is the ALL-IN fare a consumer pays: base fare plus statutory
taxes (GST), plus regulated airport charges (UDF/PSF/ASF), plus carrier
surcharges that are not optional. This matches the CPI acquisition-price
concept - what the household actually hands over. Statutory rate changes are
genuine price changes to the consumer and are not netted out.

Optional ancillaries are excluded: seat selection, baggage beyond the included
allowance, meals, priority boarding, insurance. They are separately purchasable
services, not part of the transport item, and including them would make the
index reflect the site's default checkbox state rather than the fare.

`base_inr` and `taxes_inr` are retained so an ex-tax variant can be published
alongside the headline series - useful for separating a GST change from an
underlying fare movement, which is exactly the question a monetary-policy user
asks.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Iterable, Iterator, Optional

from ..models import Cell, NormalisedQuote, QuoteStatus, RawQuote

# Fare-family strings vary wildly by source. We map to a canonical ladder so a
# cell is never accidentally matched across genuinely different products.
FARE_FAMILY_MAP = {
    "saver": "SAVER", "lite": "SAVER", "eco value": "SAVER", "economy saver": "SAVER",
    "comfort": "STANDARD", "flexi": "FLEX", "flexi plus": "FLEX", "eco flex": "FLEX",
    "value": "STANDARD", "economy": "STANDARD", "eco": "STANDARD",
    "corporate": "CORPORATE", "sme": "CORPORATE",
    "student": "SPECIAL", "armed forces": "SPECIAL", "senior citizen": "SPECIAL",
}

CABIN_MAP = {
    "economy": "ECONOMY", "eco": "ECONOMY", "e": "ECONOMY", "y": "ECONOMY",
    "premium economy": "PREMIUM_ECONOMY", "premium": "PREMIUM_ECONOMY", "w": "PREMIUM_ECONOMY",
    "business": "BUSINESS", "c": "BUSINESS", "j": "BUSINESS",
}

_NUM = re.compile(r"[^\d.]")
_CARRIER = re.compile(r"^([A-Z0-9]{2})[\s-]?(\d{1,4})$")


def parse_inr(value) -> Optional[float]:
    """'â‚¹ 5,499' / '5499.00' / 5499 -> 5499.0. Returns None on junk."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = _NUM.sub("", str(value))
    if not s or s == ".":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def canonical_cabin(value: Optional[str]) -> str:
    if not value:
        return "ECONOMY"
    return CABIN_MAP.get(value.strip().lower(), value.strip().upper().replace(" ", "_"))


def canonical_fare_family(value: Optional[str]) -> str:
    if not value:
        return "STANDARD"
    return FARE_FAMILY_MAP.get(value.strip().lower(), "OTHER")


def carrier_from_flight_number(flight_number: Optional[str]) -> Optional[str]:
    if not flight_number:
        return None
    m = _CARRIER.match(flight_number.strip().upper())
    return m.group(1) if m else None


def advance_days(collected_on: date, departure: date) -> int:
    return (departure - collected_on).days


def normalise(raw: RawQuote, price_concept: str = "all_in") -> Optional[NormalisedQuote]:
    """Convert one raw quote. Returns None if it cannot be made comparable."""
    if raw.status != QuoteStatus.OK:
        return None
    if raw.currency != "INR":
        return None  # FX conversion deliberately out of scope; a converted fare
                     # would mix exchange-rate movement into an airfare index.

    carrier = (raw.carrier or carrier_from_flight_number(raw.flight_number) or "").upper()
    if not carrier:
        return None

    total = parse_inr(raw.total_inr)
    base = parse_inr(raw.base_inr)
    taxes = parse_inr(raw.taxes_inr)
    surch = parse_inr(raw.surcharges_inr) or 0.0

    if total is None and base is not None:
        total = base + (taxes or 0.0) + surch
    if total is None:
        return None
    if base is None:
        base = total - (taxes or 0.0) - surch
    if taxes is None:
        taxes = max(total - base - surch, 0.0)

    price = total if price_concept == "all_in" else base

    collected_on = raw.collected_at.date() if isinstance(raw.collected_at, datetime) else raw.collected_at
    days = raw.advance_days if raw.advance_days is not None else advance_days(collected_on, raw.departure_date)

    cell = Cell(
        route=raw.route,
        carrier=carrier,
        advance_days=days,
        source_id=raw.source_id,
        cabin=canonical_cabin(raw.cabin),
    )
    return NormalisedQuote(
        source_id=raw.source_id,
        collected_on=collected_on,
        cell=cell,
        departure_date=raw.departure_date,
        price_inr=float(price),
        total_inr=float(total),
        base_inr=float(base),
        taxes_inr=float(taxes),
        flight_number=raw.flight_number,
        stops=raw.stops,
    )


def normalise_all(raws: Iterable[RawQuote], price_concept: str = "all_in") -> Iterator[NormalisedQuote]:
    for r in raws:
        q = normalise(r, price_concept)
        if q is not None:
            yield q
