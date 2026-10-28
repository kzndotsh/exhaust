"""The relay channel: one connection per tool call, from the gate extension to here.

Pi's own RPC stdio stream and its `extension_ui_request`/`response`
dialog subprotocol are narrow (`select`/`confirm`/`input`/`editor`, each
with a fixed, human-dialog-shaped response and a timeout that
auto-resolves with a default value) and were never going to carry an
arbitrary `{tool, input}` round trip safely — an authorization decision
silently defaulting to "allow" because a dialog timed out is exactly the
failure mode exhaust's own approvals model (ADR 0023) exists to rule out.
So the gate extension's tool handlers talk to this adapter over a
dedicated Unix domain socket instead, one connection per call, carrying
one JSON request line and one JSON response line, independent of
anything Pi's own protocol defines.
"""

import json
import socket
from pathlib import Path
from typing import Protocol, cast

from exhaust.harness.pi_adapter.errors import PiProtocolError


class PendingRelayCall(Protocol):
    """One relayed tool call, waiting for this adapter to answer it."""

    @property
    def tool_name(self) -> str:
        """The Pi tool name the model called."""
        ...

    @property
    def input(self) -> dict[str, object]:
        """That tool call's arguments, exactly as the model supplied them."""
        ...

    def respond(self, payload: dict[str, object]) -> None:
        """Answer the call with `payload`, then close the connection."""
        ...


class RelayChannel(Protocol):
    """What `PiAgentSession` needs to receive relayed tool calls.

    A `Protocol`, not a concrete base class, so a test can hand
    `PiAgentSession` an in-memory fake instead of a real socket.
    """

    def accept_once(self, *, timeout: float) -> PendingRelayCall | None:
        """Block for the next relayed call, or return `None` after `timeout` seconds."""
        ...


class _SocketPendingCall:
    def __init__(
        self, connection: socket.socket, tool_name: str, call_input: dict[str, object]
    ) -> None:
        self._connection = connection
        self._tool_name = tool_name
        self._input = call_input

    @property
    def tool_name(self) -> str:
        """The Pi tool name the model called."""
        return self._tool_name

    @property
    def input(self) -> dict[str, object]:
        """That tool call's arguments, exactly as the model supplied them."""
        return self._input

    def respond(self, payload: dict[str, object]) -> None:
        """Write `payload` as one JSON line and close the connection."""
        with self._connection:
            self._connection.sendall((json.dumps(payload) + "\n").encode())


class UnixSocketRelayChannel:
    """`RelayChannel` over a Unix domain socket the gate extension connects to.

    Deliberately thin, like `pi_adapter.rpc.SubprocessRpcTransport`: the
    actual call-handling logic lives in `PiAgentSession`, which is tested
    against a fake `RelayChannel` instead of a real socket.
    """

    def __init__(self, socket_path: Path) -> None:
        self._socket_path = socket_path
        self._socket_path.unlink(missing_ok=True)
        self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._listener.bind(str(socket_path))
        self._listener.listen(1)

    def accept_once(self, *, timeout: float) -> PendingRelayCall | None:
        """Block for one connection carrying one relayed call, or `None` after `timeout`.

        Parameters
        ----------
        timeout : float
            How long to wait for a connection before giving up.

        Returns
        -------
        PendingRelayCall | None
            The pending call, or `None` if nothing connected in time.

        Raises
        ------
        PiProtocolError
            If a connection arrives but doesn't send one well-formed
            `{"tool": str, "input": object}` JSON line.
        """
        self._listener.settimeout(timeout)
        try:
            connection, _ = self._listener.accept()
        except TimeoutError:
            return None

        with connection.makefile("r") as reader:
            line = reader.readline()
        if not line:
            connection.close()
            raise PiProtocolError("relay connection closed before sending a call")

        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            connection.close()
            raise PiProtocolError(f"malformed relay call: {line!r}") from exc

        if not isinstance(parsed, dict):
            connection.close()
            raise PiProtocolError(f"relay call is not an object: {line!r}")
        record = cast("dict[str, object]", parsed)

        tool_name, call_input = record.get("tool"), record.get("input")
        if not isinstance(tool_name, str) or not isinstance(call_input, dict):
            connection.close()
            raise PiProtocolError(f"relay call missing 'tool'/'input': {line!r}")

        return _SocketPendingCall(connection, tool_name, cast("dict[str, object]", call_input))

    def close(self) -> None:
        """Stop listening and remove the socket file."""
        self._listener.close()
        self._socket_path.unlink(missing_ok=True)
