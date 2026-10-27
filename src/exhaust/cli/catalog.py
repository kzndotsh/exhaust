"""The 'exhaust catalog' commands (ADR 0016)."""

from pathlib import Path

import typer

from exhaust.catalog import (
    DEFAULT_OUTPUT_RELATIVE_PATH,
    MalformedSkillFileError,
    is_catalog_up_to_date,
    write_catalog,
)

app = typer.Typer(name="catalog", no_args_is_help=True)


@app.command("generate")
def generate(
    skills_dir: Path = typer.Option(Path("skills"), help="Where vertical skills live."),
    output: Path = typer.Option(
        DEFAULT_OUTPUT_RELATIVE_PATH, help="Where to write the generated catalog."
    ),
) -> None:
    """Regenerate the vertical catalog from skill files (ADR 0016)."""
    try:
        write_catalog(skills_dir, output)
    except MalformedSkillFileError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote {output}")


@app.command("check")
def check(
    skills_dir: Path = typer.Option(Path("skills"), help="Where vertical skills live."),
    output: Path = typer.Option(
        DEFAULT_OUTPUT_RELATIVE_PATH, help="The committed catalog to check."
    ),
) -> None:
    """Fail if the committed catalog is out of sync with the skill files."""
    try:
        up_to_date = is_catalog_up_to_date(skills_dir, output)
    except MalformedSkillFileError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if not up_to_date:
        typer.echo(
            f"{output} is out of sync with {skills_dir}; run 'exhaust catalog generate'",
            err=True,
        )
        raise typer.Exit(code=1)
    typer.echo(f"{output} is up to date")
