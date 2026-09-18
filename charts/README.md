# dbt Charts spike

A spike, not a replacement. `webshop_performance.yml` rebuilds the Evidence report's performance
page (`evidence/pages/performance.md`) as a dbt Charts board, against the same DuckDB file and
the same marts, so the two can be compared honestly -- same four headline figures, same three
charts, same three sections.

```bash
uv tool install dbt-charts
uv run refarch run --target prod       # the board reads the prod marts
cd dbt && DBT_TARGET=prod uv run dbt parse && cd ..   # writes target/manifest.json
cd charts
mkdir -p renders                       # dct render does not create the output directory
dct validate webshop_performance.yml
dct render webshop_performance.yml --format html --output renders/webshop.html
```

`dbt parse` is a prerequisite, not a nicety: without `dbt/target/manifest.json` every `ref()`
in the board is unresolvable. It needs no warehouse and no credentials, and `refarch transform`
writes the same file as a side effect of building.

## What held up

- **No account, no Node.** `uv tool install dbt-charts` and `dct` is all of it. DuckDB is a
  first-class source type -- reached here through the dbt profile, but either way it reads
  `warehouse/refarch.duckdb` straight off disk exactly as Evidence does.
- **The marts stay the semantic layer.** Queries select from `fct_orders` and nothing else, so
  the repo's "column definitions live in dbt, never in a report page" rule survives intact.
  They reach it through `{{ ref('fct_orders') }}`, not a table name -- see below.
- **Hosting is simpler than Evidence.** `--format html` emits one self-contained file: no
  external scripts, no `fetch`, no root-absolute asset paths, fonts inlined as `@font-face`. The
  `--base-path` dance Evidence needs to live under `/reference-architecture` has no equivalent
  here because nothing is absolute -- and unlike the Evidence build, it opens over `file://`.
- **Prose sits between charts**, so the narrative pages port rather than degrade into a grid.

## The two rough edges, and what they cost to fix

### Euro formatting -- solved, with a caveat worth reading

`dct validate` and `dct render` both exit 0, with no CLI flags and no `warnings_ignore`
anywhere in the board. Nothing is suppressed.

Getting there is not obvious. There is no locale in the package; every `currency` preset is
hardcoded to a dollar (`currency_whole` is `$,.0f`); d3-format's grammar has exactly one
currency symbol, `$`, so `parse("€,.0f")` raises; and the `FormatConfig` `prefix:` that works
on a KPI value slot is rejected on a cartesian axis, as is a `style.formats` alias. Every
documented route is closed.

The way through is a Vega expression on the label text:

```yaml
axis_y:
  labels:
    format: currency_whole
    expr: "'€' + format(datum.value, ',.0f')"
```

**The `format: currency_whole` under it is load-bearing, not leftover.**
`WARN-LIKELY-CURRENCY-OR-PERCENT-MISSING-FORMATTER` inspects the *declared* format rather than
the painted string, so without it the render warns. The two lines deliberately disagree -- the
format says dollars, the expression paints euros. Delete one and you either get a warning or a
dollar-signed euro chart.

That second failure is the trap worth knowing about: `format: currency_whole` alone renders
`$20,000` over euro data, at exit 0, with no warning at all.

Upstream issue, for a first-class fix (a theme-level currency symbol, or `FormatConfig`
accepted on an axis): dbt-labs/dbt-charts#27.

### Brand fonts -- fixed, with one caveat

`embed_brand_fonts.py` puts the real Poppins bytes behind the name dbt Charts emits:

```bash
dct render webshop_performance.yml --format html --output renders/webshop.html
python embed_brand_fonts.py renders/webshop.html
```

