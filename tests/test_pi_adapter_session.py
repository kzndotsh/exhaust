from collections import deque
from pathlib import Path

import pytest

from exhaust.catalog import VerticalEntry
from exhaust.harness.actions import ActionRejected, SandboxCall
from exhaust.harness.agent import AgentTurnRequest
from exhaust.harness.pi_adapter.errors import (
    AgentWentSilentError,
    GateNotLoadedError,
    HandshakeSkippedError,
)
from exhaust.harness.pi_adapter.relay import PendingRelayCall
from exhaust.harness.pi_adapter.schema import HANDSHAKE_TOOL_NAME
from exhaust.harness.pi_adapter.session import PiAgentSession, PiLaunchConfig
from exhaust.rig import ToolInfo


class FakeRpc:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, str | None]] = []
        self.new_sessions = 0

    def prompt(self, text: str, *, streaming_behavior: str | None = None) -> None:
        self.prompts.append((text, streaming_behavior))

    def new_session(self) -> None:
        self.new_sessions += 1


class FakePendingCall:
    def __init__(self, tool_name: str, call_input: dict[str, object]) -> None:
        self.tool_name = tool_name
        self.input = call_input
        self.responses: list[dict[str, object]] = []

    def respond(self, payload: dict[str, object]) -> None:
        self.responses.append(payload)


class FakeRelay:
    """A scripted `RelayChannel`: a queue of pending calls, or `None` to simulate a timeout."""

    def __init__(self, scripted: list[PendingRelayCall | None]) -> None:
        self._queue: deque[PendingRelayCall | None] = deque(scripted)

    def accept_once(self, *, timeout: float) -> PendingRelayCall | None:
        return self._queue.popleft() if self._queue else None


def _cfg(**overrides: object) -> PiLaunchConfig:
    defaults: dict[str, object] = {
        "pi_executable": Path("/usr/local/bin/pi"),
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "provider_base_url": None,
        "gate_extension_file": Path("/tmp/gate/extension.ts"),
        "handshake_timeout_s": 1.0,
        "turn_poll_timeout_s": 1.0,
        "settle_reprompts": 2,
    }
    defaults.update(overrides)
    return PiLaunchConfig(**defaults)  # type: ignore[arg-type]


def _request(vertical: str = "injection") -> AgentTurnRequest:
    return AgentTurnRequest(
        vertical=VerticalEntry(name=vertical, required=True, gate=None),
        procedure="Try these payloads.",
        available_tools=(ToolInfo(name="fake-scanner", usage="scans", doc="see docs"),),
    )


def test_step_verifies_the_handshake_before_returning_the_first_action() -> None:
    handshake = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    real_input: dict[str, object] = {"tool": "fake-scanner", "method": "scan", "params": {}}
    real_call = FakePendingCall("sandbox_call", real_input)
    relay = FakeRelay([handshake, real_call])
    rpc = FakeRpc()
    session = PiAgentSession(rpc, relay, _cfg())

    action = session.step(_request())

    expected = SandboxCall(vertical="injection", tool="fake-scanner", method="scan", params={})
    assert action == expected
    assert rpc.new_sessions == 1
    assert handshake.responses == [{"ok": True, "output": ""}]


def test_step_raises_gate_not_loaded_when_handshake_never_arrives() -> None:
    relay = FakeRelay([None])  # the accept_once call for the handshake times out
    session = PiAgentSession(FakeRpc(), relay, _cfg())

    with pytest.raises(GateNotLoadedError):
        session.step(_request())


def test_step_raises_handshake_skipped_when_a_real_call_arrives_before_the_handshake() -> None:
    # Distinct from GateNotLoadedError: a call arriving at all proves the gate loaded,
    # so this is diagnosed as the model skipping the handshake, not an infra failure.
    impersonator = FakePendingCall("sandbox_call", {"tool": "x", "method": "y", "params": {}})
    relay = FakeRelay([impersonator])
    session = PiAgentSession(FakeRpc(), relay, _cfg())

    with pytest.raises(HandshakeSkippedError):
        session.step(_request())
    assert impersonator.responses == [{"ok": False, "output": "expected the handshake tool first"}]


def test_retrying_step_after_a_failed_handshake_re_runs_begin_vertical() -> None:
    # Regression: _active_vertical must only be set once the handshake succeeds,
    # or this retry would skip _begin_vertical entirely on the second call and
    # silently reuse a session that was never actually verified (rpc.new_sessions
    # would stay at 1 instead of advancing to 2).
    handshake = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    real_call = FakePendingCall("set_vertical_state", {"reason": "ok"})
    relay = FakeRelay([None, handshake, real_call])  # first attempt times out, second succeeds
    rpc = FakeRpc()
    session = PiAgentSession(rpc, relay, _cfg())

    with pytest.raises(GateNotLoadedError):
        session.step(_request())

    session.step(_request())  # retried: must re-run _begin_vertical, not skip it

    assert rpc.new_sessions == 2


def test_switching_vertical_opens_a_fresh_session() -> None:
    handshake1 = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    call1 = FakePendingCall("set_vertical_state", {"reason": "skip"})
    handshake2 = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    call2 = FakePendingCall("set_vertical_state", {"reason": "skip too"})
    relay = FakeRelay([handshake1, call1, handshake2, call2])
    rpc = FakeRpc()
    session = PiAgentSession(rpc, relay, _cfg())

    session.step(_request("injection"))
    session.observe(None)
    session.step(_request("auth"))

    assert rpc.new_sessions == 2


