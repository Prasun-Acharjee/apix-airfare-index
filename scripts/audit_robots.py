#!/usr/bin/env python3
"""Re-run the robots.txt compliance audit and print a table.

Run this before enabling any source, and periodically thereafter — a site can
change its crawl policy at any time, and `config/sources.yaml` is documentation
of a point-in-time audit, not a live authority. The runtime gate in
`apix.compliance.robots` is the authority.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apix.compliance.robots import RobotsGate
from apix.config import load_sources


def main() -> int:
    print(f"{'source':20s} {'configured':22s} {'live gate':10s}  detail")
    print("-" * 100)
    mismatches = 0
    for s in load_sources():
        url = s.base_url + s.search_path_template
        gate = RobotsGate(user_agent=s.user_agent, min_delay_s=s.crawl_delay_s)
        d = gate.check(url)
        live = "ALLOW" if d.allowed else "BLOCK"
        expected = "ALLOW" if s.status.collectable else "BLOCK"
        flag = "" if live == expected else "  <-- MISMATCH vs sources.yaml"
        if flag:
            mismatches += 1
        print(f"{s.id:20s} {s.status.value:22s} {live:10s}  {d.reason[:60]}{flag}")
    if mismatches:
        print(f"\n{mismatches} source(s) disagree with the audit in config/sources.yaml. "
              "Update it before collecting.")
    else:
        print("\nAll sources agree with the recorded audit.")
    print("\nNote: a BLOCK here may mean the host is unreachable from this machine "
          "(the gate fails closed on any unreadable robots.txt), not that the site "
          "disallows it. Check the detail column.")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
