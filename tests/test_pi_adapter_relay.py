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
