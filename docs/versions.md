# Versions and why they are pinned there

Every library is at its latest **stable** release as of 2026-09-09, with one deliberate
exception explained below. `uv.lock` is committed, so a fresh clone gets exactly what was
tested here.

| Library | Pinned | Why |
|---|---|---|
| dlt | 1.30.0 | latest |
| dbt-core | 1.12.4 | latest stable; see below |
| dbt-duckdb | 1.11.0 | latest that accepts dbt-core `<2` |
| model2data | 1.7.1 | latest |
| duckdb / duckdb-engine | 1.5.5 / 0.17.0 | latest |

## Why not dbt-core 2.0

dbt-core 2.0 exists on PyPI, but as of 2026-09-09 the newest build is `2.0.0rc2` — a release
candidate, published 8 September. It is not a final release.

The adapter is not the obstacle: `dbt-duckdb` 1.11.0 requires only `dbt-core>=1.8.0`, with no
upper bound, and the two resolve together cleanly. The obstacle is that the project does not
build on it. Trial it with:

```bash
cd dbt && DBT_PROFILES_DIR=$PWD REFARCH_WAREHOUSE=../warehouse/refarch.duckdb \
  uv run --with 'dbt-core==2.0.0rc2' --prerelease=allow dbt build
```

Note the invocation: `refarch transform` will **not** pick the override up. The `refarch` console
script is pinned to the project virtualenv, and `_dbt_env` puts that interpreter's bin directory
first on PATH — by design, so a stray shim cannot win — which means the child `dbt` is the
project's 1.12.4 no matter what `uv run --with` layers on top. Check the `Running with dbt=`
line in the output before believing a trial result.

Run that way, 54 of 64 nodes pass and `fct_orders` fails:

```
Catalog Error: Scalar Function with name date does not exist!
LINE 28:         date(orders.ordered_at) as order_date,
```

`date()` is a perfectly ordinary DuckDB function and works in a plain 1.5.5 session, so this is
something about how 2.0 and the current adapter dispatch SQL between them, not a bug in the
model. It was not chased further: the pin is justified by the release-candidate status alone,
and the failure only confirms it.

When dbt-core 2.0 is released and a `dbt-duckdb` that is tested against it follows, the change
is to raise the two floors in `pyproject.toml`, re-lock, and re-run the trial above. Nothing in
the models or the semantic layer is expected to need edits.
