"""Stage 1: turn the DBML data model into a running "operational database".

model2data generates relationship-preserving synthetic data plus a small dbt project around it;
building that project materialises the seeds into a DuckDB file, which then stands in for the
source system that dlt extracts from. Against a real database this whole module drops out and
the dlt source points at that Postgres / MySQL / SaaS API instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field

from refarch.config import (
    GENERATED_DIR,
    GENERATED_PROJECT_DIR,
    SOURCE_DBML,
    SOURCE_DUCKDB,
    SOURCE_SYSTEM_NAME,
)


@dataclass(frozen=True)
class BusinessShape:
    """The knobs that make the synthetic data look like a business rather than noise.

    Every value is deliberate and deterministic: the same shape + seed always produces the
    same rows, so a demo, a test fixture and a CI run all see identical data.
    """

    seed: int = 42
    as_of: str = "2026-09-01"  # anchor for every generated date; pinned so runs are reproducible
    locale: str = "nl_BE"  # a Belgian webshop: Belgian names, cities and postcodes
    rows: int = 100
    rows_for: dict[str, int] = field(
        default_factory=lambda: {
            "customers": 600,
            "products": 48,
            "orders": 4000,
            "order_items": 9000,
        }
    )
    business_hours: bool = True  # orders cluster in waking hours and on weekdays
    growth: float = 0.6  # the shop grows ~60% over the window
    seasonality: float = 0.4  # Q4 peak, the shape retail actually has
    skew: float = 0.5  # a minority of customers place most of the orders

    def cli_args(self) -> list[str]:
        args = [
            "--file",
            str(SOURCE_DBML),
            "--name",
            SOURCE_SYSTEM_NAME,
            "--rows",
            str(self.rows),
            "--seed",
            str(self.seed),
            "--as-of",
            self.as_of,
            "--locale",
            self.locale,
            "--growth",
            str(self.growth),
            "--seasonality",
            str(self.seasonality),
            "--skew",
            str(self.skew),
            "--force",
        ]
        if self.business_hours:
            args.append("--business-hours")
        for table, n in self.rows_for.items():
            args += ["--rows-for", f"{table}={n}"]
        return args


# dbt reads these straight from the environment, so whatever this repo's own dbt run needs
# would otherwise leak into the *generated* project -- which is a separate dbt project with
# its own profile and only a `dev` target. `DBT_TARGET=prod` in CI made the generated build
# fail with "does not have a target named 'prod'".
_INHERITED_DBT_VARS = ("DBT_TARGET", "DBT_PROFILES_DIR", "DBT_PROJECT_DIR")


def _generated_project_env() -> dict[str, str]:
    """The environment for the generated project: this one, minus anything aimed at our own dbt."""
    return {k: v for k, v in os.environ.items() if k not in _INHERITED_DBT_VARS}


def generate(shape: BusinessShape | None = None) -> None:
    """Generate the synthetic source system and materialise it as a DuckDB database."""
    shape = shape or BusinessShape()
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    if GENERATED_PROJECT_DIR.exists():
        shutil.rmtree(GENERATED_PROJECT_DIR)

    subprocess.run(["model2data", *shape.cli_args()], cwd=GENERATED_DIR, check=True)
    # One `dbt build` loads the seeds, builds model2data's staging views and runs its tests --
    # the generated project's own verification that the data is internally consistent.
    # Not --quiet: when this fails, the reason is the only thing worth having.
    subprocess.run(
        ["dbt", "build", "--profiles-dir", "."],
        cwd=GENERATED_PROJECT_DIR,
        check=True,
        env=_generated_project_env(),
    )
    if not SOURCE_DUCKDB.exists():
        raise RuntimeError(f"Expected {SOURCE_DUCKDB} after building the generated project")
