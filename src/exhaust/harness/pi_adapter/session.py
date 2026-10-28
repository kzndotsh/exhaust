"""`PiAgentSession`: the first concrete `AgentSession`, backed by Pi (ADR 0025).

`Harness`, `core.py`, and `actions.py` import nothing from this package:
nothing outside it knows Pi exists. `step`/`observe` strictly alternate,
enforced by `Harness._run_one_turn`'s own ordering, so a single
`_pending_call` attribute is enough state to track between them.
"""

import contextlib
import os
import subprocess
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from exhaust.harness.actions import ActionOutcome, AgentAction
from exhaust.harness.agent import AgentTurnRequest
from exhaust.harness.pi_adapter.errors import (
    AgentWentSilentError,
    GateNotLoadedError,
    MalformedRelayCallError,
    PiProtocolError,
)
from exhaust.harness.pi_adapter.relay import (
    PendingRelayCall,
    RelayChannel,
    UnixSocketRelayChannel,
)
from exhaust.harness.pi_adapter.rpc import PiCommands, PiRpc, SubprocessRpcTransport
from exhaust.harness.pi_adapter.schema import HANDSHAKE_TOOL_NAME
from exhaust.harness.pi_adapter.translate import RelayCall, action_from_relay, outcome_to_wire
from exhaust.rig import ToolInfo

_RELAY_SOCKET_ENV_VAR = "EXHAUST_RELAY_SOCKET"


@dataclass(frozen=True)
class PiLaunchConfig:
    """Everything needed to spawn and gate one Pi subprocess.

    Attributes
    ----------
    pi_executable : Path
        The `pi` binary, started as `pi --mode rpc --no-session --extensions <gate_extension_dir>`.
    provider : str
        Passed to Pi's own `--provider` flag (accepts a bare provider id
        or `provider/id`, per Pi's CLI reference).
    provider_base_url : str | None
        The seam ADR 0021's credential proxy fronts. Not yet plumbed into
        a real Pi provider config by this adapter — that wiring is out of
        scope until the proxy itself exists (see the design doc). Kept
        here so the seam is named, not silently dropped.
    gate_extension_dir : Path
        This package's own `gate/`, passed to `--extensions` explicitly —
        Pi loads no extensions into a fresh session by default (the
        `pi-schedule-prompt` finding ADR 0025 names).
    handshake_timeout_s : float
        How long to wait for the handshake tool call on a freshly started
        session before refusing to run (`GateNotLoadedError`).
    turn_poll_timeout_s : float
        How long `step()` waits for a relayed tool call before concluding
        the turn has settled idle and sending a follow-up nudge.
    settle_reprompts : int
        How many nudges `step()` sends before raising
        `AgentWentSilentError`.
    """

    pi_executable: Path
    provider: str
    provider_base_url: str | None
    gate_extension_dir: Path
    handshake_timeout_s: float = 10.0
    turn_poll_timeout_s: float = 30.0
    settle_reprompts: int = 2


def _compose_opening_prompt(request: AgentTurnRequest) -> str:
    return (
        f"Call the `{HANDSHAKE_TOOL_NAME}` tool now, with no arguments, before anything else.\n\n"
        f"Then, working the `{request.vertical.name}` vertical, follow this procedure:\n\n"
        f"{request.procedure}\n\n"
        "Available Rig tools (call `sandbox_call` or `real_target_call`, naming one of these "
        "as `tool`, with the `method` and `params` its own documentation describes):\n"
        f"{available_tools_prompt_lines(request.available_tools)}\n\n"
        "Propose exactly one action per turn, using one of your registered tools."
    )


def _settle_nudge(vertical: str) -> str:
    return (
        f"({vertical}) You have not called a tool. Take exactly one action now, using one "
        "of your registered tools."
    )


