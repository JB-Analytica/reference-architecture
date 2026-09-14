# reference-architecture

A runnable reference stack: DBML → model2data → dlt → DuckDB → dbt → Evidence. It is published
as a worked example, so changes should hold up as one — readable and honest, not just working.

It runs with no accounts and no credentials: `git clone`, `uv sync`, `uv run refarch run`. That
constraint is the point, not a convenience — protect it. A change that reintroduces a required
secret, a cloud project or a paid service puts the whole example back behind a signup. Node is
the one extra prerequisite, and only for the report stage; the first three stages run on `uv`
alone and `refarch report` says so when npm is missing.

## Commands

```bash
uv sync --extra dev
uv run poe check                       # ruff + ty + pytest
uv run refarch run --target prod       # all four stages
uv run refarch transform build -s +fct_orders   # extra args pass through to dbt
```

## Layout

- `source_system/webshop.dbml` — the only description of the source system. Edit this, not the
  generated data.
- `source_system/generated/` — git-ignored. Deterministic; rebuild with `refarch generate`.
- `refarch/` — config, model2data wrapper, dlt pipeline, Typer CLI.
- `dbt/` — staging (one model per source table) → intermediate → marts. `profiles.yml` is
  checked in and needs no environment at all.
- `warehouse/` — git-ignored. The DuckDB file the stack builds; rebuild with `refarch run`.
- `evidence/` — the report. `pages/` are the dashboards, `sources/refarch/` the queries that
  feed them. `package-lock.json` is committed; `node_modules/`, `.evidence/` and `build/` are not.

## Conventions specific to this repo

- **Column definitions live in dbt, never in a report page.** `net_amount_eur`, `is_cancelled`
  and `days_to_ship` are computed in the marts; an Evidence page may group and sum them, but it
  may not redefine what they mean. Evidence has no semantic layer of its own, so the marts are
  it — see `docs/architecture/README.md`.
- **Evidence source queries are thin.** `evidence/sources/refarch/*.sql` select from a mart and
  nothing else. Logic there is invisible to dbt's tests and lineage.
- **The report reads the prod marts, always.** `evidence/sources/refarch/*.sql` name
  `refarch_marts` literally and Evidence gives a query no way to read an environment variable,
  while `refarch transform` defaults to the `dev` target. Build with `--target prod` before
  building the report; `refarch report` guards this and says so.
- **`docs/architecture/diagram.html` is the source of the diagram**; `diagram.svg` and
  `diagram.png` are exports of its `<svg>` node. Edit the HTML and re-export with the
  `diagram-design` skill — never hand-edit the SVG or the PNG, and never let the drawing and the
  prose in `docs/architecture/README.md` disagree. `evidence/static/architecture.svg` is a copy
  of the exported SVG, because Evidence can only serve files from `static/`; re-copy it whenever
  the diagram changes, or the test in `tests/test_cli.py` fails.
- **The report's home page is positioning, not a dashboard.** `evidence/pages/index.md`
  introduces JB Analytica, the invented business the project is built around, and the problem it
  reproduces; the dashboard that used to live there is `performance.md`. Two rules for that page:
  anything said about JB Analytica must trace to jbanalytica.com, the same rule the brand colours
  follow, and nothing may read as a client engagement or a case study — this is a reference
  project, the webshop does not exist, and the page says both in its opening lines. Page order is
  set by `sidebar_position` frontmatter, not by filename.
- **The report explains itself on `evidence/pages/architecture.md`**, for readers who see the
  published site and never the repo. It has to stay in step with `docs/architecture/README.md`,
  which is the source of the two.
- **An Evidence `<Value>` must sit mid-line, and must be followed by a word.** Starting a line
  with one makes markdown treat it as its own block and splits the paragraph around it. Following
  one directly with a comma or full stop renders a space before the punctuation, because the
  component puts the number on its own line inside its `<span>` and the newline collapses to a
  trailing space — there is no prop for it and CSS cannot strip it. `tests/test_report.py` fails
  on both.
- **`docs/img/report.png` is a screenshot, so it goes stale silently.** Re-take it whenever the
  report's look changes: build the report, serve `evidence/build` over HTTP (the asset URLs need
  a web root), and capture `/performance` with Playwright at a 1440x900 viewport and
  `device_scale_factor=1` — viewport only, not `full_page`. Keep it under 500 KB or
  `check-added-large-files` blocks the commit.
- **Concrete run figures (node counts, revenue totals) live in two places only** — the README's
  "What success looks like" and `docs/versions.md`. They were previously repeated in the diagram
  and elsewhere and had drifted everywhere. Re-measure rather than copy.
- **Brand values come from the website, never from judgement.** The colours in
  `evidence.config.yaml`, the `@font-face` block in `evidence/app.css` and the assets in
  `evidence/static/` all trace to `JB-Analytica/jba-website` (`assets/css/style.css`,
  `assets/fonts/`, `assets/images/`). If a colour is needed that the site does not define, take
  it from the site's palette and say in a comment that it was derived — do not invent a hue. The
  site's accessibility choices come with it: `--orange` is a fill, `--orange-text` is for text.
