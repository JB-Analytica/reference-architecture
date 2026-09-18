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
| @evidence-dev/evidence | 40.1.8 | latest |
| @evidence-dev/duckdb | 2.0.1 | latest |
| typescript, svelte, vite, … | exact | pinned by Evidence; see below |

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

Run that way, 55 of 68 nodes pass, `fct_orders` fails and the twelve nodes behind it are
skipped:

```
Catalog Error: Scalar Function with name date does not exist!
LINE 28:         date(orders.ordered_at) as order_date,
```

`date()` is a perfectly ordinary DuckDB function and works in a plain 1.5.5 session, so this is
something about how 2.0 and the current adapter dispatch SQL between them, not a bug in the
model. It was not chased further: the pin is justified by the release-candidate status alone,
and the failure only confirms it.

These counts move whenever a model or a test is added; re-run the trial rather than trusting
the numbers above. The node count is deliberately stated in only two places — here and the
README's "What success looks like" — because it was previously in four and had drifted in all
of them.

The constraint is written twice on purpose. `pyproject.toml` decides what the virtualenv
installs; `dbt/dbt_project.yml`'s `require-dbt-version` decides what is allowed to run the
project at all, including a system `dbt` that never went through uv — which would otherwise
build these models on an untested version and say nothing. `tests/test_dbt_project.py` fails if
the two ever stop accepting the same versions. Note that `<2.0.0` still admits `2.0.0rc2`,
because a release candidate sorts below its own release; that is what keeps the trial above
runnable.

When dbt-core 2.0 is released and a `dbt-duckdb` that is tested against it follows, the change
is to raise the floors in `pyproject.toml` **and** `dbt/dbt_project.yml`, re-lock, and re-run
the trial above. Nothing in
the models or the semantic layer is expected to need edits.

## Why dbt charts is pinned to an exact version

`ci.yml` runs `uvx --from dbt-charts==0.8.0`, not a floating range. dbt charts was announced on
14 September 2026 and 0.8.0 shipped the day after; it is explicitly pre-1.0, its YAML surface has
already moved enough that a stale board trips a schema-migration warning, and its compiler rejects
unknown keys -- so an unpinned upgrade would fail CI on a board nobody touched.

Raise it deliberately: bump the pin, run `dct validate --strict` and `dct render` locally, and
read the release notes for board-schema changes. `charts/README.md` records which behaviours the
spike depends on, including two workarounds (the euro axis expression and the inlined brand fonts)
that a release could invalidate.

## Fonts

Poppins and JetBrains Mono are vendored into `evidence/static/fonts` (sixteen woff2 files, 212 KB)
rather than loaded from a CDN, so the built report has no third-party runtime dependency and works
offline. They are copies of `JB-Analytica/jba-website`'s `assets/fonts/`; if the site changes its
faces, re-copy them and the `@font-face` block in `evidence/app.css` together.

## Why evidence/package.json pins so much

Evidence declares thirteen **exact** peer dependencies — `typescript@5.4.2`, `svelte@4.2.19`,
`vite@5.4.21` and so on. npm will not install the project without them present at those exact
versions, and the error it gives names one conflict at a time. They are listed in
`evidence/package.json` for that reason, not because this project has an opinion about any of
them. When Evidence is upgraded, re-read its `peerDependencies` and replace the whole set.

## Why `npm audit` reports vulnerabilities

It reports 31, seven of them critical, and none of them are fixable here or reach anything this
project ships. They are worth understanding rather than ignoring:

- Every one is in Evidence's **build toolchain** — vitest, vite's dev server, minimatch, nanoid,
  the markdown parser. `evidence build` emits static HTML and parquet; there is no server
  process in the output for these to be exploited in.
- Some are not even in the code path. The worst-rated, `@sveltejs/adapter-node`'s
  `BODY_SIZE_LIMIT` bypass, applies to the Node adapter; this project builds through
  `@sveltejs/adapter-static`. The vitest advisory needs its UI server running, which nothing
  here starts.
- They cannot be fixed downstream. The versions are pinned by Evidence's own exact peers, so
  `npm audit fix --force` would break the install rather than repair it.

CI deliberately does not gate on `npm audit`: it would fail permanently on upstream issues this
repo cannot act on, and a check that is always red teaches people to ignore checks. The risk that
does remain is a poisoned build-time dependency, which is why `package-lock.json` is committed
and CI installs with `npm ci` rather than `npm install`.
