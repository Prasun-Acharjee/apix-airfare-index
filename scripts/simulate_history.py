#!/usr/bin/env python3
"""Populate data/apix.db with a SYNTHETIC history so the API and dashboard have
something to serve. Run `scripts/run_collection.py` for real collection."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apix.collect.simulator import generate
from apix.config import load_basket
from apix.pipeline import run_and_store


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--start", default="2026-04-01")
    ap.add_argument("--db", default="data/apix.db")
    ap.add_argument("--shock", default="2026-06-15", help="date of a simulated fuel-price shock, or 'none'")
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    shock = None if args.shock == "none" else date.fromisoformat(args.shock)

    print(f"Generating {args.days} days of SYNTHETIC quotes from {start}"
          + (f" with a +12% shock on {shock}" if shock else ""))
    quotes = list(generate(load_basket(), start=start, days=args.days, fuel_shock_on=shock))
    print(f"  {len(quotes):,} raw quotes")

    out = run_and_store(quotes, db_path=args.db)
    print(f"  QC: {out['qc']}")
    print(f"  index points: {out['points']}")
    p = out["latest"]
    if p:
        print(f"  latest daily: {p.on_date} = {p.value:.2f} "
              f"(coverage {p.coverage:.1%}, imputed {p.imputation_share:.1%}, {p.quality})")
    print(f"\n  Written to {args.db}. THIS IS SYNTHETIC DATA - not a published statistic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
