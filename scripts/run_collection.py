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
from apix.store import is_postgres_dsn


def describe_target(dsn: str) -> str:
    """Where the quotes went, with any Postgres credentials stripped."""
    if not is_postgres_dsn(dsn):
        return f"SQLite {dsn}"
    rest = dsn.split("://", 1)[1]
    return f"Postgres {rest.rsplit('@', 1)[-1] if '@' in rest else rest}"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    # Deliberately None, not a file path: CollectionRun resolves an unset DSN to
    # $DATABASE_URL and only then to local SQLite. Defaulting to a path here
    # would shadow that and send a scheduled run's quotes to the runner's disk,
    # which is discarded when the job ends.
    ap.add_argument("--db", default=None,
                    help="DSN to write to: a Postgres URL or a SQLite file path. "
                         "Defaults to $DATABASE_URL, then data/apix.db")
    ap.add_argument("--date", default=None, help="collection date (default today)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    run_date = date.fromisoformat(args.date) if args.date else date.today()

    with playwright_browser(headless=not args.headed) as browser:
        run = CollectionRun(load_basket(), browser=browser, db_path=args.db)
        stats = run.run(run_date)

    print(f"\nCollection {run.run_at.isoformat(timespec='seconds')}  ({stats['requests_per_source']} requests/source)")
    for sid, s in stats["sources"].items():
        print(f"  {sid:20s} ok={s['requests_ok']:3d} blocked={s['blocked']:3d} "
              f"failed={s['failed']:3d} quotes={s['quotes']:5d} written={s['rows_written']:5d}")
    if stats["skipped"]:
        print("\n  Skipped (not collectable):")
        for sid, why in stats["skipped"].items():
            print(f"    {sid:20s} {why[:110]}")

    # Name the destination. A run that quietly wrote to the runner's local disk
    # instead of the shared database looks identical in every other line of this
    # report, and only surfaces days later as a chained index that will not build.
    written = sum(s["rows_written"] for s in stats["sources"].values())
    print(f"\n  Total quotes: {stats['total_quotes']:,}")
    print(f"  Rows written: {written:,} -> {describe_target(run.db_path)}")
    if not stats["total_quotes"]:
        # Fail here. Exiting 0 on an empty pass lets the rebuild step inherit an
        # unchanged database and report the shortfall as its own problem, two
        # steps from the cause.
        print("ERROR: every source returned nothing. Not a successful pass.",
              file=sys.stderr)
        return 1
    if is_postgres_dsn(run.db_path):
        print("  Rebuild with scripts/seed_postgres.py --from-postgres.")
    else:
        print("  Local archive: this history is lost if the filesystem is ephemeral.")
        print("  Run scripts/compute_index.py to rebuild the index.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
