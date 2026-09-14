# reference-architecture

A runnable reference stack: DBML → model2data → dlt → DuckDB → dbt → Evidence. It is published
as a worked example, so changes should hold up as one — readable and honest, not just working.

It runs with no accounts and no credentials: `git clone`, `uv sync`, `uv run refarch run`. That
constraint is the point, not a convenience — protect it. A change that reintroduces a required
secret, a cloud project or a paid service puts the whole example back behind a signup. Node is
the one extra prerequisite, and only for the report stage; the first three stages run on `uv`
alone and `refarch report` says so when npm is missing.

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
- `evidence/` — the report. `pages/` are the dashboards, `sources/refarch/` the queries that
  feed them. `package-lock.json` is committed; `node_modules/`, `.evidence/` and `build/` are not.

## Conventions specific to this repo

- **Column definitions live in dbt, never in a report page.** `net_amount_eur`, `is_cancelled`
  and `days_to_ship` are computed in the marts; an Evidence page may group and sum them, but it
  may not redefine what they mean. Evidence has no semantic layer of its own, so the marts are
  it — see `docs/architecture/README.md`.
- **Evidence source queries are thin.** `evidence/sources/refarch/*.sql` select from a mart and
  nothing else. Logic there is invisible to dbt's tests and lineage.
- **Brand values come from the website, never from judgement.** The colours in
  `evidence.config.yaml`, the `@font-face` block in `evidence/app.css` and the assets in
  `evidence/static/` all trace to `JB-Analytica/jba-website` (`assets/css/style.css`,
  `assets/fonts/`, `assets/images/`). If a colour is needed that the site does not define, take
  it from the site's palette and say in a comment that it was derived — do not invent a hue. The
  site's accessibility choices come with it: `--orange` is a fill, `--orange-text` is for text.
- **Only marts are exposed to the report**, via the `bi` tag that `dbt_project.yml` applies to
  the marts folder. Do not tag a staging or intermediate model, and do not point an Evidence
  source at one.
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
- **Evidence pins thirteen exact peer dependencies** (`typescript@5.4.2`, `svelte@4.2.19`, …).
  They are in `evidence/package.json` because npm refuses to install without them, and npm
  reports one conflict at a time. On an Evidence upgrade, re-read its `peerDependencies` and
  replace the whole set.
- **Evidence resolves a source's `filename` against that source's own folder** and overwrites any
  `directory` it is given, so the warehouse can only be named relative to
  `evidence/sources/refarch/`. `refarch report` computes that relative path; do not "simplify" it
  to an absolute one.
- **The published report is a project site, so it lives under `/reference-architecture`.** Any
  asset referenced from a page or from `app.css` must go through SvelteKit's `base` (or a
  relative url() Vite can rewrite) — a root-absolute path works locally and 404s in production.
  `refarch report --base-path` writes the value in for the build and takes it out again; never
  commit it.
- **The built report needs a web root, not `file://`.** Its asset URLs are absolute from the
  site root. Serve it with `npm run preview`; opening `build/index.html` directly renders it
  unstyled.
- **`npm audit` reports criticals that cannot be fixed here** and do not reach the built site —
  see `docs/versions.md` before acting on them. CI does not gate on it, deliberately.
- dbt-core is pinned `<2` on purpose — see `docs/versions.md` before raising it.
