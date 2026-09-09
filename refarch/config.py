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
LIGHTDASH_DIR = ROOT / "lightdash"
DLT_PIPELINES_DIR = ROOT / ".dlt" / "pipelines"
RAW_DATASET = f"raw_{SOURCE_SYSTEM_NAME}"


@dataclass(frozen=True)
class Settings:
    gcp_project: str
    bigquery_location: str
    credentials_path: Path | None
    dbt_target: str

    @property
    def credentials(self) -> Path:
        if self.credentials_path is None or not self.credentials_path.exists():
            raise FileNotFoundError(
                "GOOGLE_APPLICATION_CREDENTIALS must point at a service-account JSON key "
                "(see .env.example)."
            )
        return self.credentials_path


def settings() -> Settings:
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    project = os.environ.get("GCP_PROJECT")
    if not project:
        raise RuntimeError(
            "GCP_PROJECT is not set. Copy .env.example to .env and point it at your own "
            "BigQuery project -- there is deliberately no default, so a fresh clone cannot "
            "quietly aim at somebody else's warehouse."
        )
    return Settings(
        gcp_project=project,
        bigquery_location=os.environ.get("BIGQUERY_LOCATION", "EU"),
        credentials_path=Path(creds).expanduser() if creds else None,
        dbt_target=os.environ.get("DBT_TARGET", "dev"),
    )
