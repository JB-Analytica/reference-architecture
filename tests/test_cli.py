from __future__ import annotations

import os
from pathlib import Path

from typer.testing import CliRunner

from refarch.cli import app


def test_help_lists_every_stage() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for stage in ("generate", "load", "transform", "report", "run"):
        assert stage in result.output


def test_settings_need_no_environment(monkeypatch) -> None:
    """A fresh clone with no .env must still run.

    This is the point of the DuckDB warehouse: the previous BigQuery version refused to start
    without GCP_PROJECT and a service-account key, which put the whole example behind an
    account. Nothing here may grow a required variable again.
    """
    from refarch.config import DEFAULT_WAREHOUSE, settings

    for var in ("REFARCH_WAREHOUSE", "DBT_TARGET"):
        monkeypatch.delenv(var, raising=False)

    resolved = settings()
    assert resolved.warehouse_path == DEFAULT_WAREHOUSE
    assert resolved.dbt_target == "dev"


def test_warehouse_path_is_overridable(monkeypatch, tmp_path: Path) -> None:
    from refarch.config import settings

    monkeypatch.setenv("REFARCH_WAREHOUSE", str(tmp_path / "elsewhere.duckdb"))
    assert settings().warehouse_path == tmp_path / "elsewhere.duckdb"


def test_evidence_filename_is_relative_to_the_source_folder(monkeypatch, tmp_path: Path) -> None:
    """Evidence cannot be given an absolute warehouse path.

    It resolves a source's `filename` against that source's own folder and overwrites any
    `directory` handed to it, so the override has to be a relative path. If this ever silently
    became absolute, Evidence would look for the warehouse *inside* evidence/sources/refarch and
    report that the database does not exist.
    """
    from refarch.cli import _evidence_env
    from refarch.config import EVIDENCE_SOURCE_DIR

    monkeypatch.setenv("REFARCH_WAREHOUSE", str(tmp_path / "elsewhere" / "refarch.duckdb"))
    filename = _evidence_env()["EVIDENCE_SOURCE__refarch__filename"]

    assert not os.path.isabs(filename)
    resolved = (EVIDENCE_SOURCE_DIR / filename).resolve()
    assert resolved == (tmp_path / "elsewhere" / "refarch.duckdb").resolve()