- **Only marts are exposed to the report**, via the `bi` tag that `dbt_project.yml` applies to
  the marts folder. Do not tag a staging or intermediate model, and do not point an Evidence
  source at one. `tests/test_dbt_project.py` enforces both, so this fails CI rather than review.
- **The dbt-core constraint lives in two files** — `pyproject.toml` (what uv installs) and
  `dbt/dbt_project.yml`'s `require-dbt-version` (what is allowed to run the project, including a
  system dbt). Change both; a test fails if they stop accepting the same versions.
- **Warehouse SQL is DuckDB SQL.** No `initcap`, no `timestamp_diff`, no `safe_divide`. Where
  a dialect gap needs papering over, add a macro next to `cents_to_eur` and `title_case` rather
  than inlining the workaround.
- **Money is integer cents in the source and euros in the marts.** Convert with the
  `cents_to_eur` macro at the mart boundary only. The macro parenthesises its argument; keep it
  that way. Without the parentheses `cents_to_eur('a - b')` expanded to `a - b / 100`, which
  divided only the last term and silently inflated two mart columns by 100x and 500x.
- **"Revenue" means realised revenue.** `fct_orders` and `fct_order_items` carry both
  `net_amount_eur` (the order as placed, cancellations included) and `realised_net_amount_eur`
  (zero when cancelled); `dim_customers.lifetime_realised_net_revenue_eur` is realised too. Sum
  the realised column for any revenue figure. Do not add a third money column without deciding
  which of the two it is, and do not store a ratio per row -- ratios must re-derive from
  additive parts or they break on roll-up. `dbt/tests/` pins the pair against the flag.
- **Marts must reconcile with each other.** `dbt/tests/assert_marts_reconcile.sql` compares
  numbers two different models compute independently from the same cents: an order against the
  sum of its lines, a customer's lifetime against their realised orders. Column-level tests pass
  happily on a model that is uniformly wrong -- that is exactly how the `cents_to_eur` bug
  survived review. Add a cross-model check whenever a new mart derives money that another mart
  also derives.
- **Layering and naming follow the staging / intermediate / marts convention** described in
  `docs/architecture/README.md`. Read that before adding a model.

## Working on this repo

`main` is protected and the protection applies to admins too. Nothing reaches it except through a
pull request whose `Lint, types, tests` and `Full run` checks have passed: no direct pushes, no
force pushes, no deletions. Approvals are set to zero, so a solo maintainer can still merge their
own pull request — requiring one would lock the only admin out, because GitHub does not let you
approve your own. The Pages job (`publish`) is deliberately **not** a required check: it only runs
on pushes to `main`, so requiring it would leave every pull request waiting for a check that never
arrives.

## Gotchas

- **`.env` is optional and nothing in it is required.** Only `DBT_TARGET` and
  `REFARCH_WAREHOUSE` are read, and both have working defaults.
- **dlt and dbt share one DuckDB file**, and DuckDB locks it to a single writing process. Run
  `load` and `transform` in sequence, and close any `duckdb` shell on the file first — otherwise
  it fails with `IO Error: Could not set lock on file`.
- **A failed dlt load leaves a pending package**, and until it is retried or dropped the next
  run ignores new data.
- **`loaded_at_field` in the sources YAML must be literal SQL** — it is rendered at parse time
  where project macros are not visible.
- **Evidence pins thirteen exact peer dependencies** (`typescript@5.4.2`, `svelte@4.2.19`, …).
  They are in `evidence/package.json` because npm refuses to install without them, and npm
  reports one conflict at a time. On an Evidence upgrade, re-read its `peerDependencies` and
  replace the whole set.
- **Evidence resolves a source's `filename` against that source's own folder** and overwrites any
  `directory` it is given, so the warehouse can only be named relative to
  `evidence/sources/refarch/`. `refarch report` computes that relative path; do not "simplify" it
  to an absolute one.
- **Never assume where the published report sits.** It is on the custom domain
  `reference.jbanalytica.com` at the domain root, so the base path is currently empty; as a plain
  project site it would be `/reference-architecture`. `pages.yml` asks `actions/configure-pages`
  for the value, so this can change without a code edit. Any asset referenced from a page or from
  `app.css` must therefore go through SvelteKit's `base` (or a relative url() Vite can rewrite) —
  a root-absolute path works locally and 404s the moment a prefix exists. `refarch report
  --base-path` writes the value in for the build and takes it out again; never commit it.
- **The built report needs a web root, not `file://`.** Its asset URLs are absolute from the
  site root. Serve it with `npm run preview`; opening `build/index.html` directly renders it
  unstyled.
- **`npm audit` reports criticals that cannot be fixed here** and do not reach the built site —
  see `docs/versions.md` before acting on them. CI does not gate on it, deliberately.
- dbt-core is pinned `<2` on purpose — see `docs/versions.md` before raising it.
