"""Collection orchestration: basket -> search requests -> quotes -> database."""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

from ..compliance.ratelimit import HostLimiter
from ..compliance.robots import RobotsGate
from ..config import Basket, SourceConfig, load_basket, load_sources
from ..models import QuoteStatus, RawQuote
from .adapters.air_india import AirIndiaAdapter
from .adapters.easemytrip import EaseMyTripAdapter
from .adapters.yatra import YatraAdapter
from .base import BaseAdapter, SearchRequest

log = logging.getLogger(__name__)

ADAPTERS: dict[str, type[BaseAdapter]] = {
    "air_india": AirIndiaAdapter,
    "easemytrip": EaseMyTripAdapter,
    "yatra": YatraAdapter,
}


def search_requests(basket: Basket, run_date: Optional[date] = None) -> list[SearchRequest]:
    run_date = run_date or date.today()
    reqs = []
    for pair in basket.route_weights:
        parts = pair.split("-")
        origin, destination = parts[0], parts[-1]
        for days in sorted(basket.window_weights):
            reqs.append(SearchRequest(
                route=pair, origin=origin, destination=destination,
                departure_date=run_date + timedelta(days=days), advance_days=days,
            ))
    return reqs


class CollectionRun:
    def __init__(self, basket: Optional[Basket] = None, browser=None,
                 db_path: Optional[str] = None):
        """`db_path` is a DSN: a file path for SQLite, or a Postgres URL.

        Defaults to $DATABASE_URL so a scheduled run writes its quotes into the
        same database the index is rebuilt from. A collector that wrote to a
        local file on an ephemeral CI runner would lose its history every run,
        and a chained index rebuilt from a single day is just the base period
        again — see METHODOLOGY.md §4.
        """
        self.basket = basket or load_basket()
        self.browser = browser
        self.db_path = db_path or os.environ.get("DATABASE_URL") or "data/apix.db"
        self.run_at = datetime.now(timezone.utc)
        self.skipped: list[tuple[str, str]] = []

    def _adapters(self) -> list[BaseAdapter]:
        out = []
        for cfg in load_sources():
            if not cfg.collectable:
                self.skipped.append((cfg.id, f"{cfg.status.value}: {cfg.note}"))
                continue
            cls = ADAPTERS.get(cfg.id)
            if cls is None:
                self.skipped.append((cfg.id, "no adapter implemented"))
                continue
            gate = RobotsGate(user_agent=cfg.user_agent, min_delay_s=cfg.crawl_delay_s)
            limiter = HostLimiter(delay_s=cfg.crawl_delay_s, max_per_hour=cfg.max_rph)
            out.append(cls(cfg, gate, limiter, browser=self.browser))
        return out

    def run(self, run_date: Optional[date] = None) -> dict:
        from ..store import open_store

        reqs = search_requests(self.basket, run_date)
        adapters = self._adapters()
        stats = {"sources": {}, "skipped": dict(self.skipped), "total_quotes": 0,
                 "requests_per_source": len(reqs)}

        with open_store(self.db_path) as store:
            for source_id, reason in self.skipped:
                store.log_collection(self.run_at, source_id, None, "skipped", reason)

            for ad in adapters:
                ok = blocked = failed = 0
                all_quotes: list[RawQuote] = []
                for req in reqs:
                    quotes, outcome = ad.collect(req)
                    all_quotes.extend(quotes)
                    if outcome.ok:
                        ok += 1
                    elif outcome.status == QuoteStatus.BLOCKED_BY_SITE:
                        blocked += 1
                    else:
                        failed += 1
                    store.log_collection(self.run_at, ad.config.id, outcome.url,
                                         "ok" if outcome.ok else outcome.status.value,
                                         outcome.detail,
                                         len([q for q in quotes if q.status == QuoteStatus.OK]))
                    if blocked >= 3:
                        # The site has declined us repeatedly. Stop asking.
                        store.log_collection(self.run_at, ad.config.id, None, "aborted",
                                             "3 consecutive block responses - stopping this source for the run")
                        break
                n = store.insert_raw(all_quotes)
                stats["sources"][ad.config.id] = {
                    "requests_ok": ok, "blocked": blocked, "failed": failed, "rows_written": n,
                    "quotes": len([q for q in all_quotes if q.status == QuoteStatus.OK]),
                }
                stats["total_quotes"] += stats["sources"][ad.config.id]["quotes"]
        return stats


def playwright_browser(headless: bool = True):
    """Context manager yielding a Playwright Chromium browser.

    JavaScript rendering is handled by running a real browser engine, which is
    what the problem statement means by handling JS-rendered pages. It is not
    a stealth browser: no fingerprint patching, no automation-flag hiding.
    """
    from contextlib import contextmanager
    from playwright.sync_api import sync_playwright

    @contextmanager
    def _cm():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                yield browser
            finally:
                browser.close()
    return _cm()
