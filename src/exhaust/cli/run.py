"""The 'exhaust run' command: drive a Workspace with the Pi-backed `AgentSession` (ADR 0025).

The only place in the CLI that knows Pi exists, per ADR 0025: everything
else — `Harness`, `core.py`, `actions.py` — stays unaware of it. `nmap`
(ADR 0026) is the only Rig tool pinned so far, so a run started this
way can dispatch a `SandboxCall`/`RealTargetCall` naming it, but
nothing else. `--anthropic-key-file` is the one place that wires up
ADR 0021's credential proxy: without it, `--provider-base-url` is still
available as a plain, unauthenticated redirect (e.g. to a gateway that
does its own authentication).
"""

import contextlib
import tempfile
import uuid
from pathlib import Path

import typer

from exhaust.harness.budget import RunBudget
from exhaust.harness.core import Harness
from exhaust.harness.credential_proxy import (
    CredentialProxy,
    CredentialProxyConfig,
    InsecureCredentialFileError,
    SpendTracker,
    TokenPricing,
    generate_virtual_key,
    load_api_key_from_file,
    write_virtual_key_file,
)
from exhaust.harness.pi_adapter import (
    AgentWentSilentError,
    GateNotLoadedError,
    HandshakeSkippedError,
    PiAgentSession,
    PiLaunchConfig,
    PiProtocolError,
)
from exhaust.rig import PINNED_TOOLS, check_pinned_tools, default_bridges

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
        None, help="Redirect Pi's provider base URL; requires --agent-dir."
    ),
    agent_dir: Path | None = typer.Option(
        None, help="Pi's per-run config dir (PI_CODING_AGENT_DIR); required by --provider-base-url."
    ),
    anthropic_key_file: Path | None = typer.Option(
        None,
        help=(
            "The real Anthropic API key, as a file (ADR 0021). Starts a local, "
            "budget-capped credential proxy and points Pi at it instead of the real API."
        ),
    ),
    budget_usd: float | None = typer.Option(
        None, help="This run's dollar budget, required with --anthropic-key-file."
    ),
    input_price_per_million_usd: float | None = typer.Option(
        None, help="The model's input price, required with --anthropic-key-file."
    ),
    output_price_per_million_usd: float | None = typer.Option(
        None, help="The model's output price, required with --anthropic-key-file."
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

    pricing_incomplete = (
        budget_usd is None
        or input_price_per_million_usd is None
        or output_price_per_million_usd is None
    )
    if anthropic_key_file is not None and pricing_incomplete:
        typer.echo(
            "--anthropic-key-file requires --budget-usd, --input-price-per-million-usd, "
            "and --output-price-per-million-usd",
            err=True,
        )
        raise typer.Exit(code=1)

    bridges = default_bridges()
    for result in check_pinned_tools(bridges, PINNED_TOOLS):
        if not result.ok:
            installed = result.installed_version or "not found"
            typer.echo(
                f"warning: {result.name} pinned at {result.pinned_version}, "
                f"found {installed} (run 'exhaust doctor' for details)",
                err=True,
            )

    socket_path = Path(f"/tmp/exhaust-pi-{uuid.uuid4().hex[:12]}.sock")

    with contextlib.ExitStack() as stack:
        anthropic_credential_file: Path | None = None

        if anthropic_key_file is not None:
            try:
                real_key = load_api_key_from_file(anthropic_key_file)
            except InsecureCredentialFileError as exc:
                typer.echo(str(exc), err=True)
                raise typer.Exit(code=1) from exc

            assert budget_usd is not None
            assert input_price_per_million_usd is not None
            assert output_price_per_million_usd is not None

            virtual_key = generate_virtual_key()
            agent_dir = agent_dir or Path(tempfile.mkdtemp(prefix="exhaust-pi-agent-"))
            anthropic_credential_file = agent_dir / "anthropic-virtual-key"
            write_virtual_key_file(anthropic_credential_file, virtual_key)

            budget = SpendTracker(
                max_usd=budget_usd,
                pricing=TokenPricing(input_price_per_million_usd, output_price_per_million_usd),
            )
            proxy_cfg = CredentialProxyConfig(
                real_api_key=real_key, virtual_key=virtual_key, budget=budget
            )
            proxy = stack.enter_context(CredentialProxy(proxy_cfg))
            provider_base_url = proxy.base_url

        cfg = PiLaunchConfig(
            pi_executable=pi_executable,
            provider=provider,
            model=model,
            provider_base_url=provider_base_url,
            gate_extension_file=gate_extension,
            agent_dir=agent_dir,
            anthropic_credential_file=anthropic_credential_file,
        )

        try:
            agent = stack.enter_context(PiAgentSession.launch(cfg, socket_path=socket_path))
            harness = Harness.open(workspace_dir, skills_dir, target, agent=agent, bridges=bridges)
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
