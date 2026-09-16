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

## What did not

- **No locale.** The `currency` presets are dollar-only and there is no locale setting. The
  `FormatConfig` `prefix:` escape hatch works on KPI value slots but is rejected on a cartesian
  axis, so euro axes carry the symbol in the axis title and the render emits
  `WARN-LIKELY-CURRENCY-OR-PERCENT-MISSING-FORMATTER`, suppressed above. For a euro report this
  is the sharpest edge.
- **Brand fonts cannot be registered.** `style.font.family` takes a family *name*; there is no
  hook for a `@font-face` or a woff2 file. The rendered HTML embeds dbt Charts' own faces (Inter
  Variable, Source Serif 4, Source Code Pro) and emits `font-family: Poppins` with no font
  behind it, so it silently falls back to whatever the viewer has. Evidence self-hosts all
  sixteen brand faces under `evidence/static/fonts` precisely so the report never depends on
  that. PNG/SVG output needs the font installed on the rendering machine -- with Poppins absent
  the whole board renders in an oblique fallback.
- **Custom palettes are not theme roles.** `style.palettes` maps a role to a *shipped* palette
  name only; brand hexes go under `style.charts.color.categorical`, which works but is not the
  same cascade a theme role gets.
- **Pre-1.0.** 0.8.0, released 14 Sep 2026. The compiler rejects unknown keys, which is good,
  but the YAML surface moved recently enough that a stale file already trips a schema-migration
  warning.
