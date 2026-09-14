"""Paths and environment-driven settings shared by every stage of the stack."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- the synthetic source system -------------------------------------------------------------
SOURCE_SYSTEM_NAME = "webshop"
SOURCE_DBML = ROOT / "source_system" / f"{SOURCE_SYSTEM_NAME}.dbml"
GENERATED_DIR = ROOT / "source_system" / "generated"
# model2data writes dbt_<name>/ into its working directory and names the DuckDB file after the
# profile it generates; this is the file that plays the role of the operational database.
GENERATED_PROJECT_DIR = GENERATED_DIR / f"dbt_{SOURCE_SYSTEM_NAME}"
SOURCE_DUCKDB = GENERATED_PROJECT_DIR / f"{SOURCE_SYSTEM_NAME}_profile.duckdb"
SOURCE_SCHEMA = "raw"  # model2data seeds land here inside the DuckDB file

# --- warehouse and downstream ------------------------------------------------------------------
DBT_DIR = ROOT / "dbt"
DLT_PIPELINES_DIR = ROOT / ".dlt" / "pipelines"
RAW_DATASET = f"raw_{SOURCE_SYSTEM_NAME}"

# The warehouse is a single DuckDB file: dlt writes raw_webshop into it, dbt reads that and
# writes its own schemas back to the same file. One file keeps the whole warehouse inspectable
# with `duckdb warehouse/refarch.duckdb` and makes the stack runnable with no accounts at all.
# DuckDB allows one writer at a time, so the stages run in sequence -- which they already do.
WAREHOUSE_DIR = ROOT / "warehouse"
DEFAULT_WAREHOUSE = WAREHOUSE_DIR / "refarch.duckdb"


@dataclass(frozen=True)
class Settings:
    warehouse_path: Path
    dbt_target: str


def settings() -> Settings:
    """Read the settings. Every one has a working default: a fresh clone needs no .env."""
    path = os.environ.get("REFARCH_WAREHOUSE")
    return Settings(
        warehouse_path=Path(path).expanduser() if path else DEFAULT_WAREHOUSE,
        dbt_target=os.environ.get("DBT_TARGET", "dev"),
    )
