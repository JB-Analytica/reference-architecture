"""The claims the dbt project makes about itself, checked without running dbt.

These read files rather than a manifest on purpose: `uv run pytest` has to pass on a fresh
clone with no warehouse and no `dbt parse` behind it.
"""

from __future__ import annotations

import re

import pytest
import yaml
from packaging.specifiers import SpecifierSet

from refarch.config import DBT_DIR, EVIDENCE_SOURCE_DIR, ROOT

MODELS = DBT_DIR / "models"


@pytest.fixture(scope="module")
def dbt_project() -> dict:
    return yaml.safe_load((DBT_DIR / "dbt_project.yml").read_text())


def _model_names(folder: str) -> set[str]:
    return {p.stem for p in (MODELS / folder).rglob("*.sql")}


def test_only_the_marts_folder_is_tagged_bi(dbt_project: dict) -> None:
    """The `bi` tag is the exposure boundary, so it has to sit on marts and nowhere else."""
    layers = dbt_project["models"]["refarch"]
    tagged = {name for name, cfg in layers.items() if "bi" in (cfg.get("+tags") or [])}
    assert tagged == {"marts"}, f"expected only marts to carry the bi tag, found {tagged}"


def test_the_report_reads_only_bi_tagged_marts() -> None:
    """Every Evidence source query selects from a mart, and never from anything upstream.

    The README says only the marts are exposed to the report. Nothing made that true -- a
    source query pointing at `refarch_staging.stg_webshop__orders` would have worked fine and
    quietly moved a column definition out of the layer that is supposed to own it. This is the
    check that makes the claim a rule.
    """
    marts = _model_names("marts")
    upstream = _model_names("staging") | _model_names("intermediate")
    assert marts and upstream, "expected to find models in both marts and upstream folders"

    queries = sorted(EVIDENCE_SOURCE_DIR.glob("*.sql"))
    assert queries, f"no Evidence source queries found in {EVIDENCE_SOURCE_DIR}"

    for query in queries:
        sql = query.read_text()
        referenced = set(re.findall(r"\bfrom\s+([A-Za-z_][\w.]*)", sql, flags=re.IGNORECASE))
        assert referenced, f"{query.name} selects from nothing"

        for ref in referenced:
            schema, _, table = ref.rpartition(".")
            assert table in marts, (
                f"{query.name} reads `{ref}`, which is not a mart. Evidence may only read the "
                f"marts layer; marts are {sorted(marts)}."
            )
            assert schema.endswith("_marts"), (
                f"{query.name} reads `{ref}`, whose schema is not a marts schema."
            )

        leaked = {name for name in upstream if name in sql}
        assert not leaked, (
            f"{query.name} mentions upstream model(s) {sorted(leaked)}. Staging and intermediate "
            "models exist for lineage and debugging, not for the report."
        )


def test_the_marts_schema_the_cli_guards_is_the_one_the_report_queries() -> None:
    """`refarch report` refuses to build when this schema is missing; it must be the real one."""
    from refarch.cli import MARTS_SCHEMA

    sql = "\n".join(p.read_text() for p in EVIDENCE_SOURCE_DIR.glob("*.sql"))
    assert f"{MARTS_SCHEMA}." in sql, (
        f"the CLI guards {MARTS_SCHEMA!r} but no source query reads that schema"
    )


def test_require_dbt_version_matches_pyproject(dbt_project: dict) -> None:
    """One dbt-core constraint, written in two files that cannot see each other.

    `pyproject.toml` decides which dbt the virtualenv installs; `require-dbt-version` decides
    which dbt is allowed to run the project at all, including a system dbt that never went
    through uv. If they drift, one of them is a lie.
    """
    declared = dbt_project["require-dbt-version"]
    project_spec = SpecifierSet(",".join(declared if isinstance(declared, list) else [declared]))

    pyproject = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'"dbt-core([^"]*)"', pyproject)
    assert match, "no dbt-core requirement found in pyproject.toml"
    package_spec = SpecifierSet(match.group(1))

    probes = ["1.8.0", "1.12.3", "1.12.4", "1.13.0", "1.99.9", "2.0.0rc2", "2.0.0", "3.0.0"]
    assert [project_spec.contains(v, prereleases=True) for v in probes] == [
        package_spec.contains(v, prereleases=True) for v in probes
    ], (
        f"dbt_project.yml requires {project_spec} but pyproject.toml pins {package_spec}; "
        "they must accept the same versions"
    )
