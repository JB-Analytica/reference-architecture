# Runbook

## First run on a new machine

```bash
uv sync --extra dev
uv run refarch run --target prod
```

Nothing else is required. `.env` is entirely optional — see `.env.example` for the two variables
it can override (`DBT_TARGET`, `REFARCH_WAREHOUSE`); copy it only if you want to change one of
their defaults.

## Day to day

| Task | Command |
|---|---|
| Regenerate the source data | `uv run refarch generate` |
| Load it into the warehouse | `uv run refarch load` |
| Build and test the models | `uv run refarch transform` |
| Build one model and its parents | `uv run refarch transform build -s +fct_orders` |
| Check source freshness | `uv run refarch transform source freshness` |
| Build the report | `uv run refarch report` |
| Serve the report with hot reload | `uv run refarch report --dev` |
| Everything, in order | `uv run refarch run` |
| Everything except the report | `uv run refarch run --skip-report` |
| Lint, types, tests | `uv run poe check` |
| Open the warehouse | `duckdb warehouse/refarch.duckdb` |

`refarch transform` passes any extra arguments straight through to dbt, so anything dbt can do
is available without a second entry point. Inside the DuckDB shell, `show all tables` lists the
whole warehouse — the raw layer dlt wrote and every schema dbt built — because it is all one
file.

`refarch report` needs Node 18 or newer (`npm` on `PATH`); the other three stages need only
`uv`. If `npm` is missing it says so and exits — `duckdb warehouse/refarch.duckdb` still works
against whatever `transform` already built. The built report is a static site at
`evidence/build/index.html`; open it directly, no server needed.

## Changing the data model

1. Edit `source_system/webshop.dbml`.
2. `uv run refarch generate` — model2data reports any hint it could not apply, before
   generating a single row.
3. `uv run refarch load` — dlt evolves the warehouse schema for added columns on its own.
4. Update the staging model and its YAML, then `uv run refarch transform`.

The generation is deterministic: the same DBML and seed always produce the same rows, so a
regeneration that changes data you did not expect to change is a signal, not noise.

## Things that have already cost time

**A failed dlt load leaves a pending package.** Until it is retried or dropped, the next run
ignores new data. `refarch load` says so on failure; `dlt pipeline webshop info` shows the
package.

**`loaded_at_field` cannot call a project macro.** It is rendered at parse time in a restricted
context, so the freshness expression in `_webshop__sources.yml` is literal SQL.

**DuckDB is single-writer across processes.** `load` and `transform` both write the warehouse
file, so they have to run in sequence — which they already do, one after the other in
`refarch run`. (`generate` is unaffected: it writes the separate source-system file under
`source_system/generated/`.) The failure is a clear `IO Error: Could not set lock on file`, not
corruption. The usual cause is a `duckdb warehouse/refarch.duckdb` shell left open in another
terminal — close it and re-run.

**Evidence resolves a source's `filename` against that source's own folder, ignoring any
`directory` given to it.** That means the warehouse can only be named relative to
`evidence/sources/refarch/`, not by an absolute path. `refarch report` works around it by
computing that relative path itself and injecting it as
`EVIDENCE_SOURCE__refarch__filename`, so dbt (via `REFARCH_WAREHOUSE`) and Evidence always read
the same file no matter where `REFARCH_WAREHOUSE` points.

**`npm run sources` has to run before a build, or the report renders the previous run's
numbers.** It re-reads the warehouse and rewrites the parquet the pages query; skip it and
`evidence build` or `evidence dev` will silently show stale figures. `refarch report` always
runs it first, so this only bites if you drive Evidence directly from `evidence/`. See
[docs/versions.md](versions.md) for why `npm audit` reports vulnerabilities and why the peer
dependencies are pinned so exactly.
