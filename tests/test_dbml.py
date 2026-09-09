"""The DBML is the contract for the whole stack: guard the things downstream relies on."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import pytest

from refarch.config import SOURCE_DBML
from refarch.pipelines.webshop import TABLES


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("m2d")
    subprocess.run(
        [
            "model2data",
            "--file",
            str(SOURCE_DBML),
            "--name",
            "t",
            "--rows",
            "12",
            "--seed",
            "1",
            "--as-of",
            "2026-01-01",
            "--force",
        ],
        cwd=out,
        check=True,
        capture_output=True,
    )
    return out / "dbt_t" / "seeds" / "raw"


def test_every_extracted_table_is_generated(generated: Path) -> None:
    for table in TABLES:
        assert (generated / f"{table}.csv").exists(), table


def test_cursor_columns_exist(generated: Path) -> None:
    for table, cursor in TABLES.items():
        with open(generated / f"{table}.csv", newline="") as f:
            header = next(csv.reader(f))
        assert cursor in header, f"{table} has no {cursor} column for dlt to page on"
        assert "id" in header, f"{table} has no id column for dlt to merge on"


def test_generated_project_env_drops_our_dbt_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """The generated project is a separate dbt project with only a `dev` target.

    dbt reads DBT_TARGET from the environment, so leaking this repo's value into that build
    fails it outright -- which is exactly what happened in CI, where the job sets
    DBT_TARGET=prod for this project's own models.
    """
    from refarch.generate import _generated_project_env

    monkeypatch.setenv("DBT_TARGET", "prod")
    monkeypatch.setenv("DBT_PROFILES_DIR", "/somewhere/else")
    monkeypatch.setenv("GCP_PROJECT", "example-project")

    env = _generated_project_env()

    assert "DBT_TARGET" not in env
    assert "DBT_PROFILES_DIR" not in env
    assert env["GCP_PROJECT"] == "example-project", "unrelated variables must still pass through"
