"""Yatra (OTA) adapter.

robots.txt audit (2026-08-25): affiliate and beta paths are disallowed
(/FM/, /TP/, /ads/, /travel-beta/cheap-air-tickets); general flight search is
not. ClaudeBot / GPTBot / anthropic-ai are explicitly permitted with
Crawl-delay: 5, which the gate enforces.

An OTA is the only legitimate route to fares for the carriers whose own sites
disallow collection. It is NOT a substitute for airline-direct pricing: the
quote carries the OTA's markup and its inventory access. That is why the source
is part of the cell identity - the index compares Yatra-6E to Yatra-6E over
time, never to IndiGo-direct. See METHODOLOGY.md.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from ...models import QuoteStatus, RawQuote
from ..base import BaseAdapter, FetchOutcome, SearchRequest

RESULTS = "#flight-results, .flight-listing, [data-testid='flight-list']"


class YatraAdapter(BaseAdapter):
    def build_url(self, req: SearchRequest) -> str:
        d = req.departure_date.strftime("%d/%m/%Y")
        return (f"{self.config.base_url}/flights/search"
                f"?type=O&class=Economy&noOfSegments=1&origin={req.origin}"
                f"&destination={req.destination}&flight_depart_date={d}&ADT=1&CHD=0&INF=0")

    def wait_for_results(self, page) -> None:
        page.wait_for_selector(RESULTS, timeout=self.config.timeout_s * 1000)
        page.wait_for_timeout(2000)

    def parse(self, req: SearchRequest, outcome: FetchOutcome) -> list[RawQuote]:
        rows = _extract_from_embedded_json(outcome.html or "")
        if not rows:
            raise ValueError("no fare records found in page payload - selectors/JSON shape likely stale")
        now = datetime.now(timezone.utc)
        return [
            RawQuote(
                source_id=self.config.id, collected_at=now,
                route=req.route, origin=req.origin, destination=req.destination,
                departure_date=req.departure_date, advance_days=req.advance_days,
                carrier=r.get("carrier"), flight_number=r.get("flight_number"),
                cabin="ECONOMY", fare_family=r.get("fare_family"),
                total_inr=r.get("total"), base_inr=r.get("base"), taxes_inr=r.get("taxes"),
                currency="INR", stops=r.get("stops"),
                status=QuoteStatus.OK, raw_payload=r,
            ) for r in rows
        ]


_JSON_BLOB = re.compile(r"window\.__(?:INITIAL_STATE|SEARCH_RESULTS)__\s*=\s*(\{.*?\});", re.S)


def _extract_from_embedded_json(html: str) -> list[dict]:
    """OTAs hydrate results from an embedded JSON blob. Reading the blob the
    page already delivered is both more robust and gentler than driving the DOM."""
    m = _JSON_BLOB.search(html)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out: list[dict] = []
    for item in _walk_for_fares(data):
        out.append(item)
    return out


def _walk_for_fares(node, depth: int = 0) -> list[dict]:
    """Find fare-shaped dicts anywhere in the payload without hard-coding a path."""
    found: list[dict] = []
    if depth > 8:
        return found
    if isinstance(node, dict):
        keys = {k.lower() for k in node}
        if {"airlinecode", "flightnumber"} & keys and ({"totalfare", "fare", "price"} & keys):
            g = lambda *names: next((node[k] for k in node if k.lower() in names), None)
            found.append({
                "carrier": g("airlinecode", "airline"),
                "flight_number": g("flightnumber", "flightno"),
                "total": g("totalfare", "price", "fare"),
                "base": g("basefare"),
                "taxes": g("tax", "taxes", "totaltax"),
                "stops": g("stops", "noofstops"),
                "fare_family": g("farefamily", "fareclass", "faretype"),
            })
        for v in node.values():
            found += _walk_for_fares(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            found += _walk_for_fares(v, depth + 1)
    return found