def test_resuming_the_same_vertical_does_not_reopen_a_session() -> None:
    handshake = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    call1 = FakePendingCall("set_vertical_state", {"reason": "first"})
    call2 = FakePendingCall("set_vertical_state", {"reason": "second"})
    relay = FakeRelay([handshake, call1, call2])
    rpc = FakeRpc()
    session = PiAgentSession(rpc, relay, _cfg())

    session.step(_request("injection"))
    session.observe(None)
    session.step(_request("injection"))

    assert rpc.new_sessions == 1


def test_observe_answers_the_pending_call_with_the_translated_outcome() -> None:
    handshake = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    real_input: dict[str, object] = {"tool": "fake-scanner", "method": "scan", "params": {}}
    call = FakePendingCall("sandbox_call", real_input)
    relay = FakeRelay([handshake, call])
    session = PiAgentSession(FakeRpc(), relay, _cfg())

    session.step(_request())
    session.observe(ActionRejected("not in scope"))

    assert call.responses == [{"ok": False, "output": "not in scope"}]


def test_malformed_relay_call_is_answered_inline_and_never_reaches_the_harness() -> None:
    handshake = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    bad_call = FakePendingCall("sandbox_call", {"tool": "fake-scanner"})  # missing method/params
    good_call = FakePendingCall("set_vertical_state", {"reason": "ok now"})
    relay = FakeRelay([handshake, bad_call, good_call])
    session = PiAgentSession(FakeRpc(), relay, _cfg())

    action = session.step(_request())

    assert action.reason == "ok now"  # type: ignore[union-attr]
    assert bad_call.responses  # answered inline, not surfaced as the step() result
    assert bad_call.responses[0]["ok"] is False


def test_turn_settling_idle_sends_a_follow_up_nudge_then_recovers() -> None:
    handshake = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    real_call = FakePendingCall("set_vertical_state", {"reason": "done"})
    relay = FakeRelay([handshake, None, real_call])  # one idle timeout, then the real action
    rpc = FakeRpc()
    session = PiAgentSession(rpc, relay, _cfg(settle_reprompts=2))

    session.step(_request())

    nudges = [p for p in rpc.prompts if p[1] == "followUp"]
    assert len(nudges) == 1


def test_turn_going_silent_past_every_reprompt_raises() -> None:
    handshake = FakePendingCall(HANDSHAKE_TOOL_NAME, {})
    relay = FakeRelay([handshake, None, None, None])  # handshake, then settle forever
    session = PiAgentSession(FakeRpc(), relay, _cfg(settle_reprompts=2))

    with pytest.raises(AgentWentSilentError):
        session.step(_request())


def test_launch_spawns_pi_with_builtin_tools_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Regression: the gate extension's tool_call allowlist must not be the
    # *only* thing stopping a built-in tool from running — --no-builtin-tools
    # removes them at spawn, so the allowlist hook is defense-in-depth, not
    # the sole boundary.
    captured_argv: list[str] = []

    class FakeProcess:
        stdin = None
        stdout = None

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> None:
            pass

    def fake_popen(argv: list[str], **_kwargs: object) -> FakeProcess:
        captured_argv.extend(argv)
        return FakeProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    cfg = _cfg(pi_executable=Path("/usr/local/bin/pi"))
    with PiAgentSession.launch(cfg, socket_path=tmp_path / "relay.sock"):
        pass

    assert "--no-builtin-tools" in captured_argv


def test_launch_uses_the_real_pi_cli_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: a no-credential smoke test against the real `pi` binary found
    # two wrong assumptions here. `--extensions <dir>` doesn't exist; the real
    # flag is singular `--extension <file>`, and it won't load a directory
    # unless it holds an `index.ts`/`index.js`, which `gate/` doesn't. And
    # `--provider` alone is rejected by the real CLI: it requires `--model`.
    captured_argv: list[str] = []

    class FakeProcess:
        stdin = None
        stdout = None

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> None:
            pass

    def fake_popen(argv: list[str], **_kwargs: object) -> FakeProcess:
        captured_argv.extend(argv)
        return FakeProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    cfg = _cfg(
        pi_executable=Path("/usr/local/bin/pi"),
        gate_extension_file=Path("/tmp/gate/extension.ts"),
        model="claude-sonnet-5",
    )
    with PiAgentSession.launch(cfg, socket_path=tmp_path / "relay.sock"):
        pass

    assert "--extensions" not in captured_argv
    extension_idx = captured_argv.index("--extension")
    assert captured_argv[extension_idx + 1] == "/tmp/gate/extension.ts"
    model_idx = captured_argv.index("--model")
    assert captured_argv[model_idx + 1] == "claude-sonnet-5"


def test_provider_base_url_without_agent_dir_is_refused() -> None:
    with pytest.raises(ValueError, match="agent_dir"):
        _cfg(provider_base_url="http://127.0.0.1:9000", agent_dir=None)


def test_anthropic_credential_file_without_agent_dir_is_refused() -> None:
    with pytest.raises(ValueError, match="agent_dir"):
        _cfg(anthropic_credential_file=Path("/tmp/virtual-key"), agent_dir=None)


def test_launch_writes_the_proxy_config_when_agent_dir_and_base_url_are_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_argv: list[str] = []

    class FakeProcess:
        stdin = None
        stdout = None

        def terminate(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> None:
            pass

    def fake_popen(argv: list[str], **_kwargs: object) -> FakeProcess:
        captured_argv.extend(argv)
        return FakeProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    agent_dir = tmp_path / "agent"
    cfg = _cfg(
        pi_executable=Path("/usr/local/bin/pi"),
        provider_base_url="http://127.0.0.1:9000",
        agent_dir=agent_dir,
    )
    with PiAgentSession.launch(cfg, socket_path=tmp_path / "relay.sock"):
        pass

    assert (agent_dir / "models.json").is_file()
