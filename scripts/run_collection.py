#!/usr/bin/env python3
"""Run one live collection pass against the permitted sources only.

Every request passes the robots.txt gate. Sources whose audit status is not
`permitted` are skipped and the skip is logged with its reason. A site that
declines us (403/429/challenge) is recorded as a non-response; nothing is
retried from a different address and no challenge is solved.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apix.collect.runner import CollectionRun, playwright_browser
from apix.config import load_basket


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/apix.db")
    ap.add_argument("--date", default=None, help="collection date (default today)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    run_date = date.fromisoformat(args.date) if args.date else date.today()

    with playwright_browser(headless=not args.headed) as browser:
        run = CollectionRun(load_basket(), browser=browser, db_path=args.db)
        stats = run.run(run_date)

    print(f"\nCollection {run.run_at.isoformat(timespec='seconds')}  ({stats['requests_per_source']} requests/source)")
    for sid, s in stats["sources"].items():
        print(f"  {sid:20s} ok={s['requests_ok']:3d} blocked={s['blocked']:3d} "
              f"failed={s['failed']:3d} quotes={s['quotes']:5d}")
    if stats["skipped"]:
        print("\n  Skipped (not collectable):")
        for sid, why in stats["skipped"].items():
            print(f"    {sid:20s} {why[:110]}")
    print(f"\n  Total quotes: {stats['total_quotes']:,}")
    print("  Run scripts/compute_index.py to rebuild the index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
