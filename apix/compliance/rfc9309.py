"""A robots.txt matcher that implements RFC 9309, because the stdlib one does not.

`urllib.robotparser.RobotFileParser` matches rules with a plain
`path.startswith(rule)`. That silently mis-handles two constructs that appear
in the robots.txt of the sites this project targets:

  1. Wildcards.  IndiGo publishes `Disallow: /booking/*`. The stdlib parser
     looks for a path literally beginning `/booking/*`, finds none, and reports
     the entire booking tree as ALLOWED. It is disallowed.

  2. Full-URL directives.  SpiceJet publishes
     `Disallow: https://www.spicejet.com/api/v1`. The stdlib parser compares it
     against the request path `/api/v1/...`, which does not start with `https:`,
     and reports the fare API as ALLOWED. It is disallowed.

Both failures are in the permissive direction, which is the dangerous one: a
collector built on the stdlib parser would believe it had permission it did not
have. This module implements the RFC's semantics: `*` wildcards, `$` end-anchor,
longest-match-wins with allow winning ties, and user-agent group selection by
longest matching prefix with `*` as the fallback group.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import unquote, urlparse


@dataclass
class Rule:
    allow: bool
    pattern: str
    regex: re.Pattern
    length: int


@dataclass
class Group:
    agents: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    crawl_delay: Optional[float] = None


def _to_path(value: str) -> str:
    """Normalise a directive value to a path, tolerating full-URL directives."""
    value = value.strip()
    if not value:
        return value
    if value.lower().startswith(("http://", "https://")):
        p = urlparse(value)
        value = p.path or "/"
        if p.query:
            value += "?" + p.query
    if not value.startswith("/") and not value.startswith("*"):
        value = "/" + value
    return value


def _compile(pattern: str) -> re.Pattern:
    """RFC 9309 path pattern -> regex. `*` = any run, `$` at end = anchor."""
    anchored_end = pattern.endswith("$")
    body = pattern[:-1] if anchored_end else pattern
    parts = body.split("*")
    rx = ".*".join(re.escape(p) for p in parts)
    return re.compile("^" + rx + ("$" if anchored_end else ""))


class RobotsTxt:
    def __init__(self, body: str):
        self.groups: list[Group] = []
        self.sitemaps: list[str] = []
        self._parse(body)

    def _parse(self, body: str) -> None:
        current: Optional[Group] = None
        expecting_agent = False
        for raw in body.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            field_name, _, value = line.partition(":")
            field_name = field_name.strip().lower()
            value = value.strip()

            if field_name == "user-agent":
                if current is None or not expecting_agent:
                    current = Group()
                    self.groups.append(current)
                    expecting_agent = True
                current.agents.append(value.lower())
                continue

            if field_name == "sitemap":
                self.sitemaps.append(value)
                continue

            if current is None:
                continue
            expecting_agent = False

            if field_name in ("allow", "disallow"):
                if field_name == "disallow" and value == "":
                    continue  # "Disallow:" with empty value means allow all
                path = _to_path(value)
                if not path:
                    continue
                current.rules.append(
                    Rule(allow=(field_name == "allow"), pattern=path,
                         regex=_compile(path), length=len(path))
                )
            elif field_name == "crawl-delay":
                try:
                    current.crawl_delay = float(value)
                except ValueError:
                    pass

    def _group_for(self, user_agent: str) -> Optional[Group]:
        """Longest matching user-agent token wins; `*` is the fallback group."""
        ua = user_agent.lower()
        best: Optional[Group] = None
        best_len = -1
        fallback: Optional[Group] = None
        for g in self.groups:
            for token in g.agents:
                if token == "*":
                    if fallback is None:
                        fallback = g
                    continue
                if token and token in ua and len(token) > best_len:
                    best, best_len = g, len(token)
        return best or fallback

    def can_fetch(self, user_agent: str, url: str) -> bool:
        group = self._group_for(user_agent)
        if group is None:
            return True
        p = urlparse(url)
        path = unquote(p.path or "/")
        if p.query:
            path += "?" + p.query

        winner: Optional[Rule] = None
        for rule in group.rules:
            if rule.regex.match(path):
                if winner is None or rule.length > winner.length:
                    winner = rule
                elif rule.length == winner.length and rule.allow:
                    winner = rule  # allow wins ties (RFC 9309 s2.2.2)
        return True if winner is None else winner.allow

    def crawl_delay(self, user_agent: str) -> Optional[float]:
        group = self._group_for(user_agent)
        return group.crawl_delay if group else None