class PiAgentSession:
    """A live Pi subprocess, presented to the Harness as one `AgentSession`."""

    def __init__(self, rpc: PiCommands, relay: RelayChannel, cfg: PiLaunchConfig) -> None:
        self._rpc = rpc
        self._relay = relay
        self._cfg = cfg
        self._active_vertical: str | None = None
        self._pending_call: PendingRelayCall | None = None

    @classmethod
    @contextlib.contextmanager
    def launch(
        cls, cfg: PiLaunchConfig, *, socket_path: Path
    ) -> Generator["PiAgentSession", None, None]:
        """Spawn the Pi subprocess and yield a session bound to it.

        Parameters
        ----------
        cfg : PiLaunchConfig
            How to launch and gate the subprocess.
        socket_path : Path
            Where to bind the relay channel's Unix domain socket; the
            subprocess's gate extension reads this path from the
            `EXHAUST_RELAY_SOCKET` environment variable.

        Yields
        ------
        PiAgentSession
            The live session. The gate is verified per vertical, on each
            vertical's first `step()` call, not once here: a session with
            no vertical visited yet has spawned no Pi session to verify.
        """
        relay = UnixSocketRelayChannel(socket_path)
        env = {**os.environ, _RELAY_SOCKET_ENV_VAR: str(socket_path)}
        process = subprocess.Popen(
            [
                str(cfg.pi_executable),
                "--mode",
                "rpc",
                "--no-session",
                "--provider",
                cfg.provider,
                "--extensions",
                str(cfg.gate_extension_dir),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            env=env,
        )
        try:
            yield cls(PiRpc(SubprocessRpcTransport(process)), relay, cfg)
        finally:
            process.terminate()
            process.wait()
            relay.close()

    def step(self, request: AgentTurnRequest) -> AgentAction:
        """Resume `request.vertical`, blocking until it proposes one relayable action.

        Parameters
        ----------
        request : AgentTurnRequest
            This turn's vertical, procedure, and available Rig tools.

        Returns
        -------
        AgentAction
            The proposed action, translated from the relayed tool call.

        Raises
        ------
        GateNotLoadedError
            If `request.vertical` is new to this session and the gate
            extension doesn't announce itself in time.
        AgentWentSilentError
            If the turn settles with no relayable call after every
            configured re-prompt.
        """
        if request.vertical.name != self._active_vertical:
            self._begin_vertical(request)
        return self._await_next_action()

    def observe(self, outcome: ActionOutcome) -> None:
        """Answer the relay call `step()` last returned with `outcome`.

        Parameters
        ----------
        outcome : ActionOutcome
            What `Harness._dispatch` produced for that action.

        Raises
        ------
        PiProtocolError
            If called with no call currently pending.
        """
        if self._pending_call is None:
            raise PiProtocolError("observe() called with no pending relay call")
        pending, self._pending_call = self._pending_call, None
        pending.respond(outcome_to_wire(outcome))

    def _begin_vertical(self, request: AgentTurnRequest) -> None:
        self._rpc.new_session()
        self._active_vertical = request.vertical.name
        self._rpc.prompt(_compose_opening_prompt(request))

        handshake = self._relay.accept_once(timeout=self._cfg.handshake_timeout_s)
        if handshake is None or handshake.tool_name != HANDSHAKE_TOOL_NAME:
            if handshake is not None:
                handshake.respond({"ok": False, "output": "expected the handshake tool first"})
            raise GateNotLoadedError(
                f"{request.vertical.name}: gate extension didn't announce itself within "
                f"{self._cfg.handshake_timeout_s}s"
            )
        handshake.respond({"ok": True, "output": ""})

    def _await_next_action(self) -> AgentAction:
        if self._active_vertical is None:
            raise PiProtocolError("_await_next_action called before any vertical began")
        reprompts = 0
        while True:
            call = self._relay.accept_once(timeout=self._cfg.turn_poll_timeout_s)
            if call is None:
                if reprompts >= self._cfg.settle_reprompts:
                    raise AgentWentSilentError(
                        f"{self._active_vertical}: settled with no action after "
                        f"{self._cfg.settle_reprompts} re-prompts"
                    )
                reprompts += 1
                self._rpc.prompt(
                    _settle_nudge(self._active_vertical), streaming_behavior="followUp"
                )
                continue

            try:
                action = action_from_relay(
                    RelayCall(tool_name=call.tool_name, input=call.input),
                    vertical=self._active_vertical,
                )
            except MalformedRelayCallError as exc:
                call.respond({"ok": False, "output": str(exc)})
                continue

            self._pending_call = call
            return action


def available_tools_prompt_lines(available_tools: tuple[ToolInfo, ...]) -> str:
    """Render `available_tools` as the prose block `_compose_opening_prompt` embeds.

    Exposed separately so a test can pin the rendering without going
    through the full prompt (ADR 0013: this is the agent's only view of
    the Rig catalog — there is no per-method schema reaching it).

    Parameters
    ----------
    available_tools : tuple[ToolInfo, ...]
        The Rig tools this turn's vertical may call.

    Returns
    -------
    str
        One line per tool, or a placeholder if there are none.
    """
    lines = "\n".join(f"- {tool.name}: {tool.usage} ({tool.doc})" for tool in available_tools)
    return lines or "(none registered yet)"
