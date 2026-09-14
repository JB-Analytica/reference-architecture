# How the pieces fit

The diagram below (and the SVG/PNG further down this page) predates this move and still shows
BigQuery and Lightdash, not DuckDB and Evidence. The stack that actually runs today:

```
source_system/webshop.dbml
        │  model2data: synthetic, relationship-preserving data
        ▼
DuckDB file  ── stands in for the operational database
        │  dlt: sql_database source, incremental, merge on primary key
        ▼
warehouse/refarch.duckdb  raw_webshop.*   ← landed exactly as the source had it, plus dlt lineage
        │  dbt: staging → intermediate → marts
        ▼
warehouse/refarch.duckdb  refarch_staging / _intermediate / _marts   ← same file, different schemas
        │  Evidence: reads the marts, builds a static site
        ▼
evidence/build/   ← HTML + parquet; serve it, no backend needed
```

Both the raw layer and every dbt layer live in the one DuckDB file — dlt and dbt just write
different schemas into it. Evidence is a fourth stage on top, not part of the file: it reads the
marts through four passthrough queries and writes its own output to `evidence/build/`.

## The one seam that matters

Everything above the DuckDB file that stands in for the source is *replaceable*. Point
`webshop_source()` in `refarch/pipelines/webshop.py` at a real Postgres, MySQL or SQL Server and
the DBML and model2data simply drop out — the same `sql_database` source, the same incremental
hints. Nothing downstream changes.

The warehouse itself is the other end of that same idea. dlt's destination and the dbt target in
`profiles.yml` are both one-line changes — swap `duckdb` for BigQuery, Snowflake or another
warehouse dlt and dbt both support, and everything from staging upward is unchanged.

That is the property the whole repo is built around: you can develop and demonstrate the entire
stack with no database access at all, then swap one connection string.

## Layer by layer

**Source model (`source_system/webshop.dbml`).** A Belgian specialty-coffee webshop. The DBML
is the only description of the source system; the note hints on columns (`weights`, `skew`,
`distribution`, `after`) are what make the data behave like a business — a Q4 peak, a
cancellation rate around 5%, a minority of customers placing most orders, no order shipped
before it was placed.

**Extraction (`refarch/pipelines/webshop.py`).** dlt's generic `sql_database` source. Every
table merges on `id`, so re-running never duplicates a row; mutable tables page on `updated_at`
and the append-only `order_items` pages on its key. dlt's `_dlt_load_id` is enabled explicitly
(the pyarrow backend omits it by default) because it is what dbt source freshness reads.

**Transformation (`dbt/`).** Staging renames and casts, one model per source table, no joins.
Intermediate holds the one piece of arithmetic two marts both need — line items rolled up to
order grain. Marts are `dim_`/`fct_` and are the only layer anything downstream may read.

**Semantic layer (`dbt/models/marts/`).** Column definitions live in dbt, not in a BI tool's UI.
`net_amount_eur`, `is_cancelled`, `days_to_ship` and `lifetime_net_revenue_eur` each mean one
thing, are code-reviewed, and travel with the repo. Evidence has no semantic layer of its own, so
these mart columns are now the whole of it — Lightdash's `meta:` metric blocks, which used to
declare `sum`/`count` aggregations once in this YAML, have been deleted. What survives that
switch and what does not is worth being precise about: the column definitions still live in one
reviewed place, but the aggregations that turn columns into headline numbers — `sum`, `count`,
the two ratios on the index page — are now written directly in each Evidence page's SQL. They are
still in git and still reviewed in the same pull request as everything else, but there is no
longer a single declarative place a metric is defined once and reused everywhere; a second page
that wants net revenue writes its own `sum(net_amount_eur)`.

**Exposure control.** `dbt_project.yml` tags every mart `bi`. Evidence's four source queries
(`evidence/sources/refarch/*.sql`) each select from exactly one mart, so that tag is the same
boundary it always was: staging and intermediate models stay in the warehouse for lineage and
debugging and are never the layer the report or an analyst is pointed at.

## Money

The source stores money in integer cents, which is right for an operational database and wrong
for a chart axis. The `cents_to_eur` macro converts exactly once, at the mart boundary. No
model downstream of that sees cents, and no chart divides by 100.

## Dialect ports

Moving the warehouse off BigQuery meant porting a few pieces of SQL rather than just the
connection. `dbt/macros/title_case.sql` exists because DuckDB has no `initcap`: it splits each
value on spaces and capitalises the first character of each word, mirroring what BigQuery gave
for free. `fct_orders.sql` uses `date_diff('hour', ...)` in place of BigQuery's
`timestamp_diff`, and the sources YAML's `loaded_at_field` was rewritten for DuckDB's timestamp
functions — it stays literal SQL either way, for the reason in the runbook.

## The diagram

**Stale.** `diagram.svg`, `diagram.png`, `diagram-v2.png` and `diagram-v2.html` below still show
the BigQuery/Lightdash version of this stack and have not been regenerated for the move to
DuckDB, nor for the addition of Evidence as the fourth stage. They are kept as a record of the
previous architecture rather than removed; treat the "How the pieces fit" diagram above this
section as the current one.

![Reference architecture](diagram.svg)

Source: [`diagram.svg`](diagram.svg), sized to the 1600×900 diagram canvas in the
JB Analytica design system, using the chart *marks* palette for the distinct stages and a single
amber accent for the swap point. [`diagram.png`](diagram.png) is a raster export
for slides and social.

The SVG names Poppins and JetBrains Mono with the design system's documented fallbacks, so it
renders correctly in a browser and degrades to Helvetica where those fonts are not installed —
which is what the committed PNG shows. Install the two fonts locally if you need a raster export
in the brand faces.

### Two versions

`diagram.svg` is hand-authored: navy ground, the four stages as numbered boxes, the story
carried by a full-height amber seam. `diagram-v2.html` is the same argument redrawn through
the `diagram-design` skill against a saved JB Analytica profile — light editorial ground,
orthogonal elbow connectors, masked arrow labels, a bottom legend strip and a `<title>`/`<desc>`
accessibility contract. The skill's geometry and render linters both pass on it.

The v2 file was drawn with the [diagram-design](https://github.com/factory-ai/diagram-design)
skill against a JB Analytica colour profile. That profile is not committed here, so regenerating
it elsewhere falls back to the skill's own palette; the committed HTML already carries the
brand values inline.
