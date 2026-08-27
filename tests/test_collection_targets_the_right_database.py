"""Where a scheduled collection writes its quotes.

The nightly run collected into the CI runner's SQLite file, which was discarded
with the runner, so the rebuild saw one collection day and refused to republish
the series. The cause was a CLI default, not the runner: argparse handed
`db_path` a non-empty SQLite path, so the `or os.environ[...]` fallback in
CollectionRun never fired. These pin the wiring end to end.
"""
from __future__ import annotations

import runpy
import sys
from contextlib import contextmanager

import pytest

from apix.collect.runner import CollectionRun

DSN = "postgresql://u:p@example.invalid/apix"
SCRIPT = "scripts/run_collection.py"


@contextmanager
def _no_browser(headless=True):
    yield None


@pytest.fixture
def script(monkeypatch):
    """Run scripts/run_collection.py with no browser and a stubbed pass.

    Yields a setter for the stats the run reports; returns the CollectionRun
    the script actually built, so the DSN it chose can be inspected.
    """
    built: list[CollectionRun] = []
    stats = {"sources": {}, "skipped": {}, "total_quotes": 1, "requests_per_source": 75}

    def fake_run(self, run_date=None):
        built.append(self)
        return stats

    monkeypatch.setattr(sys, "argv", [SCRIPT])
    monkeypatch.setattr("apix.collect.runner.playwright_browser", _no_browser)
    monkeypatch.setattr(CollectionRun, "run", fake_run)

    def invoke(**overrides):
        stats.update(overrides)
        with pytest.raises(SystemExit) as e:
            runpy.run_path(SCRIPT, run_name="__main__")
        return e.value.code, built[-1] if built else None

    return invoke


def test_cli_defers_to_database_url_instead_of_the_local_sqlite_file(script, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DSN)
    code, run = script()
    assert code == 0
    assert run.db_path == DSN, "a non-empty --db default silently overrides $DATABASE_URL"


def test_cli_still_falls_back_to_sqlite_when_nothing_is_configured(script, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    _, run = script()
    assert run.db_path == "data/apix.db"


def test_an_explicit_dsn_wins_over_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", DSN)
    assert CollectionRun(db_path="data/apix.db").db_path == "data/apix.db"


def test_a_pass_that_collects_nothing_is_a_failure(script, monkeypatch, capsys):
    """Exiting 0 on zero quotes let the workflow blame the next step instead."""
    monkeypatch.setenv("DATABASE_URL", DSN)
    code, _ = script(total_quotes=0,
                     sources={"easemytrip": {"requests_ok": 0, "blocked": 75,
                                             "failed": 0, "rows_written": 0, "quotes": 0}})
    assert code == 1
    assert "returned nothing" in capsys.readouterr().err
