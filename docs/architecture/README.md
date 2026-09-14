# How the pieces fit

The diagram below (and the SVG/PNG further down this page) predates this move and still shows
BigQuery and Lightdash. The stack that actually runs today is shorter by one stage:

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
```

Both the raw layer and every dbt layer live in the one DuckDB file — dlt and dbt just write
different schemas into it. There is no fifth stage: the marts are the end of the pipeline until a
BI front end is chosen (see the README's [Front end](../../README.md#front-end) section).

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

**Semantic layer (`dbt/models/marts/_marts__models.yml`).** Metrics live in dbt, not in a BI
tool's UI. `net_revenue_eur` means one thing, is code-reviewed, and travels with the repo. The
YAML still carries Lightdash's `meta:` syntax, kept as-is because the definitions themselves are
the substance and a replacement front end has not been chosen yet — see the README.

**Exposure control.** `dbt_project.yml` tags every mart `bi`. There is no BI tool reading that
tag today, but the intent is unchanged: staging and intermediate models stay in the warehouse
for lineage and debugging and are never the layer a BI tool or an analyst is pointed at.

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
DuckDB. They are kept as a record of the previous architecture rather than removed; treat the
"How the pieces fit" diagram above this section as the current one.

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
