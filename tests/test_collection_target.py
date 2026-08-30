"""Where a collection run writes its quotes.

The index is chained: a rebuild reads the whole accumulated history, so the
collector MUST append to the same database the rebuild reads from. A scheduled
run that writes to the CI runner's local disk loses every quote when the job
ends, and the series never reaches the two collection days a chain link needs.

That is not hypothetical — it is what `--db` defaulting to a file path did.
"""
from __future__ import annotations

import importlib.util
import sys
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


REAL_SHAPED_DSN = ("postgresql://neondb_owner:npg_EXAMPLEpassword@"
                   "ep-snowy-example-pooler.c-4.us-east-2.aws.neon.tech/neondb"
                   "?sslmode=require&channel_binding=require")


@pytest.mark.parametrize("dsn", [DSN, REAL_SHAPED_DSN, "postgres://db.example.net/apix"])
def test_a_postgres_target_leaks_nothing_into_the_log(dsn):
    """This line lands in a CI log that is world-readable on a public repo.

    Stripping the password is not enough: the endpoint hostname and database
    name identify the target precisely, which is exactly what an attacker needs
    to point a credential at. Nothing from the DSN may survive but a digest.
    """
    described = run_collection.describe_target(dsn)
    assert described.startswith("Postgres (endpoint redacted, dsn:")
    for leaked in ("neon.tech", "ep-snowy", "neondb", "db.example.net", "apix",
                   "npg_", "secret", "password", "sslmode", "@"):
        assert leaked not in described, f"{leaked!r} reached the log"


def test_the_digest_is_stable_and_distinguishes_databases():
    # Stable across runs so "same database as yesterday" is answerable, and
    # different per DSN so a misrouted run is still visible.
    assert run_collection.describe_target(DSN) == run_collection.describe_target(DSN)
    assert run_collection.describe_target(DSN) != run_collection.describe_target(REAL_SHAPED_DSN)


def test_a_sqlite_path_is_still_shown_in_full():
    # A local path holds no secret, and this is the case the line was added for.
    assert run_collection.describe_target("data/apix.db") == "SQLite data/apix.db"


def _stats(total_quotes: int) -> dict:
    return {"sources": {"easemytrip": {"requests_ok": 0 if not total_quotes else 75,
                                       "blocked": 75 if not total_quotes else 0,
                                       "failed": 0, "rows_written": total_quotes,
                                       "quotes": total_quotes}},
            "skipped": {}, "total_quotes": total_quotes, "requests_per_source": 75}


@pytest.fixture
def pass_yielding(monkeypatch):
    """Run main() over a stubbed collection pass and return its exit code."""
    from contextlib import contextmanager

    @contextmanager
    def _no_browser(headless=True):
        yield None

    monkeypatch.setenv("DATABASE_URL", DSN)
    monkeypatch.setattr(run_collection, "playwright_browser", _no_browser)
    monkeypatch.setattr(sys, "argv", ["run_collection.py"])

    def invoke(total_quotes: int) -> int:
        monkeypatch.setattr(CollectionRun, "run",
                            lambda self, run_date=None: _stats(total_quotes))
        return run_collection.main()

    return invoke


def test_a_pass_that_collects_nothing_is_a_failure(pass_yielding, capsys):
    # Exiting 0 here is what let the workflow carry on to the rebuild, which
    # then failed for want of a second collection day - two steps from the cause.
    assert pass_yielding(0) == 1
    assert "returned nothing" in capsys.readouterr().err


def test_a_pass_that_collects_quotes_succeeds(pass_yielding, capsys):
    assert pass_yielding(8129) == 0
    out = capsys.readouterr().out
    assert "Rows written: 8,129 -> Postgres (endpoint redacted, dsn:" in out
    for leaked in ("secret", "db.example.net", "apix:", "@"):
        assert leaked not in out, f"{leaked!r} reached the log"
