"""Adapter contract and the fetch path every adapter must go through."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from ..compliance.ratelimit import HostLimiter
from ..compliance.robots import RobotsGate, is_block_response
from ..config import SourceConfig
from ..models import QuoteStatus, RawQuote

log = logging.getLogger(__name__)


@dataclass
class FetchOutcome:
    url: str
    ok: bool
    status: QuoteStatus
    detail: str = ""
    html: Optional[str] = None
    payload: dict = field(default_factory=dict)


@dataclass
class SearchRequest:
    route: str
    origin: str
    destination: str
    departure_date: date
    advance_days: int


class BaseAdapter(ABC):
    """One adapter per source.

    Adapters never call the network directly. They build a URL, hand it to
    `fetch`, and parse what comes back. That single choke point is what makes
    the compliance guarantee checkable: there is exactly one place where an
    outbound request happens, and it is gated.
    """

    def __init__(self, config: SourceConfig, gate: RobotsGate, limiter: HostLimiter,
                 browser=None):
        self.config = config
        self.gate = gate
        self.limiter = limiter
        self.browser = browser

    # --- to implement per source ------------------------------------------
    @abstractmethod
    def build_url(self, req: SearchRequest) -> str: ...

    @abstractmethod
    def parse(self, req: SearchRequest, outcome: FetchOutcome) -> list[RawQuote]: ...

    def requires_javascript(self) -> bool:
        return True

    # --- the only network path --------------------------------------------
    def fetch(self, url: str) -> FetchOutcome:
        decision = self.gate.check(url)
        if not decision:
            return FetchOutcome(url, False, QuoteStatus.NOT_COLLECTED,
                                f"robots gate refused: {decision.reason}")

        host = urlparse(url).netloc
        self.limiter.delay_s = max(self.limiter.delay_s, decision.crawl_delay_s or 0.0)
        self.limiter.acquire(host)

        if self.browser is None:
            return FetchOutcome(url, False, QuoteStatus.FETCH_FAILED,
                                "no browser session supplied")
        try:
            page = self.browser.new_page(user_agent=self.config.user_agent)
            try:
                resp = page.goto(url, timeout=self.config.timeout_s * 1000,
                                 wait_until="domcontentloaded")
                status = resp.status if resp else 0

                if is_block_response(status):
                    # The site is declining us. We stop here, permanently for
                    # this run. We do not retry from elsewhere, rotate identity,
                    # or attempt a challenge. Recorded as a non-response and
                    # handled by imputation downstream.
                    return FetchOutcome(url, False, QuoteStatus.BLOCKED_BY_SITE,
                                        f"HTTP {status} - site declined; not retried")
                if status >= 400:
                    return FetchOutcome(url, False, QuoteStatus.FETCH_FAILED, f"HTTP {status}")

                self.wait_for_results(page)
                return FetchOutcome(url, True, QuoteStatus.OK, html=page.content())
            finally:
                page.close()
        except Exception as e:
            return FetchOutcome(url, False, QuoteStatus.FETCH_FAILED, f"{type(e).__name__}: {e}")

    def wait_for_results(self, page) -> None:
        """Override to wait on the source's own results container."""
        page.wait_for_timeout(3000)

    def collect(self, req: SearchRequest) -> tuple[list[RawQuote], FetchOutcome]:
        url = self.build_url(req)
        outcome = self.fetch(url)
        if not outcome.ok:
            return [self.non_response(req, outcome)], outcome
        try:
            return self.parse(req, outcome), outcome
        except Exception as e:
            outcome = FetchOutcome(url, False, QuoteStatus.FETCH_FAILED, f"parse error: {e}")
            return [self.non_response(req, outcome)], outcome

    def non_response(self, req: SearchRequest, outcome: FetchOutcome) -> RawQuote:
        """A recorded absence. Absences are data - they explain imputation later."""
        return RawQuote(
            source_id=self.config.id,
            collected_at=datetime.now(timezone.utc),
            route=req.route, origin=req.origin, destination=req.destination,
            departure_date=req.departure_date, advance_days=req.advance_days,
            status=outcome.status,
            raw_payload={"url": outcome.url, "detail": outcome.detail},
        )
