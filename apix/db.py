"""SQLite persistence. Raw quotes are append-only and never edited in place.

An official statistic has to be reproducible from its inputs years later, so
the raw table keeps the payload exactly as received, including the failures:
a run where a source blocked us is a row, not an absence. `collection_log`
is what lets you answer "why was 12 March imputed?" without guessing.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .models import Cell, CellPrice, IndexPoint, NormalisedQuote, QuoteStatus, RawQuote

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS raw_quote (
    id              INTEGER PRIMARY KEY,
    source_id       TEXT NOT NULL,
    collected_at    TEXT NOT NULL,
    collected_on    TEXT NOT NULL,
    route           TEXT NOT NULL,
    origin          TEXT NOT NULL,
    destination     TEXT NOT NULL,
    departure_date  TEXT NOT NULL,
    advance_days    INTEGER NOT NULL,
    carrier         TEXT,
    flight_number   TEXT,
    cabin           TEXT,
    fare_family     TEXT,
    total_inr       REAL,
    base_inr        REAL,
    taxes_inr       REAL,
    surcharges_inr  REAL,
    currency        TEXT,
    stops           INTEGER,
    status          TEXT NOT NULL,
    raw_payload     TEXT
);
CREATE INDEX IF NOT EXISTS ix_raw_day ON raw_quote(collected_on);
CREATE INDEX IF NOT EXISTS ix_raw_route ON raw_quote(route, collected_on);

CREATE TABLE IF NOT EXISTS cell_price (
    collected_on    TEXT NOT NULL,
    cell_key        TEXT NOT NULL,
    route           TEXT NOT NULL,
    carrier         TEXT NOT NULL,
    advance_days    INTEGER NOT NULL,
    source_id       TEXT NOT NULL,
    cabin           TEXT NOT NULL,
    price           REAL NOT NULL,
    n_quotes        INTEGER NOT NULL,
    imputed         INTEGER NOT NULL DEFAULT 0,
    imputation_source TEXT,
    PRIMARY KEY (collected_on, cell_key)
);

CREATE TABLE IF NOT EXISTS index_point (
    frequency       TEXT NOT NULL,
    on_date         TEXT NOT NULL,
    value           REAL NOT NULL,
    n_cells_matched INTEGER NOT NULL,
    n_cells_imputed INTEGER NOT NULL,
    coverage        REAL NOT NULL,
    imputation_share REAL NOT NULL,
    quality         TEXT NOT NULL,
    notes           TEXT,
    PRIMARY KEY (frequency, on_date)
);

CREATE TABLE IF NOT EXISTS collection_log (
    id          INTEGER PRIMARY KEY,
    run_at      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    url         TEXT,
    outcome     TEXT NOT NULL,
    detail      TEXT,
    n_quotes    INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_log_run ON collection_log(run_at);
"""


@contextmanager
def connect(path: str | Path = "data/apix.db") -> Iterator[sqlite3.Connection]:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_raw(conn: sqlite3.Connection, quotes: Iterable[RawQuote]) -> int:
    rows = []
    for q in quotes:
        collected_on = q.collected_at.date() if isinstance(q.collected_at, datetime) else q.collected_at
        rows.append((
            q.source_id, q.collected_at.isoformat(), collected_on.isoformat(),
            q.route, q.origin, q.destination, q.departure_date.isoformat(), q.advance_days,
            q.carrier, q.flight_number, q.cabin, q.fare_family,
            q.total_inr, q.base_inr, q.taxes_inr, q.surcharges_inr, q.currency,
            q.stops, q.status.value, json.dumps(q.raw_payload, default=str),
        ))
    conn.executemany(
        "INSERT INTO raw_quote (source_id,collected_at,collected_on,route,origin,destination,"
        "departure_date,advance_days,carrier,flight_number,cabin,fare_family,total_inr,base_inr,"
        "taxes_inr,surcharges_inr,currency,stops,status,raw_payload) "
        "VALUES (" + ",".join("?" * 20) + ")", rows)
    return len(rows)


def upsert_cell_prices(conn: sqlite3.Connection, by_day: dict[date, dict[Cell, CellPrice]]) -> int:
    rows = []
    for day, cells in by_day.items():
        for cell, cp in cells.items():
            rows.append((
                day.isoformat(), cell.key(), cell.route, cell.carrier, cell.advance_days,
                cell.source_id, cell.cabin, cp.price, cp.n_quotes,
                1 if cp.imputed else 0, cp.imputation_source,
            ))
    conn.executemany(
        "INSERT OR REPLACE INTO cell_price (collected_on,cell_key,route,carrier,advance_days,"
        "source_id,cabin,price,n_quotes,imputed,imputation_source) VALUES ("
        + ",".join("?" * 11) + ")", rows)
    return len(rows)


def upsert_index(conn: sqlite3.Connection, points: Iterable[IndexPoint]) -> int:
    rows = [(p.frequency, p.on_date.isoformat(), p.value, p.n_cells_matched, p.n_cells_imputed,
             p.coverage, p.imputation_share, p.quality, json.dumps(p.notes)) for p in points]
    conn.executemany(
        "INSERT OR REPLACE INTO index_point (frequency,on_date,value,n_cells_matched,"
        "n_cells_imputed,coverage,imputation_share,quality,notes) VALUES ("
        + ",".join("?" * 9) + ")", rows)
    return len(rows)


def log_collection(conn: sqlite3.Connection, run_at: datetime, source_id: str,
                   url: Optional[str], outcome: str, detail: str = "", n_quotes: int = 0) -> None:
    conn.execute(
        "INSERT INTO collection_log (run_at,source_id,url,outcome,detail,n_quotes) VALUES (?,?,?,?,?,?)",
        (run_at.isoformat(), source_id, url, outcome, detail, n_quotes))


def load_cell_prices(conn: sqlite3.Connection, include_imputed: bool = False) -> dict[date, dict[Cell, CellPrice]]:
    sql = "SELECT * FROM cell_price" + ("" if include_imputed else " WHERE imputed=0")
    out: dict[date, dict[Cell, CellPrice]] = {}
    for r in conn.execute(sql + " ORDER BY collected_on"):
        day = date.fromisoformat(r["collected_on"])
        cell = Cell(route=r["route"], carrier=r["carrier"], advance_days=r["advance_days"],
                    source_id=r["source_id"], cabin=r["cabin"])
        out.setdefault(day, {})[cell] = CellPrice(
            cell=cell, on_date=day, price=r["price"], n_quotes=r["n_quotes"],
            imputed=bool(r["imputed"]), imputation_source=r["imputation_source"])
    return out


def load_index(conn: sqlite3.Connection, frequency: str = "daily") -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM index_point WHERE frequency=? ORDER BY on_date", (frequency,))]
