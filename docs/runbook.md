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
| Build and test the models (dev schemas) | `uv run refarch transform` |
| Build them where the report reads | `uv run refarch transform --target prod` |
| Build one model and its parents | `uv run refarch transform build -s +fct_orders` |
| Check source freshness | `uv run refarch transform source freshness` |
| Build the report | `uv run refarch report` |
| Serve the report with hot reload | `uv run refarch report --dev` |
| Everything, in order | `uv run refarch run` |
| Everything except the report | `uv run refarch run --skip-report` |
| Lint, types, tests | `uv run poe check` |
| Open the warehouse | `duckdb warehouse/refarch.duckdb` |
| Preview the pull-request review locally | `dbt-preflight run --base-ref origin/main` |

`refarch transform` passes any extra arguments straight through to dbt, so anything dbt can do
is available without a second entry point. Inside the DuckDB shell, `show all tables` lists the
whole warehouse — the raw layer dlt wrote and every schema dbt built — because it is all one
file.

The report always reads the **prod** marts. Evidence's source queries name `refarch_marts`
literally and Evidence gives a query no way to read an environment variable, while
`refarch transform` on its own defaults to the `dev` target and builds `refarch_dev_marts`. So
`transform` then `report` will not show you what you just built unless the transform ran with
`--target prod`. `refarch report` checks the schema is there and says so, rather than failing
several minutes later inside a Node build.

`refarch report` needs Node 18 or newer (`npm` on `PATH`); the other three stages need only
`uv`. If `npm` is missing it says so and exits — `duckdb warehouse/refarch.duckdb` still works
against whatever `transform` already built. The built report is a static site at
`evidence/build/index.html`. Serve it -- `npm run preview` from `evidence/`, or any static
file server. Opening it straight off the filesystem does not work: the asset URLs are absolute
from the site root, so over `file://` they resolve to the root of your disk and the page loads
unstyled. The published copy is at https://reference.jbanalytica.com/.

`dbt-preflight` is not a dependency of this project — it runs in CI from
[its own action](https://github.com/JB-Analytica/dbt-preflight). To run it here before pushing,
install it once with `uv tool install dbt-preflight`. With `--base-ref` it reports only what the
branch changed; without one it builds every model and checks every one against the conventions,
which is the way to see where the project stands as a whole. Either way it writes its fixtures
and a throwaway DuckDB file to `.preflight/` and deletes them afterwards — it never touches
`warehouse/refarch.duckdb`, so it is safe to run while the real warehouse is open.

## Changing the data model

1. Edit `source_system/webshop.dbml`.
2. `uv run refarch generate` — model2data reports any hint it could not apply, before
   generating a single row.
3. `uv run refarch load` — dlt evolves the warehouse schema for added columns on its own.
4. Update the staging model and its YAML, then `uv run refarch transform`.

The generation is deterministic: the same DBML and seed always produce the same rows, so a
regeneration that changes data you did not expect to change is a signal, not noise.

The same DBML feeds dbt-preflight in CI, so a change here changes the fixtures every pull request
is reviewed against. Preflight treats an edit to it as a change to every source and rebuilds
everything, which is what you want: a new column or a changed hint can move any model.

## Things that have already cost time

**`cents_to_eur` needs its parentheses.** The macro expands to `round(({{ column }}) / 100, 2)`.
An earlier version omitted the inner parentheses, so a compound argument got operator precedence
instead of a conversion: `cents_to_eur('a - b')` became `a - b / 100`. Single columns and
products were unaffected, which is why it survived -- `a * b / 100` is still correct. It was
`fct_order_items.net_amount_eur` (100x too high) and `dim_products.unit_margin_eur` (500x) that
were wrong, and nothing failed: the numbers were plausible per row and absurd only in aggregate,
where one coffee SKU out-earned the entire business. The test in `dbt/tests/` now catches it by
cross-checking two columns that must agree.

**An inner join to an optional child silently changes a count.** `dim_customers` joined
`int_orders__items_aggregated` with an inner join, which looks harmless until you notice the
synthetic source produces orders with no line items at all. Those orders vanished from
`lifetime_order_count`, which claimed in its own description to be every non-cancelled order and
was 11% short of one. The money was right, so the reconciliation test passed: both sides agreed
on €0. Counts need their own evidence.

**A model can be uniformly wrong and pass every column test.** `not_null`, `unique` and
`accepted_values` all held while `fct_order_items.net_amount_eur` was a hundred times too large:
each row was individually plausible. What catches that class of bug is comparing two numbers
computed independently by different models, which is what
`dbt/tests/assert_marts_reconcile.sql` does. It has been watched to fail, which is the only
thing that makes it a test: drop the inner parentheses from `cents_to_eur`, run
`refarch transform --target prod`, and it goes red on `fct_orders vs fct_order_items (booked)`
with 3,564 rows (the realised-revenue test fails alongside it). Put the parentheses back. A
regression test nobody has seen fail is not yet a test, so do that again after changing either.

**Booked and realised revenue are different columns, on purpose.** `net_amount_eur` is the order
as placed; `realised_net_amount_eur` is zero when the order was cancelled. Sum the realised one
for revenue. Before they were split, `fct_orders` counted cancelled orders as revenue while
`dim_customers` quietly excluded them -- the same word, two numbers, five percent apart.

**A failed dlt load leaves a pending package.** Until it is retried or dropped, the next run
ignores new data. `refarch load` says so on failure; `dlt pipeline webshop info` shows the
package.

**`days_to_ship` follows `shipped_at`, not `order_status`.** The two are independent in the
generated source: 600 orders sit at cancelled, paid or pending while carrying a shipping
timestamp. The column used to require a shipped/delivered status as well, which threw all 600
away and made its own description ("null while unshipped") untrue. A shipping timestamp is what
means an order shipped; `is_cancelled` is on the same row for anyone who wants cancellations out.

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
