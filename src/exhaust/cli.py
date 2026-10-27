"""The exhaust CLI entry point (ADR 0002)."""

from pathlib import Path

import typer

from exhaust import __version__
from exhaust.workspace import scaffold_workspace

app = typer.Typer(name="exhaust", no_args_is_help=True)


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
