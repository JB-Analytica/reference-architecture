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


def test_base_path_is_restored_even_when_the_build_fails() -> None:
    """The base path is written into a checked-in file, so it must always come back out.

    evidence.config.yaml carries the comments explaining the brand colour choices. If a failed
    build left the deployment block behind, the next local build would produce a report whose
    assets only resolve under /reference-architecture -- and a stray diff would land in review.
    """
    import pytest

    from refarch.cli import _base_path
    from refarch.config import EVIDENCE_CONFIG

    before = EVIDENCE_CONFIG.read_text()
    with pytest.raises(RuntimeError), _base_path("/reference-architecture"):
        assert "basePath: /reference-architecture" in EVIDENCE_CONFIG.read_text()
        raise RuntimeError("build blew up")
    assert EVIDENCE_CONFIG.read_text() == before


def test_no_base_path_leaves_the_config_untouched() -> None:
    from refarch.cli import _base_path
    from refarch.config import EVIDENCE_CONFIG

    before = EVIDENCE_CONFIG.read_text()
    with _base_path(None):
        assert EVIDENCE_CONFIG.read_text() == before
    assert EVIDENCE_CONFIG.read_text() == before


def test_report_diagram_is_the_exported_one() -> None:
    """The report serves the same diagram the docs do.

    `docs/architecture/diagram.svg` is an export of `diagram.html`; Evidence can only serve
    files out of `evidence/static`, so the report needs its own copy. Two copies of a drawing
    is exactly how a report ends up showing an architecture the repo no longer has, so pin
    them together: re-export the diagram and copy it across, or this fails.
    """
    from refarch.config import EVIDENCE_DIR, ROOT

    source = ROOT / "docs" / "architecture" / "diagram.svg"
    served = EVIDENCE_DIR / "static" / "architecture.svg"
    assert served.read_bytes() == source.read_bytes(), (
        "evidence/static/architecture.svg is stale -- copy docs/architecture/diagram.svg over it"
    )
