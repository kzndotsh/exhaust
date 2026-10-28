"""The 'exhaust doctor' command: is every pinned Rig tool actually present at its pinned version.

A read-only check, never a gate `exhaust run` enforces by itself —
ADR 0012 pins intent; this is what actually looks.
"""

import typer

from exhaust.rig import PINNED_TOOLS, check_pinned_tools, default_bridges

app = typer.Typer()


@app.command("doctor")
def doctor() -> None:
    """Report whether every pinned Rig tool is on PATH at its pinned version."""
    results = check_pinned_tools(default_bridges(), PINNED_TOOLS)

    for result in results:
        installed = result.installed_version or "not found"
        status = "ok" if result.ok else "MISMATCH"
        typer.echo(
            f"{result.name}: pinned {result.pinned_version}, installed {installed} [{status}]"
        )

    if not all(result.ok for result in results):
        raise typer.Exit(code=1)
