"""The exhaust CLI entry point (ADR 0002)."""

from pathlib import Path

import typer

from exhaust import __version__
from exhaust.catalog import (
    DEFAULT_OUTPUT_RELATIVE_PATH,
    MalformedSkillFile,
    is_catalog_up_to_date,
    write_catalog,
)
from exhaust.workspace import scaffold_workspace

app = typer.Typer(name="exhaust", no_args_is_help=True)
catalog_app = typer.Typer(name="catalog", no_args_is_help=True)
app.add_typer(catalog_app)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    """exhaust: agent-first toolkit for security research."""


@app.command()
def new(
    target: str = typer.Argument(..., help="The Target this Workspace researches."),
    path: Path | None = typer.Option(
        None, "--path", help="Where to create the Workspace (default: ./<target>)."
    ),
) -> None:
    """Scaffold a new Workspace for TARGET."""
    workspace_path = path or Path(target)
    try:
        scaffold_workspace(workspace_path, target)
    except FileExistsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Scaffolded Workspace for {target} at {workspace_path}")


@catalog_app.command("generate")
def catalog_generate(
    skills_dir: Path = typer.Option(Path("skills"), help="Where vertical skills live."),
    output: Path = typer.Option(
        DEFAULT_OUTPUT_RELATIVE_PATH, help="Where to write the generated catalog."
    ),
) -> None:
    """Regenerate the vertical catalog from skill files (ADR 0016)."""
    try:
        write_catalog(skills_dir, output)
    except MalformedSkillFile as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote {output}")


@catalog_app.command("check")
def catalog_check(
    skills_dir: Path = typer.Option(Path("skills"), help="Where vertical skills live."),
    output: Path = typer.Option(
        DEFAULT_OUTPUT_RELATIVE_PATH, help="The committed catalog to check."
    ),
) -> None:
    """Fail if the committed catalog is out of sync with the skill files."""
    try:
        up_to_date = is_catalog_up_to_date(skills_dir, output)
    except MalformedSkillFile as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if not up_to_date:
        typer.echo(
            f"{output} is out of sync with {skills_dir}; run 'exhaust catalog "
            "generate'",
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"{output} is up to date")