dbt Charts vendors its families in a closed registry (`dbt_charts/core/fonts.py`: "adding a
font means adding a row") with no `@font-face` hook, so `style.font.family: Poppins` emits a
bare `font-family: Poppins` backed by nothing and falls back silently. The script appends one
`<style>` block to `<head>` with the four used weights inlined as base64 woff2, taken from
`evidence/static/fonts` -- the faces the Evidence report already self-hosts. Verified in a
browser: Poppins 400/500/600 load and paint, and the file stays self-contained (753 KB -> 0.8
MB, zero external references). Re-running is a no-op.

The caveat is real: dbt Charts measures text with the metrics of the family it believes it is
painting, then the browser paints Poppins, which is wider. On this board nothing clipped --
checked every `<text>` against its `<svg>` viewport, zero overflows -- but a denser board
could. Check before trusting it.

It also only fixes HTML. PNG/SVG go through vl-convert, which needs the font installed on the
machine doing the rendering; with Poppins absent the whole board renders in an oblique
fallback.

## What the dbt project link buys, measured

`dbt_charts.yml` names the dbt project (`dbt_project_dir: ../dbt`) and takes its connection from
the profile (`type: dbt_profile`) rather than pointing at `warehouse/refarch.duckdb` by path. Two
consequences, both checked on 18 September 2026 against dbt charts 0.8.0:

**One place says where the warehouse is.** The board no longer repeats the DuckDB path or the
`refarch_marts` schema. `ref()` resolves the schema out of the manifest, and `profiles.yml`
resolves the file -- so `DBT_TARGET`, `REFARCH_WAREHOUSE` and the dev/prod split keep working for
the report exactly as they do for dbt. Rendering through the profile was verified end to end.

**A renamed mart column fails before `dbt run`.** This is the one thing dbt charts does that
Evidence structurally cannot. `evidence/sources/refarch/*.sql` are raw selects against table
names; a renamed column there surfaces as a broken build or a broken page. Here it surfaces in
`dct validate`, with no warehouse connection at all:

```
ERR-DBT-MODEL-COLUMN-MISSING  Query 'revenue_by_channel' references column 'sales_channel'
of dbt model 'fct_orders', but the model's SQL does not produce it.
Hint: Did you mean 'channel'?
```

That was produced by renaming `sales_channel` to `channel` in `fct_orders.sql` and running
`dbt parse` -- no `dbt run`, no rebuilt warehouse, which still held the old column. dbt charts
derives the model's output columns statically from the SQL recorded in the manifest.

### The one new trap: the manifest's target decides the schema

`ref()` resolves to the relation recorded in `target/manifest.json`, so the target the manifest
was parsed against and the target the board connects to have to agree. Parse against dev, render
against `target: prod`, and every query goes looking for `refarch_dev_marts.fct_orders` in a
warehouse that only has `refarch_marts`:

```
Catalog Error: Table with name "refarch_dev_marts.fct_orders" does not exist
```

Hardcoding `schema: refarch_marts` could not produce that; reaching the mart through `ref()` can.
It fails loudly rather than reading the wrong data, and `DBT_TARGET=prod` in front of `dbt parse`
is the whole fix -- in the commands above and in the CI step -- but it is a second place where
the target has to be said, and it is easy to hit once.

Already filed upstream by someone else, on Snowflake, where it is worse: dbt-labs/dbt-charts#9
reports the same mismatch serving data from the wrong *database* silently, because there the
relation resolved. Ours failed loudly only because the dev schema does not exist in this file.

### What it cost: the marts no longer end `select * from final`

dbt charts cannot see through a trailing `*`. With the standard dbt idiom in place it reported
`WARN-DBT-MODEL-COLUMNS-UNRESOLVED` for all five queries -- *"a `*` projection hides the model's
column list; column references against it were not checked"* -- and skipped the check rather than
guessing. Right call, feature doing nothing.

The fix turned out to be cheaper than expected. The `final` CTE was already an explicit
projection; it only needed unwrapping, so the last `select` of the file *is* that projection:

```sql
-- before                          -- after
final as (                         )
    select                         select
        orders.order_id,               orders.order_id,
        ...                            ...
)                                  from orders
                                   left join order_money using (order_id)
select * from final
```

No column list is duplicated, and macro calls in projection position (`{{ cents_to_eur(...) }}`,
`{{ sentence_case(...) }}`) do not block derivation as long as each one is aliased. All four
marts were unwrapped this way; `dbt build` passes 69 of 69, including both reconciliation tests,
so nothing about the output changed. The rule is written down in `CLAUDE.md` next to the other
warehouse conventions.

With that done, `dct validate --strict` is clean, the rename above fails it, and CI runs it in
the `checks` job -- before the pipeline job builds a warehouse for the column to be missing from.

Filed upstream as dbt-labs/dbt-charts#40: the projection inside the `final` CTE is fully static
and sqlglot already resolves a `select *` against a CTE in the same statement, so the tool could
see through the idiom its own style guide recommends. If it lands, the mart rewrite stops being
load-bearing and stays only on its own merits.

## Still open

- **Custom palettes are not theme roles.** `style.palettes` maps a role to a *shipped* palette
  name only; brand hexes go under `style.charts.color.categorical`, which works but is not the
  same cascade a theme role gets.
- **dbt charts Cloud cannot read this warehouse, and never will.** The hosted product connects
  only to BigQuery, Postgres, Redshift and Snowflake -- there is no DuckDB or MotherDuck
  connection type to pick, so a local file is out and a MotherDuck account would not help
  either. For this repo that costs nothing: the deliverable is a static build published the
  same way the Evidence report already is, and `--format html` makes that *easier*, not harder.
  It is worth knowing for clients, and it is a fair signal about where DuckDB sits in dbt Labs'
  commercial attention.
- **Board discovery does not find boards next to their own project config.** With
  `dbt_charts.yml` inside `charts/`, a bare `dct validate` looks for `charts/charts/` and reports
  ERR-INTERNAL. CI names the board file explicitly (`--project-dir charts webshop_performance.yml`);
  a second board means a second line until the spike either dies or moves its config to the repo
  root, which is the layout the tool expects.
- **Pre-1.0.** 0.8.0, released 15 Sep 2026; the project was announced on 14 Sep. The compiler rejects unknown keys, which is good,
  but the YAML surface moved recently enough that a stale file already trips a schema-migration
  warning.
