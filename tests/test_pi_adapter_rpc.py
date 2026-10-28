import json
from collections import deque
from collections.abc import Callable

import pytest

from exhaust.harness.pi_adapter.errors import PiProtocolError
from exhaust.harness.pi_adapter.rpc import PiRpc


class FakeTransport:
    """An in-memory `RpcTransport`.

    `respond_with` decides what `response` record (if any) a written
    command earns; it's called with the parsed command and returns the
    response body (sans `id`/`type`), or `None` to enqueue nothing. Extra
    session events can be queued directly via `queue_event`. `eof=True`
    makes an empty queue mean "the stream closed" (`read_line` returns
    `None`); otherwise an empty queue means "nothing yet" (`read_line`
    raises `TimeoutError`), matching the real transport's distinction
    between EOF and a stalled subprocess.
    """

    def __init__(
        self,
        respond_with: Callable[[dict[str, object]], dict[str, object] | None],
        *,
        eof: bool = False,
    ) -> None:
        self.written: list[dict[str, object]] = []
        self._respond_with = respond_with
        self._stdout: deque[str] = deque()
        self._eof = eof

    def queue_event(self, event: dict[str, object]) -> None:
        self._stdout.append(json.dumps(event))

    def write_line(self, line: str) -> None:
        command = json.loads(line)
        self.written.append(command)
        reply = self._respond_with(command)
        if reply is not None:
            self._stdout.append(json.dumps({**reply, "id": command["id"]}))

    def read_line(self, *, timeout: float) -> str | None:
        if not self._stdout:
            if self._eof:
                return None
            raise TimeoutError(f"no fake output within {timeout}s")
        return self._stdout.popleft()


def _accept(command_name: str) -> Callable[[dict[str, object]], dict[str, object]]:
    def respond(_command: dict[str, object]) -> dict[str, object]:
        return {"type": "response", "command": command_name, "success": True}

    return respond


def test_prompt_sends_the_documented_command_shape() -> None:
    transport = FakeTransport(_accept("prompt"))
    PiRpc(transport).prompt("hello")

    assert transport.written[0]["type"] == "prompt"
    assert transport.written[0]["message"] == "hello"
    assert "streamingBehavior" not in transport.written[0]


def test_prompt_with_streaming_behavior() -> None:
    transport = FakeTransport(_accept("prompt"))
    PiRpc(transport).prompt("nudge", streaming_behavior="followUp")

    assert transport.written[0]["streamingBehavior"] == "followUp"


def test_prompt_raises_on_rejection() -> None:
    def reject(_command: dict[str, object]) -> dict[str, object]:
        return {"type": "response", "command": "prompt", "success": False, "error": "busy"}

    transport = FakeTransport(reject)

    with pytest.raises(PiProtocolError, match="busy"):
        PiRpc(transport).prompt("hi")


def test_new_session_sends_the_documented_command() -> None:
    transport = FakeTransport(_accept("new_session"))
    PiRpc(transport).new_session()

    assert transport.written[0]["type"] == "new_session"


def test_new_session_raises_on_rejection() -> None:
    def reject(_command: dict[str, object]) -> dict[str, object]:
        return {"type": "response", "command": "new_session", "success": False, "error": "nope"}

    transport = FakeTransport(reject)

    with pytest.raises(PiProtocolError, match="nope"):
        PiRpc(transport).new_session()


def test_unrelated_session_events_are_skipped_while_awaiting_a_response() -> None:
    # Queued ahead of the real response: write_line's own auto-response lands
    # after these, in FIFO order, so answering the wait has to read past them.
    transport = FakeTransport(_accept("prompt"))
    transport.queue_event({"type": "turn_start"})
    transport.queue_event({"type": "tool_execution_start", "toolName": "x"})

    PiRpc(transport).prompt("hi")  # doesn't raise despite the two unrelated events first


def test_stream_closing_mid_wait_raises() -> None:
    transport = FakeTransport(lambda _command: None, eof=True)  # never enqueues a response
    rpc = PiRpc(transport)

    with pytest.raises(PiProtocolError, match="closed"):
        rpc.prompt("hi")


def test_no_response_within_the_configured_timeout_raises() -> None:
    transport = FakeTransport(lambda _command: None)  # stalls forever, never closes
    rpc = PiRpc(transport, response_timeout_s=0.01)

    with pytest.raises(PiProtocolError, match="no response"):
        rpc.prompt("hi")
