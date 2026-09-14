# How the pieces fit

The stack that runs today, in text; the drawing at the bottom of this page says the same thing:

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

Two things the generator cannot express are worth stating rather than discovering. It spreads
child rows over parents without guaranteeing every parent gets one, so about one order in nine
has no line items — real rows worth €0 that pull the average order value down by roughly a
tenth. And it draws each column independently, so an order's `status` and its `shipped_at` are
uncorrelated: some cancelled and some still-pending orders carry a shipping timestamp. Neither
is a bug in this repo and neither can be fixed from the DBML; both are the reason a stack that
only ever ran against this data has not really been tested.

**Extraction (`refarch/pipelines/webshop.py`).** dlt's generic `sql_database` source. Every
table merges on `id`, so re-running never duplicates a row; mutable tables page on `updated_at`
and the append-only `order_items` pages on its key. dlt's `_dlt_load_id` is enabled explicitly
(the pyarrow backend omits it by default) because it is what dbt source freshness reads.

**Transformation (`dbt/`).** Staging renames and casts, one model per source table, no joins.
Intermediate holds the one piece of arithmetic two marts both need — line items rolled up to
order grain. Marts are `dim_`/`fct_` and are the only layer anything downstream may read.

**Semantic layer (`dbt/models/marts/`).** Column definitions live in dbt, not in a BI tool's UI.
`net_amount_eur`, `realised_net_amount_eur`, `is_cancelled`, `days_to_ship` and
`lifetime_realised_net_revenue_eur` each mean one thing, are code-reviewed, and travel with the
repo. That the names are long is the point: `net_amount_eur` alone used to mean the order as
placed in one mart and the order minus cancellations in another, and nothing in the name gave
that away. Evidence has no semantic layer of its own, so
these mart columns are now the whole of it — Lightdash's `meta:` metric blocks, which used to
declare `sum`/`count` aggregations once in this YAML, have been deleted. What survives that
switch and what does not is worth being precise about: the column definitions still live in one
reviewed place, but the aggregations that turn columns into headline numbers — `sum`, `count`,
the two ratios on the index page — are now written directly in each Evidence page's SQL. They are
still in git and still reviewed in the same pull request as everything else, but there is no
longer a single declarative place a metric is defined once and reused everywhere; a second page
that wants net revenue writes its own `sum(net_amount_eur)`.

**Display labels are part of that definition.** The source stores its enums lowercase and
snake_cased -- `mobile_app`, `light`, `cancelled` -- and each mart carries a `*_label` column
beside the raw one (`channel_label`, `roast_label`, `segment_label`, and so on), composed by the
`sentence_case` macro -- sentence case, because the rest of the site writes "Webshop
performance" and not "Webshop Performance". Charts and tables read the label; filters and joins
read the raw key. The alternative is each page casing its own axis labels, which is a page
redefining a value in
exactly the way the `bi` boundary exists to prevent -- and two pages eventually disagreeing about
what to call the same thing. `_marts__models.yml` declares each pairing as `meta.display_label`
and `tests/test_report.py` reads those declarations, so a page pointing `x=` or `id=` at a raw
enum fails the build rather than the review.

The report says a short version of all this to its own readers, on its `architecture` page
(`evidence/pages/architecture.md`) — someone who opens the published site never sees this file.
The two have to agree; this one is the source.

**Exposure control.** `dbt_project.yml` tags every mart `bi`. Evidence's four source queries
(`evidence/sources/refarch/*.sql`) each select from exactly one mart, so that tag is the same
boundary it always was: staging and intermediate models stay in the warehouse for lineage and
debugging and are never the layer the report or an analyst is pointed at.

Nothing about dbt or Evidence makes that boundary hold -- a source query naming
`refarch_staging.stg_webshop__orders` would have worked perfectly well, and moved a column
definition out of the layer that is supposed to own it. `tests/test_dbt_project.py` closes it:
it reads `dbt_project.yml` and the source queries directly (no manifest, no warehouse) and fails
if the `bi` tag moves, if a source query reads a non-mart, or if one so much as mentions an
upstream model by name.

## Money

The source stores money in integer cents, which is right for an operational database and wrong
for a chart axis. The `cents_to_eur` macro converts exactly once, at the mart boundary. No
model downstream of that sees cents, and no chart divides by 100.

**Euros are DECIMAL, and the conversion never goes through a float.** Every figure on the report
is an exact number of cents, so none of it has any business being approximate -- but the macro
used to return `round(cents / 100, 2)`, which is a DOUBLE. Exact per row; not exact once summed,
because floating point addition is not associative and a total therefore depends on the order the
rows happen to be read in. That order is a property of the table, not of the data. Honduras
medium roast beans total exactly 9313.50 euro of realised revenue; adding an unrelated label
column to `fct_order_items` changed the physical row order, the same sum came out as
9313.499999999998 rather than 9313.50000000001, and the published figure moved from 9,314 to
9,313 while nothing about the money had changed.

`dbt/tests/assert_money_is_exact.sql` reads the warehouse's column types and fails if any mart
`*_eur` column is floating point. It deliberately checks the type rather than comparing values:
exactly one figure in this dataset sits on a boundary, and a test that only fires when a total
happens to land on a half cent is a test that passes for years and then does not.

## Dialect ports

Moving the warehouse off BigQuery meant porting a few pieces of SQL rather than just the
connection. `dbt/macros/sentence_case.sql` exists because DuckDB has no `initcap`: it
replaces underscores with spaces and capitalises the first character, which is what this site's
labels need -- BigQuery's `initcap` capitalises every word, which is not what we want here
anyway. `fct_orders.sql` uses `date_diff('hour', ...)` in place of BigQuery's
`timestamp_diff`, and the sources YAML's `loaded_at_field` was rewritten for DuckDB's timestamp
functions — it stays literal SQL either way, for the reason in the runbook.

## The diagram

![Reference architecture](diagram.svg)

`diagram.html` is the source; `diagram.svg` and `diagram.png` are exports of the `<svg>` node
alone, made with the `diagram-design` skill's export procedure. Regenerate them from the HTML
rather than editing either by hand.

What it argues: four stages, and **two seams either side of `dlt`**. That is the honest shape of
this repo's portability claim — `dlt` is the one component with both a replaceable input and a
replaceable output, so pointing the stack at a production database or a cloud warehouse means
changing those two things and nothing else. Accent is spent on the seams and nowhere else,
because they are the whole point of the drawing.

The fonts are embedded in the HTML as base64 woff2 — Poppins 400/600/700 and JetBrains Mono 400,
the only faces the diagram uses. That keeps the file self-contained: it renders in brand offline,
inside the PNG export, and without a call to a font CDN, which is the same stance the report
takes. The export carries those `@font-face` rules into the SVG's own `<defs>`, so the standalone
SVG does not substitute typography either.

There is deliberately only one diagram. Earlier drafts were deleted rather than parked beside
this one: two drawings of the same system, one of them out of date, is worse than one that is
right, and a reader has no way to tell which is which.
