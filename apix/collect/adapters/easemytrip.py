"""EaseMyTrip adapter.

robots.txt audit (2026-08-26): fare results are served from the separate host
`flight.easemytrip.com`, whose robots.txt disallows only /cgi-bin/, /admin/,
/test/, /cheap_flights/, /cheap-flights/, /holiday_packages/,
/international_airlines/, /Packages/, /static/ and /holiday-query/.
`/FlightList/Index` is not disallowed, for `*` or for us. No Crawl-delay
directive, so our 5s floor applies.

Note the www host is a DIFFERENT robots.txt which disallows
`/flight-search/listing*`. Point `base_url` at the flight subdomain, not www,
so the runtime gate reads the policy that actually governs the path we fetch.

The page is AngularJS and renders progressively, so `wait_for_results` waits on
the row container rather than a fixed timeout. Selectors are written against
the booking flow as of the audit date and WILL rot; `parse` raises rather than
returning an empty list so a layout change surfaces as a loud parse error in
collection_log instead of a quiet run of imputed cells that looks like data.
"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime, timezone

from ...models import QuoteStatus, RawQuote
from ..base import BaseAdapter, FetchOutcome, SearchRequest

RESULTS = ".fltResult"

# Each result row opens with class="row no-margn fltResult ng-scope". Splitting
# on that keeps every field lookup scoped to one flight, which matters because
# a row carries a "Lock Price Rs 304" upsell whose number is not a fare.
_ROW = re.compile(r'class="[^"]*\bfltResult\b[^"]*"')
_TAGS = re.compile(r"<[^>]+>")
_FLIGHT = re.compile(r"\b(AI|IX|6E|SG|QP|UK|G8)\s*-\s*(\d{1,4})\b")
# Anchored on the headline-fare class, not on "the first number in the row".
_PRICE = re.compile(r"txt-r6-n.{0,600}?>\s*([\d,]{3,})\s*<", re.S)
_STOPS = re.compile(r"dura_md2.{0,400}?>\s*([^<]{1,20}?)\s*<", re.S)
_NSTOP = re.compile(r"(\d)\s*stop", re.I)
_CABIN = re.compile(r"\b(ECONOMY|PREMIUM ECONOMY|BUSINESS|FIRST)\b", re.I)


class EaseMyTripAdapter(BaseAdapter):
    def build_url(self, req: SearchRequest) -> str:
        d = req.departure_date.strftime("%d/%m/%Y")
        # Bare IATA codes are accepted; the code-plus-city form the site's own
        # links use returns an empty result set when rebuilt by hand.
        return (
            f"{self.config.base_url}{self.config.search_path_template}"
            f"?org={req.origin}&dept={req.destination}"
            f"&adt=1&chd=0&inf=0&cabin=0&airline=Any"
            f"&deptDT={d}&arrDT=undefined&isOneway=true&isDomestic=true"
        )

    def wait_for_results(self, page) -> None:
        page.wait_for_selector(RESULTS, timeout=self.config.timeout_s * 1000)
        # Angular fills prices into rows after the rows themselves appear.
        page.wait_for_timeout(4000)

    def parse(self, req: SearchRequest, outcome: FetchOutcome) -> list[RawQuote]:
        rows = _extract_rows(outcome.html or "")
        if not rows:
            raise ValueError(
                "results container rendered but no fare rows matched - selectors likely stale"
            )
        now = datetime.now(timezone.utc)
        return [
            RawQuote(
                source_id=self.config.id, collected_at=now,
                route=req.route, origin=req.origin, destination=req.destination,
                departure_date=req.departure_date, advance_days=req.advance_days,
                carrier=r["carrier"], flight_number=r["flight_number"],
                cabin=r["cabin"], total_inr=r["total"], currency="INR",
                stops=r["stops"], status=QuoteStatus.OK, raw_payload=r,
            ) for r in rows
        ]


def _extract_rows(html: str) -> list[dict]:
    out: list[dict] = []
    for chunk in _ROW.split(html)[1:]:
        price = _PRICE.search(chunk)
        if not price:
            continue
        # Tag-stripped text is only used for the header fields, which sit in
        # the first few KB; a row is ~60KB once the fare-options modal is in it.
        head = _html.unescape(_TAGS.sub(" ", chunk[:4000]))
        flight = _FLIGHT.search(head)
        if not flight:
            continue
        cabin = _CABIN.search(head)
        out.append({
            "carrier": flight.group(1),
            "flight_number": flight.group(1) + flight.group(2),
            "total": float(price.group(1).replace(",", "")),
            "stops": _parse_stops(chunk),
            "cabin": cabin.group(1).upper().replace(" ", "_") if cabin else "ECONOMY",
        })
    return out


def _parse_stops(chunk: str) -> int | None:
    m = _STOPS.search(chunk)
    if not m:
        return None
    label = _html.unescape(m.group(1)).strip()
    if label.lower().startswith("non-stop"):
        return 0
    n = _NSTOP.search(label)
    return int(n.group(1)) if n else None
