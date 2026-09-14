# reference-architecture

A runnable reference stack: DBML → model2data → dlt → DuckDB → dbt. It is published as a worked
example, so changes should hold up as one — readable and honest, not just working.

It runs with no accounts and no credentials: `git clone`, `uv sync`, `uv run refarch run`. That
constraint is the point, not a convenience — protect it. A change that reintroduces a required
secret, a cloud project or a paid service puts the whole example back behind a signup.

**The BI layer is an open question.** Lightdash was dropped with BigQuery (it has no DuckDB
connector) and no replacement has been chosen yet. The marts and their metric definitions are
in place and waiting for one.

## Commands

```bash
uv sync --extra dev
uv run poe check                       # ruff + ty + pytest
uv run refarch run --target prod       # all four stages
uv run refarch transform build -s +fct_orders   # extra args pass through to dbt
```

## Layout

- `source_system/webshop.dbml` — the only description of the source system. Edit this, not the
  generated data.
- `source_system/generated/` — git-ignored. Deterministic; rebuild with `refarch generate`.
- `refarch/` — config, model2data wrapper, dlt pipeline, Typer CLI.
- `dbt/` — staging (one model per source table) → intermediate → marts. `profiles.yml` is
  checked in and needs no environment at all.
- `warehouse/` — git-ignored. The DuckDB file the stack builds; rebuild with `refarch run`.

## Conventions specific to this repo

- **Metrics are defined in `dbt/models/marts/_marts__models.yml`, never in a BI tool's UI.**
  A metric added through a UI is invisible to review and is lost on the next deploy. Those
  blocks still carry Lightdash's `meta:` syntax; the definitions are the substance and the
  spelling gets reconciled when a front end is picked.
- **Only marts are exposed to BI**, via the `bi` tag that `dbt_project.yml` applies to the
  marts folder. Do not tag a staging or intermediate model.
- **Warehouse SQL is DuckDB SQL.** No `initcap`, no `timestamp_diff`, no `safe_divide`. Where
  a dialect gap needs papering over, add a macro next to `cents_to_eur` and `title_case` rather
  than inlining the workaround.
- **Money is integer cents in the source and euros in the marts.** Convert with the
  `cents_to_eur` macro at the mart boundary only.
- **Layering and naming follow the staging / intermediate / marts convention** described in
  `docs/architecture/README.md`. Read that before adding a model.

## Gotchas

- **`.env` is optional and nothing in it is required.** Only `DBT_TARGET` and
  `REFARCH_WAREHOUSE` are read, and both have working defaults.
- **dlt and dbt share one DuckDB file**, and DuckDB locks it to a single writing process. Run
  `load` and `transform` in sequence, and close any `duckdb` shell on the file first — otherwise
  it fails with `IO Error: Could not set lock on file`.
- **A failed dlt load leaves a pending package**, and until it is retried or dropped the next
  run ignores new data.
- **`loaded_at_field` in the sources YAML must be literal SQL** — it is rendered at parse time
  where project macros are not visible.
- **The architecture diagrams under `docs/architecture/` still show BigQuery and Lightdash.**
  They have not been regenerated since the move to DuckDB.
- dbt-core is pinned `<2` on purpose — see `docs/versions.md` before raising it.
