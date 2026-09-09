# How the pieces fit

```
source_system/webshop.dbml
        │  model2data: synthetic, relationship-preserving data
        ▼
DuckDB file  ── stands in for the operational database
        │  dlt: sql_database source, incremental, merge on primary key
        ▼
BigQuery  raw_webshop.*          ← landed exactly as the source had it, plus dlt lineage
        │  dbt: staging → intermediate → marts
        ▼
BigQuery  refarch_staging / _intermediate / _marts
        │  Lightdash: reads the dbt YAML as its semantic layer
        ▼
Lightdash explores, charts, dashboards
```

## The one seam that matters

Everything above the DuckDB file is *replaceable*. Point `webshop_source()` in
`refarch/pipelines/webshop.py` at a real Postgres, MySQL or SQL Server and the DBML and
model2data simply drop out — the same `sql_database` source, the same incremental hints.
Nothing downstream changes.

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

**Semantic layer (`dbt/models/marts/_marts__models.yml`).** Metrics live in dbt, not in
Lightdash's UI. `net_revenue_eur` means one thing, is code-reviewed, and travels with the repo.
Lightdash reads this YAML directly, so the BI tool has no separate definition to drift from.

**Exposure control.** `dbt_project.yml` tags every mart `lightdash`, and `refarch deploy`
sets the project's table selection to that tag. Staging and intermediate models stay in
BigQuery for lineage and debugging but never appear to a BI user.

## Money

The source stores money in integer cents, which is right for an operational database and wrong
for a chart axis. The `cents_to_eur` macro converts exactly once, at the mart boundary. No
model downstream of that sees cents, and no chart divides by 100.

## The diagram

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
