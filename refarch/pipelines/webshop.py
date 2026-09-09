"""Stage 2: extract the webshop's operational database into the warehouse with dlt.

The source is dlt's generic `sql_database` source over a SQLAlchemy URL. Here that URL points
at the DuckDB file model2data produced; against a real system it would be that Postgres or MySQL,
and nothing else in this module changes.
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Any

import dlt
from dlt.common.pipeline import LoadInfo
from dlt.sources.sql_database import sql_database

from refarch.config import DLT_PIPELINES_DIR, RAW_DATASET, SOURCE_DUCKDB, SOURCE_SCHEMA, Settings

# The pyarrow backend hands dlt whole Arrow tables, and dlt will not rewrite them to add its
# lineage columns unless asked. Without _dlt_load_id there is nothing recording *when* a row
# arrived, which is exactly what dbt source freshness needs. Set as environment defaults rather
# than in .dlt/config.toml so the setting travels with the code and applies no matter which
# directory the pipeline is invoked from (tests included).
os.environ.setdefault("NORMALIZE__PARQUET_NORMALIZER__ADD_DLT_LOAD_ID", "true")
os.environ.setdefault("NORMALIZE__PARQUET_NORMALIZER__ADD_DLT_ID", "true")

# Table -> cursor column. Mutable tables carry an `updated_at` the source keeps current, so only
# rows touched since the last run are read and merged in. `order_items` is append-only, so its
# monotonically increasing key is the cursor. Every table merges on `id`, which also makes the
# load idempotent: re-running never duplicates a row.
TABLES: dict[str, str] = {
    "customers": "updated_at",
    "products": "updated_at",
    "orders": "updated_at",
    "order_items": "id",
}


def webshop_source(duckdb_path: Path = SOURCE_DUCKDB, schema: str = SOURCE_SCHEMA):
    warnings.filterwarnings("ignore", message="duckdb-engine doesn't yet support reflection")
    source = sql_database(
        credentials=f"duckdb:///{duckdb_path}",
        schema=schema,
        table_names=list(TABLES),
        backend="pyarrow",
    )
    for table, cursor in TABLES.items():
        source.resources[table].apply_hints(
            primary_key="id",
            write_disposition="merge",
            incremental=dlt.sources.incremental(cursor),
        )
    return source


def bigquery_destination(settings: Settings) -> Any:
    credentials = json.loads(settings.credentials.read_text())
    return dlt.destinations.bigquery(
        credentials=credentials,
        location=settings.bigquery_location,
    )


def build_pipeline(destination: Any, pipelines_dir: Path = DLT_PIPELINES_DIR) -> dlt.Pipeline:
    return dlt.pipeline(
        pipeline_name="webshop",
        destination=destination,
        dataset_name=RAW_DATASET,
        pipelines_dir=str(pipelines_dir),
    )


def run(settings: Settings) -> LoadInfo:
    pipeline = build_pipeline(bigquery_destination(settings))
    info = pipeline.run(webshop_source())
    info.raise_on_failed_jobs()
    return info
