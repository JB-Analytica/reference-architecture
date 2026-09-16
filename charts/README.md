# dbt Charts spike

A spike, not a replacement. `webshop_performance.yml` rebuilds the Evidence report's performance
page (`evidence/pages/performance.md`) as a dbt Charts board, against the same DuckDB file and
the same marts, so the two can be compared honestly -- same four headline figures, same three
charts, same three sections.

```bash
uv tool install dbt-charts
cd charts
dct validate webshop_performance.yml
dct render webshop_performance.yml --format html --output renders/webshop.html \
    --ignore-warning WARN-LIKELY-CURRENCY-OR-PERCENT-MISSING-FORMATTER
```

The warehouse must already be built (`uv run refarch run`).

## What held up

- **No account, no Node.** `uv tool install dbt-charts` and `dct` is all of it. DuckDB is a
  first-class source type, so it reads `warehouse/refarch.duckdb` straight off disk exactly as
  Evidence does.
- **The marts stay the semantic layer.** Queries select from `fct_orders` and nothing else, so
  the repo's "column definitions live in dbt, never in a report page" rule survives intact.
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

## Still open

- **Custom palettes are not theme roles.** `style.palettes` maps a role to a *shipped* palette
  name only; brand hexes go under `style.charts.color.categorical`, which works but is not the
  same cascade a theme role gets.
- **Pre-1.0.** 0.8.0, released 15 Sep 2026; the project was announced on 14 Sep. The compiler rejects unknown keys, which is good,
  but the YAML surface moved recently enough that a stale file already trips a schema-migration
  warning.
