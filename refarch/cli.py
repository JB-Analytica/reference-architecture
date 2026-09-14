"""`refarch` -- one entry point that drives every stage of the reference architecture."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from refarch import generate as generate_stage
from refarch import seo
from refarch.config import (
    DBT_DIR,
    EVIDENCE_CONFIG,
    EVIDENCE_DIR,
    EVIDENCE_SOURCE_DIR,
    ROOT,
    settings,
)

app = typer.Typer(
    help="model2data -> dlt -> DuckDB -> dbt -> Evidence, stage by stage.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _dbt_env(target: str | None = None) -> dict[str, str]:
    """Environment for the dbt child process.

    The interpreter running this CLI owns the right dbt; without putting its bin directory
    first, a bare `dbt` resolves through whatever shim happens to be on PATH (pyenv, a system
    install) and fails or -- worse -- silently uses a different version.

    REFARCH_WAREHOUSE is passed explicitly so dbt opens the same DuckDB file dlt just wrote,
    whatever the caller's working directory.
    """
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    env["DBT_PROFILES_DIR"] = str(DBT_DIR)
    env["REFARCH_WAREHOUSE"] = str(settings().warehouse_path)
    if target:
        env["DBT_TARGET"] = target
    return env


def _run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    """Run a child command, surfacing its own output and exit code.

    The child (dbt, npm) has already printed a better diagnostic than any traceback of
    ours would be, so exit with its status instead of raising through Typer.
    """
    typer.secho("$ " + " ".join(cmd), fg=typer.colors.BLUE)
    result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command()
def generate() -> None:
    """Stage 1 -- generate the synthetic source system (model2data) as a DuckDB database."""
    generate_stage.generate()
    typer.secho("Source system ready.", fg=typer.colors.GREEN)


@app.command()
def load() -> None:
    """Stage 2 -- extract the source system into the warehouse with dlt (incremental, merge)."""
    from dlt.pipeline.exceptions import PipelineStepFailed

    from refarch.pipelines import webshop

    try:
        info = webshop.run(settings())
    except PipelineStepFailed as exc:
        # dlt keeps a failed package and retries it on the next run, which silently ignores
        # any new data. Say so here rather than letting the next run look like a no-op.
        typer.secho(f"dlt failed during {exc.step}: {exc.exception}", fg=typer.colors.RED, err=True)
        typer.secho(
            "The load package is still pending. Inspect it with `dlt pipeline webshop info`, "
            "then either retry `refarch load` or discard it with "
            "`dlt pipeline webshop drop-pending-packages`.",
            err=True,
        )
        raise typer.Exit(1) from exc
    typer.echo(info)
    typer.secho("Raw data loaded.", fg=typer.colors.GREEN)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def transform(
    ctx: typer.Context,
    target: str | None = typer.Option(None, help="dbt target (default: DBT_TARGET or dev)"),
) -> None:
    """Stage 3 -- `dbt build` the staging, intermediate and mart layers (extra args go to dbt)."""
    cmd = (
        ["dbt", "build", *ctx.args]
        if not ctx.args or ctx.args[0].startswith("-")
        else ["dbt", *ctx.args]
    )
    _run(cmd, cwd=DBT_DIR, env=_dbt_env(target))
    typer.secho("Transformations built.", fg=typer.colors.GREEN)


def _evidence_env() -> dict[str, str]:
    """Environment for the Evidence child process.

    Evidence resolves a source's `filename` against that source's own folder and ignores any
    `directory` handed to it, so an absolute path cannot be expressed: the override has to be
    the warehouse's path *relative to* evidence/sources/refarch. Computing it here means
    REFARCH_WAREHOUSE keeps working wherever it points, and dbt and Evidence cannot drift onto
    two different files.
    """
    env = dict(os.environ)
    warehouse = settings().warehouse_path.resolve()
    env["EVIDENCE_SOURCE__refarch__filename"] = os.path.relpath(warehouse, EVIDENCE_SOURCE_DIR)
    return env


# Evidence's source queries name the schema literally (`select * from refarch_marts.fct_orders`),
# and Evidence gives a query no way to read an environment variable. So the report can only ever
# read the prod marts -- while `refarch transform` defaults to the `dev` target, which builds
# refarch_dev_marts instead. Left alone that combination either fails deep inside a Node build
# with a DuckDB catalog error, or silently reports an older prod build's numbers.
MARTS_SCHEMA = "refarch_marts"


def _require_marts() -> None:
    """Fail early, and in our own words, when the prod marts the report reads are not there."""
    import duckdb

    warehouse = settings().warehouse_path
    if not warehouse.exists():
        typer.secho(
            f"No warehouse at {warehouse}. Run `refarch run --target prod` first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    con = duckdb.connect(str(warehouse), read_only=True)
    try:
        found = con.execute(
            "select count(*) from information_schema.schemata where schema_name = ?",
            [MARTS_SCHEMA],
        ).fetchone()
    finally:
        con.close()
    if not found or not found[0]:
        typer.secho(
            f"{warehouse} has no {MARTS_SCHEMA} schema, so the report has nothing to read.\n"
            "Evidence's source queries name that schema literally, so the report always reads "
            "the prod marts. `refarch transform` on its own defaults to the dev target and "
            "builds refarch_dev_marts. Run `refarch transform --target prod` (or "
            "`refarch run --target prod`) and try again.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)


def _require_npm() -> str:
    """Evidence is a Node application; this is the one stage `uv` alone cannot run."""
    npm = shutil.which("npm")
    if npm is None:
        typer.secho(
            "npm was not found. The report stage needs Node 18 or newer -- everything before "
            "it (generate, load, transform) runs without it. Install Node, or run the earlier "
            "stages and inspect the warehouse with `duckdb warehouse/refarch.duckdb`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    if not (EVIDENCE_DIR / "node_modules").exists():
        typer.secho("Installing Evidence's dependencies (first run only).", fg=typer.colors.BLUE)
        _run([npm, "ci"], cwd=EVIDENCE_DIR)
    return npm


@contextmanager
def _base_path(base_path: str | None) -> Iterator[None]:
    """Temporarily give Evidence a deployment base path.

    Evidence reads `deployment.basePath` from evidence.config.yaml and offers no environment
    override, but the value cannot simply be committed: a base path makes every asset URL
    absolute under it, which breaks opening build/index.html from the filesystem. So it is
    written for the duration of the build and taken out again afterwards.

    The original text is restored byte for byte rather than re-serialised, because
    evidence.config.yaml carries the comments explaining the brand colour choices and a YAML
    round-trip would drop every one of them.
    """
    if not base_path:
        yield
        return
    original = EVIDENCE_CONFIG.read_text()
    EVIDENCE_CONFIG.write_text(f"{original.rstrip()}\n\ndeployment:\n  basePath: {base_path}\n")
    try:
        yield
    finally:
        EVIDENCE_CONFIG.write_text(original)


@app.command()
def report(
    dev: bool = typer.Option(
        False, help="Serve with hot reload instead of building the static site."
    ),
    base_path: str | None = typer.Option(
        None,
        help="Build for a site served under this path, e.g. /reference-architecture for "
        "GitHub Pages. Must start with '/'.",
    ),
    site_url: str = typer.Option(
        seo.SITE_URL,
        help="Origin the report will be served from. Only the canonical, og:url and sitemap "
        "entries use it -- they have to be absolute, and nothing in the build knows the host.",
    ),
) -> None:
    """Stage 4 -- build the Evidence report over the warehouse (static site in evidence/build)."""
    if base_path and not base_path.startswith("/"):
        typer.secho(
            f"--base-path must start with '/' (got {base_path!r}). Evidence rejects it otherwise.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    _require_marts()
    npm = _require_npm()
    env = _evidence_env()
    with _base_path(base_path):
        # `sources` re-reads the warehouse and rewrites the parquet the report queries. Always
        # run it first, or the report silently renders the previous run's numbers.
        _run([npm, "run", "sources"], cwd=EVIDENCE_DIR, env=env)
        if dev:
            _run([npm, "run", "dev"], cwd=EVIDENCE_DIR, env=env)
            return
        _run([npm, "run", "build"], cwd=EVIDENCE_DIR, env=env)
    # Evidence cannot express absolute URLs, site-wide og tags, or the removal of its own
    # twitter:site default, so the built head is finished here. See refarch/seo.py.
    # An empty --site-url means the caller had nothing to offer (actions/configure-pages does
    # not always resolve an origin), not that the site has no host. Fall back rather than
    # writing a canonical URL with no scheme, which is worse than not writing one at all.
    origin = site_url.strip() or seo.SITE_URL
    routes = seo.finalise(EVIDENCE_DIR / "build", site_url=origin, base_path=base_path)
    typer.secho(
        f"Head, robots.txt and sitemap.xml written for {len(routes)} pages at {origin}.",
        fg=typer.colors.BLUE,
    )
    typer.secho(
        f"Report built into {EVIDENCE_DIR / 'build'}. Serve it with `npm run preview` from "
        "evidence/ -- its asset URLs are absolute from the site root, so opening index.html "
        "over file:// renders it unstyled.",
        fg=typer.colors.GREEN,
    )


@app.command()
def run(
    target: str = typer.Option("prod", help="dbt target for the transform stage."),
    skip_generate: bool = typer.Option(False, help="Reuse the existing generated source system."),
    skip_report: bool = typer.Option(False, help="Stop after dbt; do not build the report."),
    base_path: str | None = typer.Option(None, help="Passed through to `refarch report`."),
    site_url: str = typer.Option(seo.SITE_URL, help="Passed through to `refarch report`."),
) -> None:
    """Run every stage in order: generate -> load -> transform -> report."""
    if not skip_generate:
        generate_stage.generate()
    load()
    _run(["dbt", "build"], cwd=DBT_DIR, env=_dbt_env(target))
    if not skip_report:
        report(dev=False, base_path=base_path, site_url=site_url)
    typer.secho(
        f"Full run complete. The warehouse is {settings().warehouse_path}.",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
