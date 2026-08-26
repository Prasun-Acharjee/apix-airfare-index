"""The compliance gate is the load-bearing claim of this project. Test it hard."""
from __future__ import annotations

from pathlib import Path

import pytest

from apix.compliance.ratelimit import HostLimiter
from apix.compliance.rfc9309 import RobotsTxt
from apix.compliance.robots import RobotsGate, gate_from_body, is_block_response

FIX = Path(__file__).parent / "fixtures"
UA = "APIx-ResearchBot/0.1"


def rt(name: str) -> RobotsTxt:
    return RobotsTxt((FIX / f"robots_{name}.txt").read_text())


@pytest.mark.parametrize("name,url,allowed", [
    # The two cases the stdlib parser gets WRONG, in the permissive direction.
    ("indigo",    "https://www.goindigo.in/booking/select-flight",   False),  # wildcard
    ("spicejet",  "https://www.spicejet.com/api/v1/search",          False),  # full-URL directive
    # Everything else.
    ("indigo",    "https://www.goindigo.in/book/anything",           False),
    ("indigo",    "https://www.goindigo.in/about-us/awards",         True),
    ("airindia",  "https://www.airindia.com/in/en/book/flight-search.html", True),
    ("airindia",  "https://www.airindia.com/bin/api",                False),
    ("spicejet",  "https://www.spicejet.com/",                       True),
    ("spicejet",  "https://www.spicejet.com/public/x",               False),
    ("aiexpress", "https://www.airindiaexpress.com/flight-availability", False),
    ("aiexpress", "https://www.airindiaexpress.com/about",           True),
    ("yatra",     "https://www.yatra.com/flights/search",            True),
    ("yatra",     "https://www.yatra.com/travel-beta/cheap-air-tickets", False),
])
def test_directives_are_matched_correctly(name, url, allowed):
    assert rt(name).can_fetch(UA, url) is allowed


def test_stdlib_parser_would_have_been_wrong():
    """Regression guard documenting exactly why we do not use urllib.robotparser."""
    from urllib.robotparser import RobotFileParser
    for name, url in [("indigo", "https://www.goindigo.in/booking/select-flight"),
                      ("spicejet", "https://www.spicejet.com/api/v1/search")]:
        stdlib = RobotFileParser()
        stdlib.parse((FIX / f"robots_{name}.txt").read_text().splitlines())
        assert stdlib.can_fetch(UA, url) is True, "stdlib behaviour changed - re-evaluate"
        assert rt(name).can_fetch(UA, url) is False, "our matcher must still block it"


def test_named_agent_group_wins_over_wildcard_group():
    r = rt("yatra")
    assert r.crawl_delay("ClaudeBot") == 5.0
    assert r.crawl_delay(UA) is None


def test_end_anchor_and_wildcards():
    r = RobotsTxt("User-agent: *\nDisallow: /*.pdf$\nDisallow: /a/*/b\nAllow: /a/x/b/keep\n")
    assert r.can_fetch(UA, "https://h/doc.pdf") is False
    assert r.can_fetch(UA, "https://h/doc.pdf?x=1") is True   # $ anchors the end
    assert r.can_fetch(UA, "https://h/a/x/b") is False
    assert r.can_fetch(UA, "https://h/a/x/b/keep") is True    # longer Allow wins
    assert r.can_fetch(UA, "https://h/a/b") is True


def test_allow_wins_equal_length_tie():
    r = RobotsTxt("User-agent: *\nDisallow: /x\nAllow: /x\n")
    assert r.can_fetch(UA, "https://h/x") is True


def test_empty_disallow_means_allow_all():
    r = RobotsTxt("User-agent: *\nDisallow:\n")
    assert r.can_fetch(UA, "https://h/anything") is True


# --- fail-closed behaviour -------------------------------------------------

def _gate_with_status(status):
    import urllib.error
    g = RobotsGate(user_agent=UA)
    def boom(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, status, "no", {}, None)
    import apix.compliance.robots as mod
    mod.urllib.request.urlopen = boom
    return g


@pytest.mark.parametrize("status", [403, 404, 401, 500])
def test_unreadable_robots_fails_closed(status, monkeypatch):
    """RFC 9309 says 4xx means 'crawl freely'. For an official statistic it must not."""
    import urllib.error
    import apix.compliance.robots as mod
    def boom(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, status, "no", {}, None)
    monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
    g = RobotsGate(user_agent=UA)
    d = g.check("https://www.akasaair.com/search")
    assert d.allowed is False
    assert "failing closed" in d.reason


def test_network_error_fails_closed(monkeypatch):
    import apix.compliance.robots as mod
    def boom(req, timeout=0):
        raise TimeoutError("read timeout")
    monkeypatch.setattr(mod.urllib.request, "urlopen", boom)
    assert RobotsGate(user_agent=UA).check("https://www.makemytrip.com/flight/search").allowed is False


