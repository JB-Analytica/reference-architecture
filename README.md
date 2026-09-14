# Reference architecture

A complete, running analytics stack that you can clone and run with nothing installed but `uv` —
no account, no credentials, no `.env`. It stands up on a laptop against a local DuckDB file, and
points at a real warehouse by changing one connection string.

![The reference architecture: two interchangeable sources meeting at one swap point, then dlt, BigQuery, dbt and Lightdash](docs/architecture/diagram.svg)

*The diagram above still shows the BigQuery/Lightdash version of this stack — it has not been
redrawn for the DuckDB move (see [docs/architecture/README.md](docs/architecture/README.md)).
The running code is now `model2data` → `dlt` → DuckDB → `dbt`.*

`model2data` → `dlt` → DuckDB → `dbt`. Every layer is real and every layer runs; nothing here is
a sketch of how it would work. There is no BI layer wired up yet — see
[Front end](#front-end) — so the stack currently ends at a queryable warehouse file, not a
dashboard.

It is published as something to read and take apart. Clone it, run it, disagree with the layering,
copy the bits that are useful. It is a worked example rather than a library, so there is no package
to install and no API to keep stable.

## Why it is built this way

**The source system is synthetic, and that is the point.** Most reference architectures either
ship a static CSV, which teaches you nothing about incremental loading, or need access to a
production database, which you usually do not have when you start. Here,
[model2data](https://github.com/JB-Analytica/model2data) turns `source_system/webshop.dbml` into a
real, relationship-preserving database with a Q4 peak, a realistic cancellation rate and a
long-tailed order distribution. The pipeline that reads it is `dlt`'s generic `sql_database`
source — the same one you would point at Postgres.

**Metrics live in dbt, not in a BI tool.** `net_revenue_eur` and the rest of the semantic layer
are defined once in `dbt/models/marts/_marts__models.yml`, reviewed in a pull request, and
survive whichever front end eventually reads them — see [Front end](#front-end).

**Only the marts are exposed.** Every mart carries the `bi` tag from `dbt_project.yml`, so
staging and intermediate models stay available for lineage and debugging but are never the
thing a BI tool or an analyst points at.

**Data that behaves like a business.** Uniformly random test data hides the bugs that matter: it
will never show you a dashboard that breaks in December, or the query that falls over on your
largest account. The generated orders grow across the window, peak in Q4, cancel about 5% of the
time, and concentrate on a minority of customers. All of it is deterministic, so the same schema
and seed always produce the same rows.

## What you need first

| Requirement | Why | Notes |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | runs everything Python | `brew install uv`, or the official installer |

That's the whole list. The warehouse is a DuckDB file the pipeline creates itself, so there is
nothing to sign up for, nothing to pay for, and no `.env` you have to fill in before the first
run.

## Quick start

```bash
uv sync --extra dev
uv run refarch run --target prod
```

That's it — no `.env`, no credentials, no account. `refarch run` generates the synthetic source,
loads it, and builds and tests every dbt model, all against a DuckDB file at
`warehouse/refarch.duckdb`. `.env.example` documents two optional overrides
(`DBT_TARGET`, `REFARCH_WAREHOUSE`); copy it to `.env` only if you want to change one of them.

### The three stages

| Stage | Command | What happens |
|---|---|---|
| 1 | `refarch generate` | model2data builds the synthetic source system as a DuckDB file |
| 2 | `refarch load` | dlt loads it into the warehouse, incrementally, merging on the primary key |
| 3 | `refarch transform` | dbt builds and tests staging → intermediate → marts |

`refarch transform` passes extra arguments straight through to dbt, so
`refarch transform build -s +fct_orders` and `refarch transform source freshness` both work.

### What success looks like

A finished run builds 64 dbt nodes — 4 table models, 5 view models, 54 data tests and 1 unit
test — all passing, against roughly 4,000 orders and around €346,600 in net revenue that grows
visibly month over month. Re-running the load adds no duplicate rows, because every table merges
on its primary key. Open the result with `duckdb warehouse/refarch.duckdb`, then
`show all tables` — the file holds the raw layer and every dbt schema together.

## Front end

There is no BI layer wired up. The stack used to end at Lightdash, but Lightdash has no DuckDB
connector, so it could not make the move and was removed along with `refarch/lightdash_api.py`,
the `lightdash/` directory and the `deploy` command. The metric definitions in
`dbt/models/marts/_marts__models.yml` were kept — they are the substance of a semantic layer —
but they still carry Lightdash's `meta:` syntax pending a replacement, which has not been chosen.
Candidates under consideration include [Evidence.dev](https://evidence.dev/),
[Rill Developer](https://www.rilldata.com/) and dbt's own MetricFlow, all of which can read a
DuckDB file directly. Until one is picked, `duckdb warehouse/refarch.duckdb` is the front end.

## Working on it

```bash
uv run poe check     # ruff, ty and pytest
uv run pytest        # tests alone — no warehouse needed
```

The pipeline tests run dlt for real against a temporary DuckDB file, so the extraction logic
including incremental merge is covered by the same kind of file the real run produces.

## Layout

- `source_system/` — the DBML data model. The only description of the source system.
- `refarch/` — the Python package: config, the model2data wrapper, the dlt pipeline, the CLI.
- `dbt/` — the dbt project. `models/marts/_marts__models.yml` carries the semantic layer.
- `tests/` — pytest, mirroring the package.
- `docs/` — [architecture](docs/architecture/README.md), [runbook](docs/runbook.md),
  [versions](docs/versions.md).

`source_system/generated/`, `warehouse/`, `.env` and `dbt/target/` are git-ignored. The generated
data and the warehouse file are both deterministic and disposable, so they are rebuilt rather
than committed.

## Pointing it at a real database

The synthetic source exists so the stack can run before you have access to anything. Replacing it
is the whole design, and it is a two-part change:

1. Point `webshop_source()` in [refarch/pipelines/webshop.py](refarch/pipelines/webshop.py) at your
   own database — it takes a SQLAlchemy URL and a list of tables — and delete `source_system/`,
   `refarch/generate.py` and the `generate` command.
2. Swap the dlt destination and the dbt target: point dlt at BigQuery, Snowflake or Postgres
   instead of `duckdb`, and add the matching target to `dbt/profiles.yml`. That is a one-line
   change in each place plus the dialect-specific adapter (`dbt-bigquery`, `dbt-snowflake`, …).

Everything from staging upward is unchanged either way. That property is the reason the repo is
shaped this way — the seam sits at exactly one place, the dlt destination and the dbt target,
and nothing above it needs to know which warehouse it is talking to.

## Automation

One GitHub Actions workflow, `ci.yml`, with two jobs. `checks` runs lint, types and tests on
every push and pull request. `pipeline` then runs the full stack — generate, load, transform,
source freshness — on every pull request too, and uploads the resulting
`warehouse/refarch.duckdb` as a downloadable artifact. That is only possible because the
warehouse is a file: there is no account to hold a secret for, so the job runs the same way on a
fork as it does here.

## Cost

Nothing. The warehouse is a local file, so there is no account to bill and no query cost to
think about. Every run reads and writes `warehouse/refarch.duckdb` and nothing else.

## Versions

Every library is at its latest stable release, with `uv.lock` committed. dbt-core 2.0 is
deliberately *not* used: it is still a release candidate, and the only adapter that accepts it is a
beta. See [docs/versions.md](docs/versions.md) for the reasoning and the one-line command to trial
it anyway.

## Licence

[MIT](LICENSE) — use it, change it, ship it.

## Credits

Built and maintained by [JB Analytica](https://www.jbanalytica.com/), on top of
[model2data](https://github.com/JB-Analytica/model2data), [dlt](https://dlthub.com/),
[DuckDB](https://duckdb.org/) and [dbt](https://www.getdbt.com/).
