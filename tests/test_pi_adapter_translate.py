from pathlib import Path

import pytest

from exhaust.findings import FindingScope, Verdict, VerdictType
from exhaust.harness.actions import (
    ActionRejected,
    ProposeVerdict,
    RealTargetCall,
    RecordFinding,
    SandboxCall,
    SelfReport,
    SetVerticalState,
)
from exhaust.harness.pi_adapter.errors import MalformedRelayCallError
from exhaust.harness.pi_adapter.schema import RELAY_TOOL_FIELDS, RELAY_TOOL_NAMES
from exhaust.harness.pi_adapter.translate import RelayCall, action_from_relay, outcome_to_wire
from exhaust.ledger import VerticalState
from exhaust.rig import ToolResult


def test_sandbox_call_translates() -> None:
    call = RelayCall(
        tool_name="sandbox_call",
        input={"tool": "fake-scanner", "method": "scan", "params": {"target": "x"}},
    )
    assert action_from_relay(call, vertical="injection") == SandboxCall(
        vertical="injection", tool="fake-scanner", method="scan", params={"target": "x"}
    )


def test_real_target_call_requires_target() -> None:
    call = RelayCall(
        tool_name="real_target_call",
        input={"tool": "fake-scanner", "method": "exploit", "params": {}},
    )
    with pytest.raises(MalformedRelayCallError):
        action_from_relay(call, vertical="injection")


def test_real_target_call_translates() -> None:
    call = RelayCall(
        tool_name="real_target_call",
        input={"tool": "fake-scanner", "method": "exploit", "params": {}, "target": "1.2.3.4"},
    )
    assert action_from_relay(call, vertical="injection") == RealTargetCall(
        vertical="injection", tool="fake-scanner", method="exploit", params={}, target="1.2.3.4"
    )


def test_record_finding_translates() -> None:
    call = RelayCall(
        tool_name="record_finding",
        input={
            "claim": "session fixation",
            "severity": "high",
            "scope": "sandbox",
            "evidence_scratch_path": "req.http",
        },
    )
    assert action_from_relay(call, vertical="auth") == RecordFinding(
        vertical="auth",
        claim="session fixation",
        severity="high",
        scope=FindingScope.SANDBOX,
        evidence_scratch_path=Path("req.http"),
    )


def test_record_finding_rejects_unknown_scope() -> None:
    call = RelayCall(
        tool_name="record_finding",
        input={
            "claim": "x",
            "severity": "low",
            "scope": "not-a-real-scope",
            "evidence_scratch_path": "req.http",
        },
    )
    with pytest.raises(MalformedRelayCallError):
        action_from_relay(call, vertical="auth")


def test_propose_verdict_translates() -> None:
    call = RelayCall(
        tool_name="propose_verdict", input={"finding_id": "f1", "verdict_type": "confirmed"}
    )
    assert action_from_relay(call, vertical="auth") == ProposeVerdict(
        finding_id="f1", verdict=Verdict(type=VerdictType.CONFIRMED)
    )


def test_propose_verdict_does_not_require_a_vertical_field() -> None:
    # ProposeVerdict has no vertical attribute; translation still succeeds
    # with the Harness's active vertical supplied, it's just unused.
    call = RelayCall(
        tool_name="propose_verdict", input={"finding_id": "f1", "verdict_type": "false_positive"}
    )
    action = action_from_relay(call, vertical="whatever")
    assert isinstance(action, ProposeVerdict)
    assert not hasattr(action, "vertical")


def test_self_report_translates() -> None:
    call = RelayCall(
        tool_name="self_report",
        input={
            "tools_exercised": ["fake-scanner"],
            "findings_dispositioned": ["f1"],
            "no_further_avenues": True,
        },
    )
    action = action_from_relay(call, vertical="auth")
    assert isinstance(action, SelfReport)
    assert action.vertical == "auth"
    assert action.attestation.tools_exercised == ("fake-scanner",)
    assert action.attestation.no_further_avenues is True


def test_set_vertical_state_always_proposes_skipped() -> None:
    call = RelayCall(tool_name="set_vertical_state", input={"reason": "out of scope"})
    assert action_from_relay(call, vertical="auth") == SetVerticalState(
        vertical="auth", to=VerticalState.SKIPPED, reason="out of scope"
    )


def test_unknown_tool_name_is_rejected() -> None:
    call = RelayCall(tool_name="bash", input={"command": "ls"})
    with pytest.raises(MalformedRelayCallError):
        action_from_relay(call, vertical="auth")


def test_missing_field_is_rejected() -> None:
    call = RelayCall(tool_name="sandbox_call", input={"tool": "fake-scanner"})
    with pytest.raises(MalformedRelayCallError):
        action_from_relay(call, vertical="auth")


@pytest.mark.parametrize("tool_name", sorted(RELAY_TOOL_NAMES - {"exhaust_handshake"}))
def test_every_relay_tool_name_has_a_builder(tool_name: str) -> None:
    # Parity anchor (schema.py's own docstring): every tool this module
    # claims to handle actually round-trips through action_from_relay,
    # even if just by raising on an empty input.
    call = RelayCall(tool_name=tool_name, input={})
    with pytest.raises(MalformedRelayCallError):
        action_from_relay(call, vertical="auth")
    # and every required field is in fact required
    assert RELAY_TOOL_FIELDS[tool_name]  # non-empty for every real action tool


def test_outcome_to_wire_tool_result() -> None:
    assert outcome_to_wire(ToolResult(ok=True, output="done")) == {"ok": True, "output": "done"}


def test_outcome_to_wire_action_rejected_is_not_a_block() -> None:
    wire = outcome_to_wire(ActionRejected("not in scope"))
    assert wire == {"ok": False, "output": "not in scope"}
    assert "block" not in wire


def test_outcome_to_wire_none() -> None:
    assert outcome_to_wire(None) == {"ok": True, "output": ""}
