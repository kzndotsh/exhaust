import json
import socket
from collections.abc import Generator
from pathlib import Path

import pytest

from exhaust.harness.pi_adapter.errors import PiProtocolError
from exhaust.harness.pi_adapter.relay import UnixSocketRelayChannel


@pytest.fixture
def relay(tmp_path: Path) -> Generator[UnixSocketRelayChannel, None, None]:
    channel = UnixSocketRelayChannel(tmp_path / "relay.sock")
    yield channel
    channel.close()


def _connect_and_send(socket_path: Path, payload: dict[str, object]) -> socket.socket:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(str(socket_path))
    client.sendall((json.dumps(payload) + "\n").encode())
    return client


def test_a_real_connection_round_trips_a_call_and_its_response(tmp_path: Path) -> None:
    socket_path = tmp_path / "relay.sock"
    channel = UnixSocketRelayChannel(socket_path)
    try:
        client = _connect_and_send(
            socket_path, {"tool": "sandbox_call", "input": {"tool": "x", "method": "y"}}
        )

        pending = channel.accept_once(timeout=2.0)

        assert pending is not None
        assert pending.tool_name == "sandbox_call"
        assert pending.input == {"tool": "x", "method": "y"}

        pending.respond({"ok": True, "output": "done"})

        with client.makefile("r") as reader:
            reply = json.loads(reader.readline())
        assert reply == {"ok": True, "output": "done"}
    finally:
        channel.close()


def test_accept_once_times_out_with_no_connection(relay: UnixSocketRelayChannel) -> None:
    assert relay.accept_once(timeout=0.1) is None


def test_a_connection_with_malformed_json_raises(tmp_path: Path) -> None:
    socket_path = tmp_path / "relay.sock"
    channel = UnixSocketRelayChannel(socket_path)
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(socket_path))
        client.sendall(b"not json at all\n")

        with pytest.raises(PiProtocolError, match="malformed"):
            channel.accept_once(timeout=2.0)
    finally:
        channel.close()


def test_a_connection_missing_tool_or_input_raises(tmp_path: Path) -> None:
    socket_path = tmp_path / "relay.sock"
    channel = UnixSocketRelayChannel(socket_path)
    try:
        _connect_and_send(socket_path, {"tool": "sandbox_call"})  # no "input"

        with pytest.raises(PiProtocolError, match="missing"):
            channel.accept_once(timeout=2.0)
    finally:
        channel.close()


def test_a_connection_accepted_but_never_sending_data_times_out(tmp_path: Path) -> None:
    # Regression: settimeout on the listener alone only bounds accept(); the
    # accepted connection's own read must be bounded too, or a peer that
    # connects and then stalls hangs accept_once forever regardless of timeout.
    socket_path = tmp_path / "relay.sock"
    channel = UnixSocketRelayChannel(socket_path)
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(str(socket_path))  # connects, but never sends anything

        with pytest.raises(PiProtocolError, match="sent no call"):
            channel.accept_once(timeout=0.2)
    finally:
        client.close()
        channel.close()


def test_close_cleans_up_a_connection_accepted_but_never_answered(tmp_path: Path) -> None:
    # Regression: close() used to only close the listener, leaking any
    # connection whose call was accepted but never respond()-ed to (e.g. an
    # uncaught exception elsewhere left it unanswered).
    socket_path = tmp_path / "relay.sock"
    channel = UnixSocketRelayChannel(socket_path)
    client = _connect_and_send(socket_path, {"tool": "sandbox_call", "input": {}})

    pending = channel.accept_once(timeout=2.0)
    assert pending is not None  # accepted, but respond() deliberately never called

    channel.close()  # must not hang, and must close the dangling connection

    with client.makefile("r") as reader:
        assert reader.readline() == ""  # the peer sees the connection close, not a hang
    client.close()
