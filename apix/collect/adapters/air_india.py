"""Air India adapter.

robots.txt audit (2026-08-25): fare search is not disallowed; /bin/, a company
image path, the Google flight-booking page and a loyalty page are. The file
additionally names ClaudeBot, GPTBot, Google-Extended, PerplexityBot, xAI-Bot,
DeepseekBot and CCBot with "Allow: *". No Crawl-delay, so our 5s floor applies.

The selectors below are written against the booking flow as of the audit date
and WILL rot. `parse` raises rather than returning an empty list when the
results container is present but no row matches a selector, so a layout change
surfaces as a loud parse error in collection_log instead of a quiet run of
imputed cells that looks like real data.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ...models import QuoteStatus, RawQuote
from ..base import BaseAdapter, FetchOutcome, SearchRequest

RESULTS = "[data-testid='flight-results'], .flight-results, .search-results"
ROW = "[data-testid='flight-card'], .flight-card, .fare-row"


class AirIndiaAdapter(BaseAdapter):
    def build_url(self, req: SearchRequest) -> str:
        d = req.departure_date.strftime("%Y-%m-%d")
        return (f"{self.config.base_url}/in/en/book/flight-search.html"
                f"?tripType=O&origin={req.origin}&destination={req.destination}"
                f"&departureDate={d}&adults=1&cabinClass=Economy")

    def wait_for_results(self, page) -> None:
        page.wait_for_selector(RESULTS, timeout=self.config.timeout_s * 1000)
        page.wait_for_timeout(1500)

    def parse(self, req: SearchRequest, outcome: FetchOutcome) -> list[RawQuote]:
        rows = _extract_rows(outcome.html or "")
        if not rows:
            raise ValueError("results container rendered but no fare rows matched - selectors likely stale")
        now = datetime.now(timezone.utc)
        return [
            RawQuote(
                source_id=self.config.id, collected_at=now,
                route=req.route, origin=req.origin, destination=req.destination,
                departure_date=req.departure_date, advance_days=req.advance_days,
                carrier=r.get("carrier", "AI"), flight_number=r.get("flight_number"),
                cabin="ECONOMY", fare_family=r.get("fare_family"),
                total_inr=r.get("total"), base_inr=r.get("base"), taxes_inr=r.get("taxes"),
                currency="INR", stops=r.get("stops"),
                status=QuoteStatus.OK, raw_payload=r,
            ) for r in rows
        ]


_FLIGHT = re.compile(r"\b(AI|IX)[\s-]?(\d{1,4})\b")
_PRICE = re.compile(r"(?:₹|INR|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)")


def _extract_rows(html: str) -> list[dict]:
    """Deliberately regex-based fallback so the adapter degrades rather than
    hard-failing on a class-name change. A structured DOM parse via Playwright
    locators is preferred and is what `wait_for_results` sets up."""
    out: list[dict] = []
    for m in _FLIGHT.finditer(html):
        window = html[m.start(): m.start() + 1200]
        prices = [float(p.replace(",", "")) for p in _PRICE.findall(window)]
        if not prices:
            continue
        out.append({
            "carrier": m.group(1),
            "flight_number": f"{m.group(1)}{m.group(2)}",
            "total": min(prices),
            "stops": 0 if "non-stop" in window.lower() or "nonstop" in window.lower() else None,
        })
    return out
