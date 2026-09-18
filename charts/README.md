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

### The catch: it is inert on this repo's mart SQL as it stands

Every mart here ends with the standard dbt idiom:

```sql
select * from final
```

dbt charts cannot see through that. It reports `WARN-DBT-MODEL-COLUMNS-UNRESOLVED` for each
query -- *"a `*` projection hides the model's column list; column references against it were not
checked"* -- and skips the check rather than guessing, which is the right call but leaves the
feature doing nothing. Five warnings, exit 0 (they only fail under `--strict`).

Replacing that last line in `fct_orders.sql` with an explicit 21-column projection made all five
warnings disappear and turned the rename above into the error quoted. **That change is not in
this branch**: dropping `select * from final` across the marts is a change to the house SQL style
of a repo published as a worked example, and it should be decided on its own merits rather than
smuggled in as a dependency's requirement. Until it is decided, the link is worth having for the
single-source-of-truth half, and the column check is latent.

The narrower fix belongs upstream: the projection inside the `final` CTE *is* explicit, and
sqlglot can resolve a trailing `select *` through a CTE. Worth an issue alongside
dbt-labs/dbt-charts#27.

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
- **Not in CI yet.** `dct validate --strict` in the pull-request job is the obvious next step,
  but it would fail today on the five unresolved-columns warnings. It goes in when the mart
  projection question above is settled, not before.
- **Pre-1.0.** 0.8.0, released 15 Sep 2026; the project was announced on 14 Sep. The compiler rejects unknown keys, which is good,
  but the YAML surface moved recently enough that a stale file already trips a schema-migration
  warning.
