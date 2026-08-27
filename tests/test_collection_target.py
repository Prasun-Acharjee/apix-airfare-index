"""Where a collection run writes its quotes.

The index is chained: a rebuild reads the whole accumulated history, so the
collector MUST append to the same database the rebuild reads from. A scheduled
run that writes to the CI runner's local disk loses every quote when the job
ends, and the series never reaches the two collection days a chain link needs.

That is not hypothetical — it is what `--db` defaulting to a file path did.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from apix.collect.runner import CollectionRun

ROOT = Path(__file__).resolve().parent.parent
DSN = "postgresql://apix:secret@db.example.net:5432/apix"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_collection", ROOT / "scripts" / "run_collection.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


run_collection = _load_script()


def parsed_db(argv: list[str]):
    return run_collection.build_parser().parse_args(argv).db


def test_db_flag_defaults_to_unset_so_the_env_fallback_survives():
    # A file-path default here is truthy, which makes CollectionRun's
    # `db_path or $DATABASE_URL` resolve to the path and never consult the
    # environment. The default must stay None.
    assert parsed_db([]) is None


def test_scheduled_run_writes_to_postgres(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DSN)
    run = CollectionRun(db_path=parsed_db([]))
    assert run.db_path == DSN


def test_explicit_db_still_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DSN)
    run = CollectionRun(db_path=parsed_db(["--db", "data/local.db"]))
    assert run.db_path == "data/local.db"


def test_falls_back_to_sqlite_only_when_nothing_is_configured(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    run = CollectionRun(db_path=parsed_db([]))
    assert run.db_path == "data/apix.db"


@pytest.mark.parametrize("dsn,expected", [
    (DSN, "Postgres db.example.net:5432/apix"),
    ("postgres://db.example.net/apix", "Postgres db.example.net/apix"),
    ("data/apix.db", "SQLite data/apix.db"),
])
def test_target_is_reported_without_leaking_credentials(dsn, expected):
    described = run_collection.describe_target(dsn)
    assert described == expected
    assert "secret" not in described
