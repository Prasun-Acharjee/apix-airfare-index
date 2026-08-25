"""Storage backends.

SQLite for local runs and tests; Postgres for anything the website reads. The
choice is made by the DSN, so nothing above this module knows or cares which is
in use:

    open_store("data/apix.db")                    -> SQLite
    open_store(os.environ["DATABASE_URL"])        -> Postgres

The schema is defined once, in `db/migrations/001_init.sql`. Postgres applies
that file verbatim; the SQLite path in `apix.db` mirrors it. Neither the
collector nor the index worker writes DDL at runtime against Postgres — a
migration is an explicit, reviewable step.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from .config import Basket, SourceConfig, load_basket, load_sources
from .models import Cell, CellPrice, IndexPoint, RawQuote

MIGRATION = Path(__file__).resolve().parent.parent / "db" / "migrations" / "001_init.sql"


def is_postgres_dsn(dsn: str) -> bool:
    return dsn.startswith(("postgres://", "postgresql://"))


class Store(ABC):
    @abstractmethod
    def insert_raw(self, quotes: Iterable[RawQuote]) -> int: ...
    @abstractmethod
    def upsert_cell_prices(self, by_day: dict[date, dict[Cell, CellPrice]]) -> int: ...
    @abstractmethod
    def upsert_index(self, points: Iterable[IndexPoint]) -> int: ...
    @abstractmethod
    def log_collection(self, run_at: datetime, source_id: str, url: Optional[str],
                       outcome: str, detail: str = "", n_quotes: int = 0) -> None: ...
    @abstractmethod
    def sync_sources(self, sources: Iterable[SourceConfig], audited_at: datetime) -> int: ...
    @abstractmethod
    def sync_basket(self, basket: Basket) -> int: ...
    @abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# Postgres
# --------------------------------------------------------------------------- #
class PostgresStore(Store):
    def __init__(self, dsn: str):
        import psycopg
        self.conn = psycopg.connect(dsn, autocommit=False)

    def migrate(self) -> None:
        """Apply the schema file. Idempotent — every statement is IF NOT EXISTS."""
        with self.conn.cursor() as cur:
            cur.execute(MIGRATION.read_text())
        self.conn.commit()

    def insert_raw(self, quotes: Iterable[RawQuote]) -> int:
        rows = []
        for q in quotes:
            on = q.collected_at.date() if isinstance(q.collected_at, datetime) else q.collected_at
            rows.append((
                q.source_id, q.collected_at, on, q.route, q.origin, q.destination,
                q.departure_date, q.advance_days, q.carrier, q.flight_number, q.cabin,
                q.fare_family, q.total_inr, q.base_inr, q.taxes_inr, q.surcharges_inr,
                q.currency, q.stops, q.status.value, json.dumps(q.raw_payload, default=str),
            ))
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO raw_quote (source_id,collected_at,collected_on,route,origin,"
                "destination,departure_date,advance_days,carrier,flight_number,cabin,"
                "fare_family,total_inr,base_inr,taxes_inr,surcharges_inr,currency,stops,"
                "status,raw_payload) VALUES (" + ",".join(["%s"] * 19) + ",%s::jsonb)", rows)
        self.conn.commit()
        return len(rows)

    def upsert_cell_prices(self, by_day: dict[date, dict[Cell, CellPrice]]) -> int:
        rows = [
            (day, cell.key(), cell.route, cell.carrier, cell.advance_days, cell.source_id,
             cell.cabin, cp.price, cp.n_quotes, cp.imputed, cp.imputation_source)
            for day, cells in by_day.items() for cell, cp in cells.items()
        ]
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO cell_price (collected_on,cell_key,route,carrier,advance_days,"
                "source_id,cabin,price,n_quotes,imputed,imputation_source) "
                "VALUES (" + ",".join(["%s"] * 11) + ") "
                "ON CONFLICT (collected_on,cell_key) DO UPDATE SET "
                "price=EXCLUDED.price, n_quotes=EXCLUDED.n_quotes, imputed=EXCLUDED.imputed, "
                "imputation_source=EXCLUDED.imputation_source", rows)
        self.conn.commit()
        return len(rows)

    def upsert_index(self, points: Iterable[IndexPoint]) -> int:
        rows = [(p.frequency, p.on_date, p.value, p.n_cells_matched, p.n_cells_imputed,
                 p.coverage, p.imputation_share, p.quality, json.dumps(p.notes))
                for p in points]
        if not rows:
            return 0
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO index_point (frequency,on_date,value,n_cells_matched,"
                "n_cells_imputed,coverage,imputation_share,quality,notes) "
                "VALUES (" + ",".join(["%s"] * 8) + ",%s::jsonb) "
                "ON CONFLICT (frequency,on_date) DO UPDATE SET "
                "value=EXCLUDED.value, n_cells_matched=EXCLUDED.n_cells_matched, "
                "n_cells_imputed=EXCLUDED.n_cells_imputed, coverage=EXCLUDED.coverage, "
                "imputation_share=EXCLUDED.imputation_share, quality=EXCLUDED.quality, "
                "notes=EXCLUDED.notes", rows)
        self.conn.commit()
        return len(rows)

    def log_collection(self, run_at, source_id, url, outcome, detail="", n_quotes=0) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO collection_log (run_at,source_id,url,outcome,detail,n_quotes) "
                "VALUES (%s,%s,%s,%s,%s,%s)", (run_at, source_id, url, outcome, detail, n_quotes))
        self.conn.commit()

    def sync_sources(self, sources, audited_at) -> int:
        rows = [(s.id, s.name, s.kind, list(s.carrier_codes), s.base_url, s.status.value,
                 s.collectable, s.note, s.crawl_delay_s, audited_at) for s in sources]
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO source (id,name,kind,carrier_codes,base_url,status,collectable,"
                "reason,crawl_delay_s,audited_at) VALUES (" + ",".join(["%s"] * 10) + ") "
                "ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, kind=EXCLUDED.kind, "
                "carrier_codes=EXCLUDED.carrier_codes, base_url=EXCLUDED.base_url, "
                "status=EXCLUDED.status, collectable=EXCLUDED.collectable, "
                "reason=EXCLUDED.reason, crawl_delay_s=EXCLUDED.crawl_delay_s, "
                "audited_at=EXCLUDED.audited_at", rows)
        self.conn.commit()
        return len(rows)

    def sync_basket(self, basket: Basket) -> int:
        rows = (
            [("route", k, v, None) for k, v in basket.route_weights.items()]
            + [("carrier", k, v, None) for k, v in basket.carrier_weights.items()]
            + [("window", str(k), v, f"T+{k}") for k, v in basket.window_weights.items()]
        )
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO basket_weight (kind,key,weight,label) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT (kind,key) DO UPDATE SET weight=EXCLUDED.weight, label=EXCLUDED.label",
                rows)
            cur.execute(
                "INSERT INTO index_meta (id,base_period,base_value,weight_source,updated_at) "
                "VALUES (TRUE,%s,%s,%s,now()) ON CONFLICT (id) DO UPDATE SET "
                "base_period=EXCLUDED.base_period, base_value=EXCLUDED.base_value, "
                "weight_source=EXCLUDED.weight_source, updated_at=now()",
                (basket.base_period, basket.base_value,
                 str(basket.meta.get("weight_source", "unspecified"))))
        self.conn.commit()
        return len(rows)

    def load_raw(self, since: Optional[date] = None) -> list[RawQuote]:
        """Every usable raw quote, oldest first.

        The index is chained, so a rebuild needs the whole history, not just
        today's collection. This is what makes the daily job idempotent: it
        appends one day of quotes and recomputes the series from all of them.
        """
        from .models import QuoteStatus
        sql = (
            "SELECT source_id, collected_at, route, origin, destination, departure_date, "
            "advance_days, carrier, flight_number, cabin, fare_family, total_inr, base_inr, "
            "taxes_inr, surcharges_inr, currency, stops, raw_payload "
            "FROM raw_quote WHERE status = 'ok'"
        )
        params: tuple = ()
        if since is not None:
            sql += " AND collected_on >= %s"
            params = (since,)
        sql += " ORDER BY collected_on"

        out: list[RawQuote] = []
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            for r in cur:
                out.append(RawQuote(
                    source_id=r[0], collected_at=r[1], route=r[2], origin=r[3],
                    destination=r[4], departure_date=r[5], advance_days=r[6],
                    carrier=r[7], flight_number=r[8], cabin=r[9] or "ECONOMY",
                    fare_family=r[10], total_inr=r[11], base_inr=r[12], taxes_inr=r[13],
                    surcharges_inr=r[14], currency=r[15] or "INR", stops=r[16],
                    status=QuoteStatus.OK, raw_payload=r[17] or {},
                ))
        return out

    def close(self) -> None:
        self.conn.close()


# --------------------------------------------------------------------------- #
# SQLite (wraps the existing module-level helpers)
# --------------------------------------------------------------------------- #
class SqliteStore(Store):
    def __init__(self, path: str):
        from . import db as _db
        self._db = _db
        self._cm = _db.connect(path)
        self.conn = self._cm.__enter__()

    def insert_raw(self, quotes):
        n = self._db.insert_raw(self.conn, quotes); self.conn.commit(); return n

    def upsert_cell_prices(self, by_day):
        n = self._db.upsert_cell_prices(self.conn, by_day); self.conn.commit(); return n

    def upsert_index(self, points):
        n = self._db.upsert_index(self.conn, points); self.conn.commit(); return n

    def log_collection(self, run_at, source_id, url, outcome, detail="", n_quotes=0):
        self._db.log_collection(self.conn, run_at, source_id, url, outcome, detail, n_quotes)
        self.conn.commit()

    def sync_sources(self, sources, audited_at):
        return 0  # SQLite path is for local pipeline runs; the site reads Postgres.

    def sync_basket(self, basket):
        return 0

    def close(self) -> None:
        self._cm.__exit__(None, None, None)


def open_store(dsn: Optional[str] = None) -> Store:
    """Open whichever backend the DSN names. Defaults to $DATABASE_URL, then SQLite."""
    dsn = dsn or os.environ.get("DATABASE_URL") or "data/apix.db"
    if is_postgres_dsn(dsn):
        return PostgresStore(dsn)
    return SqliteStore(dsn)
