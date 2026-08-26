#!/usr/bin/env python3
"""Re-run the robots.txt compliance audit and print a table.

Run this before enabling any source, and periodically thereafter — a site can
change its crawl policy at any time, and `config/sources.yaml` is documentation
of a point-in-time audit, not a live authority. The runtime gate in
`apix.compliance.robots` is the authority.

EXIT CODE. This is a canary, not the guard: `RobotsGate.check` runs on every
single request and fails closed, so the collector cannot fetch a disallowed URL
however stale this file gets. Accordingly only ONE disagreement is worth
stopping a scheduled run for:

  UNSAFE   we intend to collect, and robots.txt actively disallows the path.
           Exit 1. Fix the config before collecting.
  UNREACH  we intend to collect, but robots.txt could not be read at all.
           Usually the network between us and the host, not a policy. The gate
           refuses these requests at runtime and records them as absences,
           which is the designed behaviour. Warn, exit 0.
  INFO     robots.txt permits a source we have chosen NOT to collect (no
           adapter, terms of use, commercial feed required). Being more
           conservative than robots requires is not a compliance risk.

Failing the run on INFO — which this script used to do — took the whole nightly
collection down because a source we deliberately do not scrape became MORE
permissive. That is backwards.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apix.compliance.robots import RobotsGate
from apix.config import load_sources


def main() -> int:
    print(f"{'source':20s} {'configured':22s} {'live gate':10s} {'verdict':8s}  detail")
    print("-" * 108)
    unsafe: list[str] = []
    unreachable: list[str] = []
    info: list[str] = []

    for s in load_sources():
        url = s.base_url + s.search_path_template
        gate = RobotsGate(user_agent=s.user_agent, min_delay_s=s.crawl_delay_s)
        d = gate.check(url)
        live = "ALLOW" if d.allowed else "BLOCK"
        intend_to_collect = s.status.collectable

        if intend_to_collect and not d.allowed:
            if d.readable:
                verdict = "UNSAFE"
                unsafe.append(s.id)
            else:
                verdict = "UNREACH"
                unreachable.append(s.id)
        elif not intend_to_collect and d.allowed:
            verdict = "INFO"
            info.append(s.id)
        else:
            verdict = "OK"

        print(f"{s.id:20s} {s.status.value:22s} {live:10s} {verdict:8s}  {d.reason[:56]}")

    print()
    if unsafe:
        print(f"FAIL: {len(unsafe)} source(s) marked collectable but DISALLOWED by robots.txt: "
              f"{', '.join(unsafe)}")
        print("      Fix config/sources.yaml before collecting. Refusing to proceed.")
    if unreachable:
        print(f"WARN: robots.txt unreadable for {', '.join(unreachable)} — cannot confirm policy "
              "from this host.")
        print("      The runtime gate refuses these requests and records non-responses; "
              "collection continues for every other source.")
    if info:
        print(f"INFO: robots.txt permits {', '.join(info)}, which we do not collect "
              "(no adapter / terms / commercial feed). More conservative than required.")
    if not (unsafe or unreachable or info):
        print("All sources agree with the recorded audit.")
    return 1 if unsafe else 0


if __name__ == "__main__":
    raise SystemExit(main())
