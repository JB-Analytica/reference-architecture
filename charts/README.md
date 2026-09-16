# dbt Charts spike

A spike, not a replacement. `webshop_performance.yml` rebuilds the front page of the Evidence
report (`evidence/pages/index.md`) as a dbt Charts board, against the same DuckDB file and the
same marts, so the two can be compared honestly.

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

### Euro formatting -- fixed as far as the tool allows

`dct render` now exits 0 with no CLI flags. The board is the only place that knows about it.

The euro genuinely cannot reach a cartesian axis tick in 0.8.0, and the reason is structural
rather than a missing config key: `style.number_format` and `style.axis_y.labels.format` both
take a bare d3 spec, and **d3-format's grammar allows only `$` or `#` as the currency symbol**
-- `parse("€,.0f")` raises. The `FormatConfig` `prefix:` escape hatch that the KPIs use is
rejected on an axis (`str | preset` only). There is no locale setting anywhere in the package.

So the KPIs -- the numbers anyone actually reads off this page -- carry a real `€`, and the
axes put the unit in the axis title, which is where a unit belongs anyway. The
`WARN-LIKELY-CURRENCY-OR-PERCENT-MISSING-FORMATTER` heuristic wants to see a `$`; it is told
otherwise per chart via `warnings_ignore`, next to the comment explaining why, rather than
blanket-suppressed from the command line.

Worth an upstream issue: a `currency_symbol` on the theme, or `FormatConfig` accepted on an
axis, would close this for every non-dollar report.

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
