#!/usr/bin/env python3
"""Build the index and load it into Postgres for the website to serve.

    export DATABASE_URL="postgresql://..."
    python scripts/seed_postgres.py --days 120          # synthetic demo data
    python scripts/seed_postgres.py --from-postgres     # rebuild from collected history
    python scripts/seed_postgres.py --from-sqlite data/apix.db   # from a local archive

The index is CHAINED, so a rebuild reads the whole accumulated quote history, not
just the latest collection. `--from-postgres` refuses to run on fewer than two
collection days rather than republishing the base period over a real series.

Synthetic runs write source ids prefixed `sim_`, which the website detects and
banners. There is no flag to suppress that banner.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apix.collect.simulator import generate
from apix.config import load_basket, load_sources
from apix.models import QuoteStatus, RawQuote
from apix.pipeline import build_index
from apix.store import PostgresStore, open_store


def from_sqlite(path: str) -> list[RawQuote]:
    from apix.db import connect
    out: list[RawQuote] = []
    with connect(path) as conn:
        for r in conn.execute("SELECT * FROM raw_quote WHERE status='ok' ORDER BY collected_on"):
            out.append(RawQuote(
                source_id=r["source_id"], collected_at=datetime.fromisoformat(r["collected_at"]),
                route=r["route"], origin=r["origin"], destination=r["destination"],
                departure_date=date.fromisoformat(r["departure_date"]),
                advance_days=r["advance_days"], carrier=r["carrier"],
                flight_number=r["flight_number"], cabin=r["cabin"] or "ECONOMY",
                fare_family=r["fare_family"], total_inr=r["total_inr"], base_inr=r["base_inr"],
                taxes_inr=r["taxes_inr"], surcharges_inr=r["surcharges_inr"],
                currency=r["currency"] or "INR", stops=r["stops"], status=QuoteStatus.OK,
                raw_payload=json.loads(r["raw_payload"] or "{}"),
            ))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=120, help="days of synthetic history")
    ap.add_argument("--start", default="2026-04-01")
    ap.add_argument("--shock", default="2026-06-15", help="simulated fuel shock date, or 'none'")
    ap.add_argument("--from-sqlite", default=None,
                    help="rebuild from a local SQLite quote archive")
    ap.add_argument("--from-postgres", action="store_true",
                    help="rebuild from the raw quotes already accumulated in Postgres "
                         "(this is what a scheduled run should use)")
    ap.add_argument("--dsn", default=None, help="defaults to $DATABASE_URL")
    ap.add_argument("--keep-raw", action="store_true",
                    help="also write every raw quote (large; off by default)")
    args = ap.parse_args()

    dsn = args.dsn or os.environ.get("DATABASE_URL")
    if not dsn or not dsn.startswith(("postgres://", "postgresql://")):
        print("ERROR: set DATABASE_URL to a Postgres connection string.", file=sys.stderr)
        return 2

    basket = load_basket()
    store = PostgresStore(dsn)
    store.migrate()

    if args.from_postgres:
        raws = store.load_raw()
        print(f"Loaded {len(raws):,} accumulated quotes from Postgres")
        if not raws:
            print("ERROR: no usable raw quotes in the database. Run the collector first.",
                  file=sys.stderr)
            store.close()
            return 2
        days = len({r.collected_at.date() for r in raws})
        if days < 2:
            # A chained index needs two periods to form its first link. Rebuilding
            # from one day would republish the base period and silently wipe the
            # existing series.
            print(f"ERROR: only {days} collection day(s) present. A chained index needs at "
                  "least 2 to form a link; refusing to overwrite the published series.",
                  file=sys.stderr)
            store.close()
            return 3
        print(f"  spanning {days} collection days")
    elif args.from_sqlite:
        raws = from_sqlite(args.from_sqlite)
        print(f"Loaded {len(raws):,} collected quotes from {args.from_sqlite}")
    else:
        shock = None if args.shock == "none" else date.fromisoformat(args.shock)
        print(f"Generating {args.days} days of SYNTHETIC quotes from {args.start}"
              + (f", +12% shock on {shock}" if shock else ""))
        raws = list(generate(basket, start=date.fromisoformat(args.start),
                             days=args.days, fuel_shock_on=shock))
        print(f"  {len(raws):,} raw quotes")

    result = build_index(raws, basket)
    print(f"  QC: {result['qc']}")

    store.sync_sources(load_sources(), datetime.now(timezone.utc))
    store.sync_basket(basket)
    n_cells = store.upsert_cell_prices(result["cell_prices"])
    n_pts = sum(store.upsert_index(result[f]) for f in ("daily", "weekly", "monthly"))
    if args.keep_raw and not args.from_postgres:
        n_raw = store.insert_raw(r for r in raws if r.status == QuoteStatus.OK)
        print(f"  raw quotes written: {n_raw:,}")
    store.close()

    print(f"  cell prices: {n_cells:,}   index points: {n_pts}")
    last = result["daily"][-1] if result["daily"] else None
    if last:
        print(f"  latest daily: {last.on_date} = {last.value:.2f} "
              f"(coverage {last.coverage:.1%}, imputed {last.imputation_share:.1%}, {last.quality})")
    if not args.from_sqlite and not args.from_postgres:
        print("\n  SYNTHETIC DATA — the site will display a banner saying so.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
