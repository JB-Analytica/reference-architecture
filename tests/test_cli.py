from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from refarch.cli import app


def test_help_lists_every_stage() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for stage in ("generate", "load", "transform", "run"):
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
