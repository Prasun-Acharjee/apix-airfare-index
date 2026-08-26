"""Runtime robots.txt gate.

This module is the reason the collector is defensible. Every outbound fetch
passes through `RobotsGate.check`, which fails CLOSED: if we cannot read a
site's robots.txt, or the directive is ambiguous, we do not fetch.

Deliberately absent from this codebase, and not to be added:
  * CAPTCHA solving or CAPTCHA-solving service integration
  * residential/rotating proxy pools used to evade IP-based blocks
  * browser-fingerprint spoofing or stealth plugins
  * retrying a 403 or a bot-challenge response from a different address

A 403, a 429 or an interstitial challenge is the site operator declining our
request. The correct response is to record a non-response and move on; the
index is built to survive that (see apix.index.imputation). Routing around it
would make every number downstream inadmissible as official statistics, which
is the opposite of the point.
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from .rfc9309 import RobotsTxt

log = logging.getLogger(__name__)

ROBOTS_TTL_S = 3600.0
BLOCK_STATUSES = {401, 403, 429}


@dataclass
class RobotsDecision:
    allowed: bool
    reason: str
    crawl_delay_s: Optional[float] = None
    # False when robots.txt could not be read at all. The gate fails closed
    # either way, but the two refusals mean different things: a disallow is the
    # operator's policy, an unreadable file is usually the network between us
    # and them. Only the first should ever fail an audit.
    readable: bool = True

    def __bool__(self) -> bool:
        return self.allowed


@dataclass
class _CachedRobots:
    parser: Optional[RobotsTxt]
    fetched_at: float
    readable: bool
    http_status: Optional[int] = None


@dataclass
class RobotsGate:
    user_agent: str
    min_delay_s: float = 5.0
    _cache: dict[str, _CachedRobots] = field(default_factory=dict)

    def _robots_url(self, url: str) -> tuple[str, str]:
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        return origin, f"{origin}/robots.txt"

    def _fetch(self, origin: str, robots_url: str) -> _CachedRobots:
        cached = self._cache.get(origin)
        if cached and (time.time() - cached.fetched_at) < ROBOTS_TTL_S:
            return cached
        req = urllib.request.Request(robots_url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            entry = _CachedRobots(RobotsTxt(body), time.time(), readable=True, http_status=200)
        except urllib.error.HTTPError as e:
            # RFC 9309 treats 4xx as "no restrictions". We do not. A 403 on
            # robots.txt is an operator actively refusing an automated client,
            # and 404 leaves us unable to demonstrate permission for an index
            # that has to be auditable. Fail closed either way.
            entry = _CachedRobots(None, time.time(), readable=False, http_status=e.code)
            log.warning("robots.txt for %s returned HTTP %s - treating as disallowed", origin, e.code)
        except Exception as e:  # network error, TLS failure, timeout
            entry = _CachedRobots(None, time.time(), readable=False, http_status=None)
            log.warning("robots.txt for %s unreadable (%s) - treating as disallowed", origin, e)
        self._cache[origin] = entry
        return entry

    def check(self, url: str) -> RobotsDecision:
        origin, robots_url = self._robots_url(url)
        entry = self._fetch(origin, robots_url)
        if not entry.readable or entry.parser is None:
            return RobotsDecision(
                False,
                f"robots.txt unreadable for {origin}"
                + (f" (HTTP {entry.http_status})" if entry.http_status else "")
                + " - failing closed",
                readable=False,
            )
        if not entry.parser.can_fetch(self.user_agent, url):
            return RobotsDecision(False, f"robots.txt disallows {url} for {self.user_agent}")
        declared = entry.parser.crawl_delay(self.user_agent)
        delay = max(self.min_delay_s, float(declared) if declared else 0.0)
        return RobotsDecision(True, "allowed by robots.txt", crawl_delay_s=delay)


def is_block_response(status_code: int) -> bool:
    """True when a response is the site declining us. Never retried or evaded."""
    return status_code in BLOCK_STATUSES


def gate_from_body(user_agent: str, origin: str, body: str, min_delay_s: float = 5.0) -> RobotsGate:
    """Build a gate pre-seeded with a known robots.txt body.

    Used by the test suite, and by `scripts/audit_robots.py` when the collector
    host cannot reach the origin directly but the body has been captured.
    """
    g = RobotsGate(user_agent=user_agent, min_delay_s=min_delay_s)
    g._cache[origin] = _CachedRobots(RobotsTxt(body), time.time(), readable=True, http_status=200)
    return g
