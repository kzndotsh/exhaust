"""The closed set of things an agent may ask the Harness to do (ADR 0007).

ADR 0007's "typed tools, not prose" generalized to every state-changing
request an agent can make, not just a Verdict: an agent proposes one of
these; the Harness validates and performs the privileged effect itself,
or rejects it. There is deliberately no field anywhere in this module
that lets an agent supply its own `OracleResult` (ADR 0008) or request a
human-only ledger transition (ADR 0015) — those capabilities don't exist
in this vocabulary at all, rather than existing and being checked at
runtime.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from exhaust.findings import FindingScope, Verdict
from exhaust.ledger import VerticalState
from exhaust.rig import ToolResult


@dataclass(frozen=True)
class SandboxCall:
    """A tool call that touches only the Workspace's Sandbox. No scope check.

    Attributes
    ----------
    vertical : str
        The vertical this call is made on behalf of.
    tool : str
        The Rig tool to call.
    method : str
        Which of that tool's methods to invoke.
    params : Mapping[str, Any]
        Passed through to the tool.
    """

    vertical: str
    tool: str
    method: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class RealTargetCall:
    """A tool call that touches the real Target (ADR 0003).

    `target` is mandatory, not optional: it is what gets re-checked
    against the Scope Contract immediately before execution. A shared
    `scope` flag on one call type was considered and rejected in favor of
    this separate type, so the scope check is a match arm the dispatcher
    cannot skip, not a runtime branch a reviewer has to trust was taken.

    Attributes
    ----------
    vertical : str
        The vertical this call is made on behalf of.
    tool : str
        The Rig tool to call.
    method : str
        Which of that tool's methods to invoke.
    params : Mapping[str, Any]
        Passed through to the tool.
    target : str
        The real Target this call is about to touch.
    """

    vertical: str
    tool: str
    method: str
    params: Mapping[str, Any]
    target: str


@dataclass(frozen=True)
class RecordFinding:
    """Claim a weakness. Promotes evidence and records the Finding in one step.

    `evidence_scratch_path` names a file in the agent's own scratch space
    that has NOT been promoted yet (ADR 0010): the dispatcher promotes it
    and records the Finding together, so there is no separate
    propose-then-record pair whose bookkeeping could go stale across a
    crash between the two calls.

    Attributes
    ----------
    vertical : str
        The vertical this Finding belongs to.
    claim : str
        The claimed weakness, in prose.
    severity : str
        The claimed severity.
    scope : FindingScope
        Whether this was demonstrated against the Sandbox or a real Target.
    evidence_scratch_path : Path
        The evidence file's path, relative to the agent's scratch dir.
    """

    vertical: str
    claim: str
    severity: str
    scope: FindingScope
    evidence_scratch_path: Path


@dataclass(frozen=True)
class ProposeVerdict:
    """Propose a Verdict on a Finding.

    There is no `oracle_result` field: the agent cannot supply its own
    proof of confirmation even by construction. Only the Harness's own
    Oracle-runner seam can obtain one.

    Attributes
    ----------
    finding_id : str
        The Finding this Verdict applies to.
    verdict : Verdict
        The proposed Verdict.
    """

    finding_id: str
    verdict: Verdict


@dataclass(frozen=True)
class ExhaustionAttestation:
    """Structured, falsifiable claims backing a vertical's exhaustion (ADR 0005).

    The Harness checks these against facts it already holds; it never
    takes `no_further_avenues` on faith. That field is necessary but
    never sufficient on its own.

    Attributes
    ----------
    tools_exercised : tuple[str, ...]
        Tools the agent claims to have run on this vertical. Checked
        against this vertical's persisted attempt record.
    findings_dispositioned : tuple[str, ...]
        Finding ids the agent claims are all resolved. Checked against
        `findings.load_findings`: every Finding this vertical opened must
        carry a terminal Verdict.
    no_further_avenues : bool
        The agent's own claim that nothing else is worth trying.
    """

    tools_exercised: tuple[str, ...]
    findings_dispositioned: tuple[str, ...]
    no_further_avenues: bool


@dataclass(frozen=True)
class SelfReport:
    """The forced self-report turn (ADR 0005): attest a vertical is exhausted.

    Attributes
    ----------
    vertical : str
        The vertical being reported exhausted.
    attestation : ExhaustionAttestation
        The structured claims backing the attestation.
    """

    vertical: str
    attestation: ExhaustionAttestation


@dataclass(frozen=True)
class SetVerticalState:
    """A narrow, agent-legal ledger transition. Today, only skipping.

    `to` is `Literal[VerticalState.SKIPPED]`, not the full `VerticalState`
    enum: a human-only transition (`blocked` -> `in_progress`) isn't even
    expressible through this type (ADR 0015).

    Attributes
    ----------
    vertical : str
        The vertical to transition.
    to : Literal[VerticalState.SKIPPED]
        The target state. Only `SKIPPED` is legal from this type.
    reason : str
        Why, as the ledger requires for a `skipped` transition.
    """

    vertical: str
    to: Literal[VerticalState.SKIPPED]
    reason: str


AgentAction = (
    SandboxCall | RealTargetCall | RecordFinding | ProposeVerdict | SelfReport | SetVerticalState
)


class ExhaustionNotJustifiedError(ValueError):
    """Raised when a SelfReport's attestation doesn't match recorded facts."""


@dataclass(frozen=True)
class ActionRejected:
    """An action the Harness refused.

    Harness-authored, never delimiter-wrapped: it didn't come from the
    Target. Fed back to the agent so it can retry with a corrected call
    (ADR 0007).

    Attributes
    ----------
    reason : str
        Why the action was refused.
    """

    reason: str


ActionOutcome = ToolResult | ActionRejected | None
