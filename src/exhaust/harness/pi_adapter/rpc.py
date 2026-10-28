"""The thin transport driving Pi's own documented RPC stdio protocol.

Newline-delimited JSON over a subprocess's stdin/stdout (`pi --mode rpc
--no-session`). This module only ever sends the two commands
`PiAgentSession` needs (`prompt`, `new_session`) and correlates each with
its `response` record, skipping any session event it isn't waiting for.
It carries no exhaust vocabulary and no relay logic: the actual tool-call
relay is a separate channel (`relay.py`), since Pi's RPC stdio stream and
its narrow `extension_ui_request`/`response` dialog subprotocol are not a
general-purpose channel for an arbitrary `{tool, input}` round trip (see
`docs/artifacts/2026-10-27-pi-agent-session-design.md`'s verification
notes).
"""

import json
import subprocess
from collections.abc import Mapping
from typing import Any, Protocol, cast

from exhaust.harness.pi_adapter.errors import PiProtocolError


class PiCommands(Protocol):
    """What `PiAgentSession` needs from the RPC command side.

    `PiRpc` satisfies this; a test hands `PiAgentSession` an in-memory
    fake instead, the same way `RelayChannel` decouples it from a real
    socket.
    """

    def prompt(self, text: str, *, streaming_behavior: str | None = None) -> None:
        """Send `text` as the active session's next prompt."""
        ...

    def new_session(self) -> None:
        """Start a fresh Pi session in the running subprocess."""
        ...


class RpcTransport(Protocol):
    """What `PiRpc` needs from the line underneath it.

    A `Protocol`, not a concrete base class, so a test can hand `PiRpc` an
    in-memory fake instead of a real subprocess's pipes.
    """

    def write_line(self, line: str) -> None:
        """Write one line (no trailing newline) to the subprocess's stdin."""
        ...

    def read_line(self) -> str | None:
        """Block for the next line of the subprocess's stdout, or `None` on EOF."""
        ...


class SubprocessRpcTransport:
    """`RpcTransport` over a real `subprocess.Popen`'s stdio pipes.

    Deliberately thin: everything this adapter can get wrong is in
    `PiRpc`, which is tested without a subprocess at all. This class is
    the untestable edge boundary-discipline asks to keep as small as
    possible.
    """

    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process

    def write_line(self, line: str) -> None:
        """Write `line` plus a trailing LF to the subprocess's stdin."""
        if self._process.stdin is None:
            raise PiProtocolError("subprocess has no stdin pipe")
        self._process.stdin.write(line + "\n")
        self._process.stdin.flush()

    def read_line(self) -> str | None:
        """Read one line from the subprocess's stdout, or `None` at EOF."""
        if self._process.stdout is None:
            raise PiProtocolError("subprocess has no stdout pipe")
        line = self._process.stdout.readline()
        return None if line == "" else line.rstrip("\n")


class PiRpc:
    """Drives Pi's RPC stdio protocol: send a command, wait for its response.

    Every session event that arrives while waiting for a specific
    command's response is read and discarded; `PiAgentSession` doesn't
    need Pi's own tool-level event stream, since the relay channel already
    carries the authoritative content for every action.
    """

    def __init__(self, transport: RpcTransport) -> None:
        self._transport = transport
        self._next_id = 0

    def _fresh_id(self) -> str:
        self._next_id += 1
        return f"pi-adapter-{self._next_id}"

    def _send_and_await(self, command: Mapping[str, Any]) -> Mapping[str, Any]:
        request_id = self._fresh_id()
        self._transport.write_line(json.dumps({**command, "id": request_id}))

        while True:
            line = self._transport.read_line()
            if line is None:
                raise PiProtocolError("Pi's RPC stream closed while awaiting a response")

            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PiProtocolError(f"malformed RPC record: {line!r}") from exc

            if not isinstance(parsed, dict):
                raise PiProtocolError(f"RPC record is not an object: {line!r}")
            record = cast("dict[str, Any]", parsed)
            if record.get("type") == "response" and record.get("id") == request_id:
                return record

    def prompt(self, text: str, *, streaming_behavior: str | None = None) -> None:
        """Send `text` as the active session's next prompt.

        Parameters
        ----------
        text : str
            The prompt to send.
        streaming_behavior : str | None
            `"followUp"` queues `text` to be delivered once the current
            run goes idle, and is safe to send whether or not a run is
            currently active — unlike a plain prompt, which Pi rejects if
            the agent is already streaming. `None` sends a plain prompt.

        Raises
        ------
        PiProtocolError
            If Pi rejects the prompt (`success: false`) or the stream
            closes before answering.
        """
        command: dict[str, Any] = {"type": "prompt", "message": text}
        if streaming_behavior is not None:
            command["streamingBehavior"] = streaming_behavior
        response = self._send_and_await(command)
        if not response.get("success"):
            raise PiProtocolError(f"prompt rejected: {response.get('error')}")

    def new_session(self) -> None:
        """Start a fresh Pi session in the running subprocess.

        Raises
        ------
        PiProtocolError
            If Pi rejects the command or the stream closes before
            answering.
        """
        response = self._send_and_await({"type": "new_session"})
        if not response.get("success"):
            raise PiProtocolError(f"new_session rejected: {response.get('error')}")
