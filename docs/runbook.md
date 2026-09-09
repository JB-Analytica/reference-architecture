# Runbook

## First run on a new machine

```bash
uv sync --extra dev
cp .env.example .env      # then point GOOGLE_APPLICATION_CREDENTIALS at a service-account key
brew install node@24                       # the CLI needs Node >= 24
export PATH="/opt/homebrew/opt/node@24/bin:$PATH"
npm install -g @lightdash/cli@2.177.0
lightdash login https://app.lightdash.cloud
uv run refarch run --target prod
```

The service account needs **BigQuery Job User** and **BigQuery Data Editor** on the project.

## Day to day

| Task | Command |
|---|---|
| Regenerate the source data | `uv run refarch generate` |
| Load it into BigQuery | `uv run refarch load` |
| Build and test the models | `uv run refarch transform` |
| Build one model and its parents | `uv run refarch transform build -s +fct_orders` |
| Check source freshness | `uv run refarch transform source freshness` |
| Publish to Lightdash | `uv run refarch deploy` |
| Everything, in order | `uv run refarch run` |
| Lint, types, tests | `uv run poe check` |

`refarch transform` passes any extra arguments straight through to dbt, so anything dbt can do
is available without a second entry point.

## Changing the data model

1. Edit `source_system/webshop.dbml`.
2. `uv run refarch generate` — model2data reports any hint it could not apply, before
   generating a single row.
3. `uv run refarch load` — dlt evolves the BigQuery schema for added columns on its own.
4. Update the staging model and its YAML, then `uv run refarch transform`.

The generation is deterministic: the same DBML and seed always produce the same rows, so a
regeneration that changes data you did not expect to change is a signal, not noise.

## Preview environments

`lightdash start-preview --name my-branch` builds a throwaway Lightdash project from the
current branch's dbt. Useful for reviewing a semantic-layer change before it reaches the main
project. `lightdash stop-preview --name my-branch` removes it.

## Things that have already cost time

**Changing a dlt setting that adds a required column.** BigQuery cannot add a required field to
an existing table, and dlt's merge disposition keeps a second `<dataset>_staging` dataset. Drop
**both** datasets and clear `.dlt/pipelines/` before reloading, or the load fails on the staging
table with a schema error.

**A failed dlt load leaves a pending package.** Until it is retried or dropped, the next run
ignores new data. `refarch load` says so on failure; `dlt pipeline webshop info` shows the
package.

**`loaded_at_field` cannot call a project macro.** It is rendered at parse time in a restricted
context, so the freshness expression in `_webshop__sources.yml` is literal SQL.

**The Lightdash CLI needs Node 24** for `upload` and `download`, though `deploy` runs on
Node 20. A stack that only deploys the semantic layer looks healthy right up until the first
content sync fails.

**The Lightdash CLI shells out to `dbt`.** If a pyenv shim wins the PATH race, the deploy fails
with a Python version error that has nothing to do with Lightdash. `refarch deploy` puts its own
interpreter's bin directory first to prevent this; running `lightdash deploy` by hand outside
the CLI needs the same care.
