"""The 'exhaust run' command: drive a Workspace with the Pi-backed `AgentSession` (ADR 0025).

The only place in the CLI that knows Pi exists, per ADR 0025: everything
else — `Harness`, `core.py`, `actions.py` — stays unaware of it. No Rig
bridges are wired in yet (ADR 0012: no tools are pinned yet), so a run
started this way can drive `SetVerticalState` and `SelfReport` turns but
cannot yet dispatch a `SandboxCall` or `RealTargetCall` to anything real.
"""

import uuid
from pathlib import Path

import typer

from exhaust.harness.budget import RunBudget
from exhaust.harness.core import Harness
from exhaust.harness.pi_adapter import (
    AgentWentSilentError,
    GateNotLoadedError,
    HandshakeSkippedError,
    PiAgentSession,
    PiLaunchConfig,
    PiProtocolError,
)

app = typer.Typer()

_DEFAULT_GATE_EXTENSION = (
    Path(__file__).resolve().parent.parent / "harness" / "pi_adapter" / "gate" / "extension.ts"
)


@app.command("run")
def run(
    target: str = typer.Argument(..., help="The Target this Workspace researches."),
    workspace: Path | None = typer.Option(
        None, "--workspace", help="The Workspace to drive (default: ./<target>)."
    ),
    skills_dir: Path = typer.Option(Path("skills"), help="Where vertical skills live."),
    provider: str = typer.Option("anthropic", help="Passed to Pi's --provider flag."),
    model: str = typer.Option(..., help="Passed to Pi's --model flag."),
    provider_base_url: str | None = typer.Option(
        None, help="ADR 0021's credential-proxy seam; not plumbed by this adapter yet."
    ),
    pi_executable: Path = typer.Option(Path("pi"), help="The pi binary to spawn."),
    gate_extension: Path = typer.Option(
        _DEFAULT_GATE_EXTENSION, help="This package's gate/extension.ts (ADR 0025)."
    ),
    max_turns: int = typer.Option(200, help="The most agent turns this run will take."),
) -> None:
    """Drive TARGET's Workspace with a live Pi-backed agent until done, blocked, or out of turns."""
    workspace_dir = workspace or Path(target)
    if not workspace_dir.exists():
        typer.echo(f"{workspace_dir} does not exist; run 'exhaust new {target}' first", err=True)
        raise typer.Exit(code=1)

    cfg = PiLaunchConfig(
        pi_executable=pi_executable,
        provider=provider,
        model=model,
        provider_base_url=provider_base_url,
        gate_extension_file=gate_extension,
    )
    socket_path = Path(f"/tmp/exhaust-pi-{uuid.uuid4().hex[:12]}.sock")

    try:
        with PiAgentSession.launch(cfg, socket_path=socket_path) as agent:
            harness = Harness.open(workspace_dir, skills_dir, target, agent=agent)
            outcome = harness.run(budget=RunBudget(max_turns=max_turns))
    except (GateNotLoadedError, HandshakeSkippedError) as exc:
        typer.echo(f"refusing to run ungated: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (AgentWentSilentError, PiProtocolError) as exc:
        typer.echo(f"pi adapter error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(outcome.summary())
    if outcome.needs_human:
        typer.echo(f"needs human attention: {', '.join(outcome.needs_human)}")
    if not outcome.done:
        raise typer.Exit(code=1)
