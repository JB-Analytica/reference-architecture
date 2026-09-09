"""`refarch` -- one entry point that drives every stage of the reference architecture."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer

from refarch import generate as generate_stage
from refarch import lightdash_api
from refarch.config import DBT_DIR, LIGHTDASH_DIR, ROOT, settings

app = typer.Typer(
    help="model2data -> dlt -> BigQuery -> dbt -> Lightdash, stage by stage.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

LIGHTDASH_TAG = "lightdash"


def _dbt_env(target: str | None = None) -> dict[str, str]:
    """Environment for dbt and for the Lightdash CLI, which shells out to dbt itself.

    The interpreter running this CLI owns the right dbt; without putting its bin directory
    first, a bare `dbt` resolves through whatever shim happens to be on PATH (pyenv, a system
    install) and fails or -- worse -- silently uses a different version.
    """
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    env["DBT_PROFILES_DIR"] = str(DBT_DIR)
    if target:
        env["DBT_TARGET"] = target
    return env


def _run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    """Run a child command, surfacing its own output and exit code.

    The child (dbt, lightdash) has already printed a better diagnostic than any traceback of
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
    """Stage 2 -- extract the source system into BigQuery with dlt (incremental, merge on key)."""
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


@app.command()
def deploy(
    create: str | None = typer.Option(
        None,
        help="Create a new Lightdash project with this name instead of updating the current one.",
    ),
    target: str = typer.Option("prod", help="dbt target whose datasets Lightdash should read."),
    project_uuid: str | None = typer.Option(
        None, help="Lightdash project UUID (default: CLI config)."
    ),
) -> None:
    """Stage 4 -- deploy the semantic layer to Lightdash and upload charts and dashboards."""
    # --assume-yes keeps the CLI non-interactive: it otherwise prompts on an unsupported dbt
    # version and whenever a stale preview project exists, either of which hangs forever in CI.
    deploy_cmd = [
        "lightdash",
        "deploy",
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
        "--target",
        target,
        "--assume-yes",
    ]
    if create:
        deploy_cmd += ["--create", create]
    else:
        # Name the project explicitly; the CLI's saved default can be a leftover preview.
        deploy_cmd += ["--project", lightdash_api.resolve_auth(project_uuid).project_uuid]
    _run(deploy_cmd, env=_dbt_env(target))

    # `lightdash deploy --create` switches the CLI's active project to the new one, so resolving
    # auth *after* the deploy picks it up without the user copying a UUID around.
    auth = lightdash_api.resolve_auth(project_uuid)
    lightdash_api.restrict_explores_to_tag(auth, LIGHTDASH_TAG)
    name = lightdash_api.project_name(auth)
    typer.echo(f"Explores in '{name}' restricted to models tagged '{LIGHTDASH_TAG}'.")

    _run(
        [
            "lightdash",
            "upload",
            "--path",
            str(LIGHTDASH_DIR),
            "--project",
            auth.project_uuid,
            "--force",
        ],
        env=_dbt_env(target),
    )
    typer.secho("Lightdash deployed.", fg=typer.colors.GREEN)


@app.command()
def run(
    target: str = typer.Option("prod", help="dbt target for the transform and deploy stages."),
    skip_generate: bool = typer.Option(False, help="Reuse the existing generated source system."),
    skip_deploy: bool = typer.Option(False, help="Stop after dbt; do not touch Lightdash."),
) -> None:
    """Run every stage in order: generate -> load -> transform -> deploy."""
    if not skip_generate:
        generate_stage.generate()
    load()
    _run(["dbt", "build"], cwd=DBT_DIR, env=_dbt_env(target))
    if not skip_deploy:
        deploy(create=None, target=target, project_uuid=None)
    typer.secho("Full run complete.", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
