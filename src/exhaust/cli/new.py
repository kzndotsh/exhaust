"""The 'exhaust new' command (ADR 0001, ADR 0006)."""

from pathlib import Path

import typer

from exhaust.workspace import scaffold_workspace

app = typer.Typer()


@app.command("new")
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
