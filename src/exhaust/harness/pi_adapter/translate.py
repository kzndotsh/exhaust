"""Pure translation between a Pi relay call and exhaust's own `AgentAction` vocabulary.

No I/O, no subprocess, no socket: everything here is a plain function over
plain data, so the wire contract this adapter promises Pi (`schema.py`
documents the tool names and fields) is tested without spawning anything.
`action_from_relay` is the only place a `vertical` name is attached to an
`AgentAction` built from a relay call, and it always comes from the
Harness's own currently active vertical, never from the call's `input` —
nothing in the model's payload can forge which vertical an action belongs
to.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from exhaust.findings import FindingScope as _FindingScope
from exhaust.findings import Verdict, VerdictType
from exhaust.harness.actions import (
    ActionOutcome,
    ActionRejected,
    AgentAction,
    ExhaustionAttestation,
    ProposeVerdict,
    RealTargetCall,
    RecordFinding,
    SandboxCall,
    SelfReport,
    SetVerticalState,
)
from exhaust.harness.pi_adapter.errors import MalformedRelayCallError
from exhaust.ledger import VerticalState
from exhaust.rig import ToolResult


@dataclass(frozen=True)
class RelayCall:
    """One relayed tool call, already deserialized off the wire.

    Attributes
    ----------
    tool_name : str
        The Pi tool name the model called, one of `schema.RELAY_TOOL_NAMES`.
    input : Mapping[str, Any]
        That tool's call arguments, exactly as the model supplied them.
    """

    tool_name: str
    input: Mapping[str, Any]


def _str(input_: Mapping[str, Any], key: str) -> str:
    value = input_.get(key)
    if not isinstance(value, str):
        raise MalformedRelayCallError(f"{key!r} must be a string")
    return value


def _mapping(input_: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = input_.get(key)
    if not isinstance(value, Mapping):
        raise MalformedRelayCallError(f"{key!r} must be an object")
    return cast(Mapping[str, Any], value)


def _str_tuple(input_: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = input_.get(key, [])
    if not isinstance(value, list):
        raise MalformedRelayCallError(f"{key!r} must be a list of strings")
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise MalformedRelayCallError(f"{key!r} must be a list of strings")
    return tuple(cast("list[str]", items))


def _bool(input_: Mapping[str, Any], key: str) -> bool:
    value = input_.get(key)
    if not isinstance(value, bool):
        raise MalformedRelayCallError(f"{key!r} must be a boolean")
    return value


def _sandbox_call(call: RelayCall, *, vertical: str) -> SandboxCall:
    return SandboxCall(
        vertical=vertical,
        tool=_str(call.input, "tool"),
        method=_str(call.input, "method"),
        params=_mapping(call.input, "params"),
    )


def _real_target_call(call: RelayCall, *, vertical: str) -> RealTargetCall:
    return RealTargetCall(
        vertical=vertical,
        tool=_str(call.input, "tool"),
        method=_str(call.input, "method"),
        params=_mapping(call.input, "params"),
        target=_str(call.input, "target"),
    )


def _record_finding(call: RelayCall, *, vertical: str) -> RecordFinding:
    try:
        scope = _FindingScope(_str(call.input, "scope"))
    except ValueError as exc:
        raise MalformedRelayCallError(f"unknown 'scope': {exc}") from exc
    return RecordFinding(
        vertical=vertical,
        claim=_str(call.input, "claim"),
        severity=_str(call.input, "severity"),
        scope=scope,
        evidence_scratch_path=Path(_str(call.input, "evidence_scratch_path")),
    )


def _propose_verdict(call: RelayCall, *, vertical: str) -> ProposeVerdict:  # noqa: ARG001
    # `vertical` is part of every builder's shared signature (see `_BUILDERS`'s uniform
    # call in `action_from_relay`); ProposeVerdict has no vertical field of its own.
    try:
        verdict_type = VerdictType(_str(call.input, "verdict_type"))
    except ValueError as exc:
        raise MalformedRelayCallError(f"unknown 'verdict_type': {exc}") from exc
    try:
        verdict = Verdict(
            type=verdict_type,
            note=call.input.get("note", ""),
            requirements=call.input.get("requirements"),
            supporting_evidence=_str_tuple(call.input, "supporting_evidence"),
            contradicting_evidence=_str_tuple(call.input, "contradicting_evidence"),
        )
    except ValueError as exc:
        raise MalformedRelayCallError(str(exc)) from exc
    return ProposeVerdict(finding_id=_str(call.input, "finding_id"), verdict=verdict)


def _self_report(call: RelayCall, *, vertical: str) -> SelfReport:
    attestation = ExhaustionAttestation(
        tools_exercised=_str_tuple(call.input, "tools_exercised"),
        findings_dispositioned=_str_tuple(call.input, "findings_dispositioned"),
        no_further_avenues=_bool(call.input, "no_further_avenues"),
    )
    return SelfReport(vertical=vertical, attestation=attestation)


def _set_vertical_state(call: RelayCall, *, vertical: str) -> SetVerticalState:
    return SetVerticalState(
        vertical=vertical, to=VerticalState.SKIPPED, reason=_str(call.input, "reason")
    )


_BUILDERS: dict[str, Callable[..., AgentAction]] = {
    "sandbox_call": _sandbox_call,
    "real_target_call": _real_target_call,
    "record_finding": _record_finding,
    "propose_verdict": _propose_verdict,
    "self_report": _self_report,
    "set_vertical_state": _set_vertical_state,
}


def action_from_relay(call: RelayCall, *, vertical: str) -> AgentAction:
    """Build one `AgentAction` from a relayed tool call.

    `tool`/`method`/`params` on `SandboxCall`/`RealTargetCall` are passed
    through unvalidated beyond their basic shape: a bad tool or method name
    isn't checked here. It's checked exactly once, inside
    `Harness._dispatch`'s own `rig.call`, which is already the Rig's single
    source of truth for what's callable; duplicating that check here would
    only risk drifting from it.

    Parameters
    ----------
    call : RelayCall
        The relayed tool call to translate.
    vertical : str
        The Harness's own currently active vertical. Never read from
        `call.input`: nothing in the model's payload can name a different
        vertical than the one actually taking its turn.

    Returns
    -------
    AgentAction
        The translated action.

    Raises
    ------
    MalformedRelayCallError
        If `call.tool_name` isn't a relay tool name, or `call.input`
        doesn't carry the fields that tool's variant requires.
    """
    builder = _BUILDERS.get(call.tool_name)
    if builder is None:
        raise MalformedRelayCallError(f"not a relay tool: {call.tool_name!r}")
    return builder(call, vertical=vertical)


def outcome_to_wire(outcome: ActionOutcome) -> dict[str, Any]:
    """Render a Harness `ActionOutcome` as the reply a relay connection sends back.

    `ActionRejected` becomes a readable, unsuccessful tool result the model
    can react to and retry against (ADR 0007's retry loop), never a
    Pi-level `block`: `block` is reserved for the gate's own refusal of a
    call that was never a relay tool to begin with, not for a legitimate
    dispatch outcome the model is meant to read as feedback.

    Parameters
    ----------
    outcome : ActionOutcome
        What `Harness._dispatch` produced for the action this outcome
        answers.

    Returns
    -------
    dict[str, Any]
        `{"ok": bool, "output": str}`, exactly what the gate extension's
        tool `execute()` turns into an `AgentToolResult`.
    """
    match outcome:
        case ToolResult(ok=ok, output=output):
            return {"ok": ok, "output": output}
        case ActionRejected(reason=reason):
            return {"ok": False, "output": reason}
        case None:
            return {"ok": True, "output": ""}
