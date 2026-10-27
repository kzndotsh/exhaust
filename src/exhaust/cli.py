"""The exhaust CLI entry point (ADR 0002)."""

import typer

from exhaust import __version__

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
