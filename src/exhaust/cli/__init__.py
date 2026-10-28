"""The exhaust CLI entry point (ADR 0002).

Each command group lives in its own module, composed here, per Typer's
own documented structure for a CLI with more than one group
(https://typer.tiangolo.com/tutorial/one-file-per-command).
"""

import typer

from exhaust import __version__
from exhaust.cli.catalog import app as catalog_app
from exhaust.cli.new import app as new_app
from exhaust.cli.run import app as run_app

app = typer.Typer(name="exhaust", no_args_is_help=True)
app.add_typer(new_app)
app.add_typer(catalog_app)
app.add_typer(run_app)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    """exhaust: agent-first toolkit for security research."""
