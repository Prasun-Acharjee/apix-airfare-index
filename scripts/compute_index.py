#!/usr/bin/env python3
"""Rebuild the index from raw quotes already stored in the database."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apix.db import connect
from apix.models import QuoteStatus, RawQuote
from apix.pipeline import run_and_store


def load_raw(db_path: str) -> list[RawQuote]:
    out = []
    with connect(db_path) as conn:
        for r in conn.execute("SELECT * FROM raw_quote WHERE status='ok' ORDER BY collected_on"):
            out.append(RawQuote(
                source_id=r["source_id"],
                collected_at=datetime.fromisoformat(r["collected_at"]),
                route=r["route"], origin=r["origin"], destination=r["destination"],
                departure_date=date.fromisoformat(r["departure_date"]),
                advance_days=r["advance_days"], carrier=r["carrier"],
                flight_number=r["flight_number"], cabin=r["cabin"] or "ECONOMY",
                fare_family=r["fare_family"], total_inr=r["total_inr"],
                base_inr=r["base_inr"], taxes_inr=r["taxes_inr"],
                surcharges_inr=r["surcharges_inr"], currency=r["currency"] or "INR",
                stops=r["stops"], status=QuoteStatus.OK,
                raw_payload=json.loads(r["raw_payload"] or "{}"),
            ))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data/apix.db")
    ap.add_argument("--price-concept", choices=["all_in", "ex_tax"], default="all_in")
    args = ap.parse_args()

    raws = load_raw(args.db)
    print(f"Loaded {len(raws):,} usable raw quotes from {args.db}")
    if not raws:
        print("Nothing to compute. Run scripts/run_collection.py or scripts/simulate_history.py first.")
        return 1
    out = run_and_store(raws, db_path=args.db)
    print(f"  QC: {out['qc']}")
    print(f"  index points: {out['points']}")
    p = out["latest"]
    if p:
        print(f"  latest daily: {p.on_date} = {p.value:.2f} "
              f"(coverage {p.coverage:.1%}, imputed {p.imputation_share:.1%}, {p.quality})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
