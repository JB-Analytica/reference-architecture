"""Run the real dlt source against a DuckDB destination: no warehouse needed to prove the logic."""

from __future__ import annotations

from pathlib import Path

import dlt
import duckdb

from refarch.config import RAW_DATASET
from refarch.pipelines.webshop import TABLES, build_pipeline, webshop_source


def _pipeline(tmp_path: Path):
    dest = dlt.destinations.duckdb(str(tmp_path / "warehouse.duckdb"))
    return build_pipeline(dest, pipelines_dir=tmp_path / "pipelines")


def _count(tmp_path: Path, table: str) -> int:
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"), read_only=True)
    try:
        return con.execute(f"select count(*) from {RAW_DATASET}.{table}").fetchone()[0]
    finally:
        con.close()


def test_first_load_brings_every_table(tmp_path: Path, source_db: Path) -> None:
    p = _pipeline(tmp_path)
    info = p.run(webshop_source(source_db))
    info.raise_on_failed_jobs()
    assert {_count(tmp_path, t) for t in TABLES} == {2, 1}


def test_rerun_is_idempotent(tmp_path: Path, source_db: Path) -> None:
    p = _pipeline(tmp_path)
    p.run(webshop_source(source_db))
    p.run(webshop_source(source_db))
    assert _count(tmp_path, "orders") == 2
    assert _count(tmp_path, "order_items") == 2


def test_updated_row_is_merged_not_duplicated(tmp_path: Path, source_db: Path) -> None:
    p = _pipeline(tmp_path)
    p.run(webshop_source(source_db))

    con = duckdb.connect(str(source_db))
    con.execute(
        "update raw.orders set status = 'paid', updated_at = timestamp '2026-04-01' where id = 11"
    )
    con.execute("insert into raw.order_items values (102, 11, 1, 3, 1450, 0)")
    con.close()

    p.run(webshop_source(source_db))
    assert _count(tmp_path, "orders") == 2
    assert _count(tmp_path, "order_items") == 3
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"), read_only=True)
    status = con.execute(f"select status from {RAW_DATASET}.orders where id = 11").fetchone()[0]
    con.close()
    assert status == "paid"
