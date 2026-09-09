# reference-architecture

A runnable reference stack: DBML → model2data → dlt → BigQuery → dbt → Lightdash. It is published
as a worked example, so changes should hold up as one — readable and honest, not just working.

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
  checked in and reads everything from environment variables.
- `lightdash/` — charts and dashboards as code.

## Conventions specific to this repo

- **Metrics are defined in `dbt/models/marts/_marts__models.yml`, never in the Lightdash UI.**
  A metric added through the UI is invisible to review and is lost on the next deploy.
- **Only marts are exposed to Lightdash**, via the `lightdash` tag that `dbt_project.yml`
  applies to the marts folder. `refarch deploy` enforces it through the API. Do not tag a
  staging or intermediate model.
- **Money is integer cents in the source and euros in the marts.** Convert with the
  `cents_to_eur` macro at the mart boundary only.
- **Layering and naming follow the staging / intermediate / marts convention** described in
  `docs/architecture/README.md`. Read that before adding a model.

## Gotchas

- **`.env` is required** for anything touching BigQuery. `GOOGLE_APPLICATION_CREDENTIALS` must
  be an absolute path to a service-account key with BigQuery Job User + Data Editor.
- **Changing a dlt setting that adds a required column breaks reloads.** BigQuery cannot add a
  required field to an existing table, and merge keeps a `<dataset>_staging` dataset too. Drop
  both datasets and `.dlt/pipelines/` before reloading.
- **A failed dlt load leaves a pending package**, and until it is retried or dropped the next
  run ignores new data.
- **`loaded_at_field` in the sources YAML must be literal SQL** — it is rendered at parse time
  where project macros are not visible.
- **The Lightdash CLI needs Node >= 24** for `upload`/`download` (`deploy` works on Node 20).
  Install with `brew install node@24`, which is keg-only and leaves any existing Node alone.
- **The Lightdash CLI shells out to `dbt`.** `refarch deploy` puts its own interpreter's bin
  directory first on PATH so a pyenv shim cannot win; keep that if you touch `_dbt_env`.
- dbt-core is pinned `<2` on purpose — see `docs/versions.md` before raising it.
