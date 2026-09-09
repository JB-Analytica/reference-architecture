# Versions and why they are pinned there

Every library is at its latest **stable** release as of 2026-09-09, with one deliberate
exception explained below. `uv.lock` is committed, so a fresh clone gets exactly what was
tested here.

| Library | Pinned | Why |
|---|---|---|
| dlt | 1.30.0 | latest |
| dbt-core | 1.12.4 | latest stable; see below |
| dbt-bigquery | 1.12.0 | latest |
| model2data | 1.7.1 | latest |
| duckdb / duckdb-engine | 1.5.5 / 0.17.0 | latest |
| Lightdash CLI | 2.177.0 | latest; needs **Node >= 24** |
| Node | 24.x | required by the Lightdash CLI's `upload` / `download` |

## The Lightdash CLI needs Node 24

`@lightdash/cli` 2.177.0 refuses to run `upload` and `download` on anything below Node 24 —
`deploy` still works on Node 20, so a stack that only publishes the semantic layer will appear
fine until the first time someone tries to sync content as code.

Install Node 24 alongside whatever else is on the machine rather than replacing it:

```bash
brew install node@24            # keg-only: does not touch an existing node
export PATH="/opt/homebrew/opt/node@24/bin:$PATH"
```

Note that `lightdash` and `@lightdash/cli` are **different npm packages**. The one this project
uses is `@lightdash/cli`; the unscoped `lightdash` package is unrelated and its version numbers
do not line up.

## A second reason to keep the CLI current

Version 0.2158.0 supported dbt 1.4-1.10 and *interactively prompted* on anything newer, which
hangs forever wherever there is no terminal — a CI job, or an agent. 2.177.0 both handles dbt
1.12 and provides `--assume-yes`, which `refarch deploy` passes so no prompt can ever block a
run. It also takes `--project`, which the deploy passes explicitly: the CLI's saved default
project can be a leftover preview, and deploying to the wrong project is worse than failing.

## Why not dbt-core 2.0

dbt-core 2.0 exists on PyPI, but as of 2026-09-09 the newest build is `2.0.0rc2` — a release
candidate, published 8 September. It is not a final release.

More decisive than its own status is the adapter. `dbt-bigquery` 1.12.0, the current stable
adapter, declares `dbt-core>=1.10.0rc0,<2.0`. It therefore refuses to install against 2.0 at
all. The only adapter that accepts dbt-core 2.0 today is `dbt-bigquery` **1.11.1b1**, itself
a beta.

So running this stack on dbt 2.0 means a release-candidate core plus a beta adapter. For a repo
whose whole point is that someone else can clone it and have it run, that trade is not worth
making for features nothing here needs yet.

It is, however, one command to try:

```bash
uv run --prerelease=allow --with 'dbt-core>=2.0.0rc2' --with 'dbt-bigquery>=1.11.1b1' dbt build
```

That combination has been checked far enough to confirm it resolves and that the BigQuery
adapter imports; it has **not** been run against the warehouse here.

When dbt-core 2.0 is released and a stable `dbt-bigquery` 2.x follows, the change is to raise
the two floors in `pyproject.toml` and re-lock. Nothing in the models or the semantic layer is
expected to need edits.
