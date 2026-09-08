#!/usr/bin/env python3
"""Can this machine read each source's robots.txt? Run it before moving the collector.

    python scripts/check_reachability.py
    python scripts/check_reachability.py --only air_india,yatra --attempts 5

The collector fails closed: a source whose robots.txt it cannot read produces
zero quotes, whatever the site's actual policy is. That failure is a property of
the NETWORK the collector runs on, not of the code, so the only way to know
whether a candidate host will work is to ask from that host.

This is the qualifying test for a new runner. It fetches robots.txt and nothing
else - no fare pages, no search requests - so it is safe to run repeatedly from
anywhere, and it makes exactly the same request the gate makes: same user agent,
same timeout, same retry count.

Exit codes:
  0  every source checked was readable
  1  at least one source was unreadable from here
  2  bad arguments

Reading the output. `refused` is the operator answering - a 403 or a 429 means
that site declines automated clients and no amount of moving hosts will change
it. `unreachable` is the network between here and them, and is the case worth
retesting elsewhere. A host where the sources you need come back `readable` is a
host the collector will work from.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apix.compliance.robots import (
    BLOCK_STATUSES,
    ROBOTS_RETRY_BACKOFF_S,
    ROBOTS_TIMEOUT_S,
    ROBOTS_TRANSIENT_ATTEMPTS,
)
from apix.config import load_sources


def probe(origin: str, user_agent: str, attempts: int) -> tuple[str, str]:
    """Return (verdict, detail). Same request shape as RobotsGate._fetch."""
    url = f"{origin}/robots.txt"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=ROBOTS_TIMEOUT_S) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            lines = len([ln for ln in body.splitlines() if ln.strip()])
            return "readable", f"HTTP 200, {len(body):,} bytes, {lines} directives"
        except urllib.error.HTTPError as e:
            # An answer, not a network problem. Never retried - retrying a
            # refusal is the evasion this project does not do.
            kind = "refused" if e.code in BLOCK_STATUSES else "unreadable"
            return kind, f"HTTP {e.code} - moving hosts will not change this"
        except Exception as e:
            waited = time.monotonic() - started
            if attempt < attempts:
                time.sleep(ROBOTS_RETRY_BACKOFF_S * attempt)
                continue
            return "unreachable", f"{type(e).__name__} after {attempt} attempts ({waited:.0f}s each): {e}"
    return "unreachable", "no attempts made"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default=None,
                    help="comma-separated source ids (default: every enabled source)")
    ap.add_argument("--attempts", type=int, default=ROBOTS_TRANSIENT_ATTEMPTS,
                    help=f"attempts per source before calling it unreachable "
                         f"(default {ROBOTS_TRANSIENT_ATTEMPTS}, matching the gate)")
    args = ap.parse_args()

    if args.attempts < 1:
        print("ERROR: --attempts must be at least 1", file=sys.stderr)
        return 2

    sources = [s for s in load_sources() if s.enabled]
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        known = {s.id for s in load_sources()}
        unknown = sorted(wanted - known)
        if unknown:
            print(f"ERROR: unknown source id(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
        sources = [s for s in load_sources() if s.id in wanted]
    if not sources:
        print("ERROR: no sources selected.", file=sys.stderr)
        return 2

    print(f"Probing robots.txt only, {args.attempts} attempt(s) each, "
          f"{ROBOTS_TIMEOUT_S:.0f}s timeout.\n")
    print(f"{'source':20s} {'verdict':12s} detail")
    print("-" * 100)

    unreadable = []
    for cfg in sources:
        p = urlparse(cfg.base_url)
        origin = f"{p.scheme}://{p.netloc}"
        verdict, detail = probe(origin, cfg.user_agent, args.attempts)
        print(f"{cfg.id:20s} {verdict:12s} {detail[:66]}")
        if verdict != "readable":
            unreadable.append((cfg.id, verdict))

    if not unreadable:
        print(f"\nAll {len(sources)} source(s) readable from this host. "
              f"The collector will not fail closed on any of them here.")
        return 0

    print(f"\n{len(unreadable)} of {len(sources)} source(s) not readable from this host:")
    for sid, verdict in unreadable:
        print(f"  {sid:20s} {verdict}")
    if any(v == "unreachable" for _, v in unreadable):
        print("\n  `unreachable` is the network, not the site's policy. Try another\n"
              "  host - see DEPLOY.md, \"Runner network\".")
    if any(v == "refused" for _, v in unreadable):
        print("\n  `refused` is the operator declining automated clients. That is an\n"
              "  answer, and it is the same answer from anywhere. Leave it alone.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