def test_gate_applies_delay_floor_and_respects_larger_declared_delay():
    g = gate_from_body(UA, "https://h", "User-agent: *\nCrawl-delay: 20\nAllow: /\n", min_delay_s=5.0)
    assert g.check("https://h/x").crawl_delay_s == 20.0
    g2 = gate_from_body(UA, "https://h", "User-agent: *\nAllow: /\n", min_delay_s=5.0)
    assert g2.check("https://h/x").crawl_delay_s == 5.0


def test_block_statuses_are_recognised():
    assert is_block_response(403) and is_block_response(429) and is_block_response(401)
    assert not is_block_response(200) and not is_block_response(500)


# --- rate limiting ---------------------------------------------------------

def test_limiter_spaces_requests_by_crawl_delay():
    clock = {"t": 0.0}
    slept: list[float] = []
    def now(): return clock["t"]
    def sleep(s):
        slept.append(s); clock["t"] += s
    lim = HostLimiter(delay_s=5.0, max_per_hour=1000)
    for _ in range(4):
        lim.acquire("h", sleep=sleep, now=now)
    assert slept == pytest.approx([5.0, 5.0, 5.0])


def test_limiter_enforces_hourly_ceiling():
    clock = {"t": 0.0}
    def now(): return clock["t"]
    def sleep(s): clock["t"] += s
    lim = HostLimiter(delay_s=0.0, max_per_hour=3)
    for _ in range(3):
        lim.acquire("h", sleep=sleep, now=now)
    assert clock["t"] == 0.0
    lim.acquire("h", sleep=sleep, now=now)
    assert clock["t"] > 3599.0, "fourth request in the hour must wait out the window"


# --- config-level guarantees ----------------------------------------------

def test_no_blocked_source_is_marked_collectable():
    from apix.config import load_sources
    for s in load_sources():
        if s.status.value.startswith("blocked"):
            assert not s.collectable, f"{s.id} is blocked but marked collectable"


def test_codebase_contains_no_evasion_machinery():
    """Guard against someone 'fixing' coverage by adding what we refused to add."""
    import re
    root = Path(__file__).resolve().parent.parent / "apix"
    banned = re.compile(
        r"(2captcha|anticaptcha|capsolver|deathbycaptcha|solve_captcha|"
        r"playwright_stealth|puppeteer[-_]extra|undetected_chromedriver|"
        r"rotate_proxy|proxy_pool|residential_proxy)", re.I)
    hits = []
    for p in root.rglob("*.py"):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if line.strip().startswith("#") or '"""' in line:
                continue
            if banned.search(line):
                hits.append(f"{p.relative_to(root)}:{i}: {line.strip()}")
    assert not hits, "evasion machinery found:\n" + "\n".join(hits)


# --- audit severity: only one disagreement may stop a scheduled run --------

def test_disallow_and_unreachable_are_distinguishable(monkeypatch):
    """The gate refuses both, but an audit must treat them differently.

    A disallow is the operator's policy. An unreadable robots.txt is usually
    the network between us and the host. Failing a nightly run on the second
    takes down collection for every other source for no compliance reason.
    """
    disallowed = gate_from_body(UA, "https://h", "User-agent: *\nDisallow: /fares\n")
    d = disallowed.check("https://h/fares")
    assert d.allowed is False and d.readable is True

    import urllib.error
    import apix.compliance.robots as mod
    monkeypatch.setattr(mod.urllib.request, "urlopen",
                        lambda req, timeout=0: (_ for _ in ()).throw(TimeoutError("x")))
    u = RobotsGate(user_agent=UA).check("https://unreachable.example/fares")
    assert u.allowed is False and u.readable is False


def test_audit_fails_only_when_a_collectable_source_is_disallowed(monkeypatch):
    """scripts/audit_robots.py exit code contract, exercised without the network."""
    import apix.compliance.robots as mod
    from apix.config import load_sources
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "audit_robots", Path(__file__).resolve().parent.parent / "scripts" / "audit_robots.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)

    collectable = next(s for s in load_sources() if s.status.collectable)

    def gate_returning(decision):
        class G:
            def __init__(self, **kw): pass
            def check(self, url): return decision
        return G

    # Unreachable everywhere -> warn, but the run proceeds.
    monkeypatch.setattr(audit, "RobotsGate", gate_returning(
        mod.RobotsDecision(False, "unreadable - failing closed", readable=False)))
    assert audit.main() == 0, "an unreadable robots.txt must not stop collection"

    # Actively disallowed while we intend to collect -> stop.
    monkeypatch.setattr(audit, "RobotsGate", gate_returning(
        mod.RobotsDecision(False, "robots.txt disallows it", readable=True)))
    assert audit.main() == 1, f"{collectable.id} is collectable but disallowed; must exit 1"

    # Permitted everywhere -> clean.
    monkeypatch.setattr(audit, "RobotsGate", gate_returning(
        mod.RobotsDecision(True, "allowed by robots.txt", crawl_delay_s=5.0)))
    assert audit.main() == 0
