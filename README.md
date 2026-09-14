# Reference architecture

A complete, running analytics stack that you can clone and run against a local DuckDB file with
no account and no credentials. Only the report stage needs anything beyond `uv` — see
[What you need first](#what-you-need-first). It points at a real warehouse by changing one
connection string.

![Four stages left to right — a synthetic source system, dlt, a DuckDB warehouse file, dbt, and an Evidence report published to GitHub Pages — with two dashed seams either side of dlt marking the only swap points](docs/architecture/diagram.svg)

`model2data` → `dlt` → DuckDB → `dbt` → `Evidence`. Every layer is real and every layer runs;
nothing here is a sketch of how it would work. The stack ends at a static report you can open in
a browser, built from the same DuckDB file the dbt run left behind.

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

**Column definitions live in dbt, not in a BI tool.** `net_amount_eur`, `is_cancelled`,
`days_to_ship` and the rest of the columns the report charts are defined once in the mart SQL,
reviewed in a pull request, and read by Evidence without being redefined — see
[The report](#the-report).

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
| [uv](https://docs.astral.sh/uv/) | runs generate, load and transform | `brew install uv`, or the official installer |
| Node 18 or newer | runs the report | developed against Node 20; `brew install node` |

The first three stages need only `uv`: there is nothing to sign up for, nothing to pay for, and
no `.env` you have to fill in before the first run. Node is only needed for the fourth stage, the
Evidence report. If `npm` is not on your `PATH`, `refarch report` says so and exits, and you can
still inspect everything the pipeline produced with `duckdb warehouse/refarch.duckdb`.

## Quick start

```bash
uv sync --extra dev
uv run refarch run --target prod
```

No `.env`, no credentials, no account. `refarch run` generates the synthetic source, loads it,
builds and tests every dbt model, and builds the static report, all against a DuckDB file at
`warehouse/refarch.duckdb`. The whole run takes about 43 seconds from a clean clone.
`.env.example` documents two optional overrides (`DBT_TARGET`, `REFARCH_WAREHOUSE`); copy it to
`.env` only if you want to change one of them. Pass `--skip-report` to stop after dbt if you do
not have Node installed.

### The four stages

| Stage | Command | What happens |
|---|---|---|
| 1 | `refarch generate` | model2data builds the synthetic source system as a DuckDB file |
| 2 | `refarch load` | dlt loads it into the warehouse, incrementally, merging on the primary key |
| 3 | `refarch transform` | dbt builds and tests staging → intermediate → marts |
| 4 | `refarch report` | Evidence builds the static report over the warehouse into `evidence/build` |

`refarch transform` passes extra arguments straight through to dbt, so
`refarch transform build -s +fct_orders` and `refarch transform source freshness` both work.
`refarch report --dev` serves the report with hot reload instead, for writing pages.

### What success looks like

A finished run builds 64 dbt nodes — 4 table models, 5 view models, 54 data tests and 1 unit
test — all passing, against roughly 4,000 orders and around €346,600 in net revenue that grows
visibly month over month. Re-running the load adds no duplicate rows, because every table merges
on its primary key. Open the warehouse with `duckdb warehouse/refarch.duckdb`, then
`show all tables` — the file holds the raw layer and every dbt schema together. Open the report
at https://jb-analytica.github.io/reference-architecture/, or build it and serve it locally
with `npm run preview` from `evidence/`.

## The report

The stack used to end at Lightdash, which has no DuckDB connector and so could not make the move;
it was removed along with `refarch/lightdash_api.py`, the `lightdash/` directory and the `deploy`
command. Its replacement is [Evidence](https://evidence.dev/), chosen over Rill Developer and
dbt's own MetricFlow for one reason: `evidence build` emits a self-contained static site — HTML
plus a handful of parquet files, about 87 MB, most of it the DuckDB WASM bundle that lets the
browser query the parquet directly. A reader can see the dashboards without running anything,
which the other two candidates cannot do.

The report lives in `evidence/`. `evidence/pages/` holds four pages — `index.md` (net revenue,
orders, average order value and cancellation rate, plus net revenue by month and by channel,
order status mix, and average days to ship by month), `products.md` (top ten products by net
revenue), `customers.md` (top twenty customers, plus lifetime net revenue by segment) and
`cancellations.md` (rate and lost revenue over time, by channel and by product). The first three
carry the nine figures this stack used to publish to Lightdash; the fourth is new.
`evidence/sources/refarch/` holds the connection and four thin passthrough queries, one per mart.

### Revenue

Revenue means **realised** revenue, and the marts say so in the column names. `fct_orders` and
`fct_order_items` each carry `net_amount_eur` — the order as placed, cancellations included —
next to `realised_net_amount_eur`, which is zero when the order was cancelled.
`dim_customers.lifetime_realised_net_revenue_eur` is realised too.

They are separate columns rather than one column and a filter because a filter is something a
reader has to remember, and this repo had already proved that they do not: `fct_orders` used to
count cancelled orders as revenue while `dim_customers` quietly excluded them, so the same word
meant two numbers five percent apart depending on which mart you asked. Both are stored per row
so both stay additive — summing either is correct at any grain, and the cancellation rate
re-derives correctly when rolled up from day to month, which a stored ratio would not.
`dbt/tests/` pins the pair against `is_cancelled`.

Evidence has no semantic layer of its own, so the trade from the Lightdash days is real: the dbt
marts are now the semantic layer for column definitions — `net_amount_eur`, `is_cancelled`,
`days_to_ship`, `lifetime_realised_net_revenue_eur` are all defined once in mart SQL and Evidence pages
only group and sum them — but the aggregations themselves (`sum`, `count`, the two ratios) are
now written in each page's SQL rather than declared once in YAML. They are still in git and still
code-reviewed, but there is no single declarative metric definition the way Lightdash's `meta:`
blocks were, and those blocks have been deleted from
`dbt/models/marts/_marts__models.yml` rather than kept around unused.

### Brand

The report carries JB Analytica's own look rather than Evidence's default, and every value is
taken from the website's stylesheet rather than eyeballed:

- **Type.** Poppins and JetBrains Mono, the faces jbanalytica.com uses. The `@font-face` block in
  `evidence/app.css` is lifted verbatim from the site's `assets/css/style.css` with only the
  `url()` paths rewritten, and all sixteen files are self-hosted under `evidence/static/fonts`,
  so the built report stays self-contained and never calls a font CDN.
- **Colour.** `evidence.config.yaml` maps the site's CSS custom properties onto Evidence's theme
  tokens. Two of them are deliberately not the obvious choice, and the file says why: `primary`
  is `--link-blue`, not `--bright-blue`, and `accent` is `--orange-text`, not `--orange`, because
  the brand keeps a separate darker orange for accent text that clears 4.5:1 on light grounds.
  The chart palette is derived from the brand colours and stops there rather than being padded
  out with invented hues.
- **Marks.** The wordmark in the header and the full favicon set are the site's own assets. The
  wordmark is cropped to its content box, because the source PNG carries enough transparent
  padding to render it about half size at the header's 20px height.

Three files carry it: `evidence.config.yaml` (colour), `evidence/app.css` (type) and
`evidence/tailwind.config.cjs` (font family). `evidence/pages/+layout.svelte` puts the wordmark in
the header. What is not themed is Evidence's layout chrome — the sidebar, the spacing, the
table and chart furniture are Evidence's, and the brand sits on top of them rather than replacing
them.

### Published

The report is published to GitHub Pages on every push to `main`:

**https://jb-analytica.github.io/reference-architecture/**

`.github/workflows/pages.yml` runs all four stages and deploys `evidence/build`, so what is
live is built from the DBML upwards by the same commands a reader runs locally — there is no
checked-in copy of the report to drift out of date.

A project site is served from `/<repo>` rather than the domain root, so the build needs
`--base-path`. That value is deliberately not committed: `refarch report --base-path /x` writes
it into `evidence.config.yaml` for the build and takes it out again, because a committed base
path would make every asset URL absolute under `/x` and break the local preview. Pull requests
do not publish; they get the report as a downloadable artifact from `ci.yml` instead.

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
- `dbt/` — the dbt project. Marts carry the column definitions the report reads.
- `evidence/` — the Evidence project: `pages/` and `sources/refarch/`. `build/` is git-ignored.
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
every push and pull request. `pipeline` sets up Node 20, installs Evidence's dependencies, then
runs the full stack — generate, load, transform, report, source freshness — on every pull
request too, and uploads two artifacts: `warehouse` (the DuckDB file) and `report` (the built
static site — unzip it and serve the folder). That is only possible because
the warehouse is a file: there is no account to hold a secret for, so the job runs the same way
on a fork as it does here.

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
[DuckDB](https://duckdb.org/), [dbt](https://www.getdbt.com/) and [Evidence](https://evidence.dev/).
