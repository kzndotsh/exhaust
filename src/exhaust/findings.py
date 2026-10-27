"""Findings and Verdicts (ADR 0004, ADR 0007, ADR 0008, ADR 0019).

A Finding is an append-only claim: it is never deleted, and a Verdict
recorded on it never overwrites prior history, only adds to it. This
module is the structured data shape and append-only store a future
Harness tool call (ADR 0007) would write through, not the tool call
itself. It deliberately knows nothing about the Scope Contract or any
other domain module except `oracle`: ADR 0010 requires the function
that accepts a Finding as evidence-backed to itself refuse one that
didn't pass through an Oracle, so this module is the one place
permitted to depend on `exhaust.oracle` (see pyproject.toml's import
contracts).
"""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from exhaust.oracle import OracleResult, oracle_result_from_dict, oracle_result_to_dict

FINDINGS_FILENAME = "findings.jsonl"


class FindingScope(StrEnum):
    """Whether a Finding was demonstrated against the Sandbox or a real Target."""

    SANDBOX = "sandbox"
    REAL_TARGET = "real_target"


class VerdictType(StrEnum):
    """The six Verdicts a Finding can carry (ADR 0004, ADR 0019)."""

    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    DUPLICATE = "duplicate"
    FIXED = "fixed"
    ACCEPTED_RISK = "accepted_risk"
    NEEDS_CONFIRMATION = "needs_confirmation"


class RecordedBy(StrEnum):
    """Who recorded a Verdict: the investigating agent, or a human."""

    AGENT = "agent"
    HUMAN = "human"


# Every VerdictType that closes a Finding. needs_confirmation is the one
# exception (ADR 0019): it exists precisely to leave a Finding open pending
# more evidence, so a vertical can't be reported exhausted while one is
# outstanding.
TERMINAL_VERDICT_TYPES = frozenset(
    {
        VerdictType.CONFIRMED,
        VerdictType.FALSE_POSITIVE,
        VerdictType.DUPLICATE,
        VerdictType.FIXED,
        VerdictType.ACCEPTED_RISK,
    }
)


class FindingAlreadyExistsError(ValueError):
    """Raised when recording a Finding whose id is already on file."""


class UnknownFindingError(ValueError):
    """Raised when recording a Verdict against a Finding id not on file."""


class AcceptedRiskOverrideError(ValueError):
    """Raised when automation tries to overwrite a human accepted-risk Verdict."""


class MissingOracleResultError(ValueError):
    """Raised when recording `confirmed` with no OracleResult at all (ADR 0008)."""


class OracleCheckFailedError(ValueError):
    """Raised when recording `confirmed` with an OracleResult that didn't pass."""


class ContradictingEvidenceOnRecordError(ValueError):
    """Raised when confirming over a needs_confirmation with open contradictions (ADR 0019)."""


def compute_finding_id(target: str, vertical: str, claim: str) -> str:
    """Derive a Finding's deterministic id from its Target, vertical, and claim.

    Parameters
    ----------
    target : str
        The Target the Finding is about.
    vertical : str
        The vertical that produced the claim.
    claim : str
        The claimed weakness, verbatim.

    Returns
    -------
    str
        A stable hex digest. The same three inputs always produce the
        same id, so a re-discovered Finding is recognized as the same
        one rather than duplicated.
    """
    digest_input = "\x1f".join((target, vertical, claim)).encode()
    return hashlib.sha256(digest_input).hexdigest()


@dataclass(frozen=True)
class Finding:
    """One claimed weakness against a Target (ADR 0004).

    Attributes
    ----------
    id : str
        Deterministic id, from `compute_finding_id`.
    target : str
        The Target this Finding is about.
    vertical : str
        The vertical that produced this claim.
    claim : str
        The claimed weakness, in prose.
    severity : str
        The claimed severity (e.g. low, medium, high, critical).
    scope : FindingScope
        Whether this was demonstrated against the Sandbox or a real Target.
    evidence : str
        A pointer to or description of the repro/evidence.
    """

    id: str
    target: str
    vertical: str
    claim: str
    severity: str
    scope: FindingScope
    evidence: str


def _finding_to_dict(finding: Finding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "target": finding.target,
        "vertical": finding.vertical,
        "claim": finding.claim,
        "severity": finding.severity,
        "scope": finding.scope.value,
        "evidence": finding.evidence,
    }


def _finding_from_dict(data: dict[str, Any]) -> Finding:
    return Finding(
        id=data["id"],
        target=data["target"],
        vertical=data["vertical"],
        claim=data["claim"],
        severity=data["severity"],
        scope=FindingScope(data["scope"]),
        evidence=data["evidence"],
    )


def new_finding(
    target: str,
    vertical: str,
    claim: str,
    severity: str,
    scope: FindingScope,
    evidence: str,
) -> Finding:
    """Build a Finding with its id computed from `target`, `vertical`, `claim`.

    Parameters
    ----------
    target : str
        The Target this Finding is about.
    vertical : str
        The vertical that produced this claim.
    claim : str
        The claimed weakness, in prose.
    severity : str
        The claimed severity.
    scope : FindingScope
        Whether this was demonstrated against the Sandbox or a real Target.
    evidence : str
        A pointer to or description of the repro/evidence.

    Returns
    -------
    Finding
        The constructed Finding.
    """
    return Finding(
        id=compute_finding_id(target, vertical, claim),
        target=target,
        vertical=vertical,
        claim=claim,
        severity=severity,
        scope=scope,
        evidence=evidence,
    )


@dataclass(frozen=True)
class Verdict:
    """A typed outcome recorded on a Finding (ADR 0004, ADR 0007, ADR 0019).

    `requirements`, `supporting_evidence`, and `contradicting_evidence`
    are only meaningful for `VerdictType.NEEDS_CONFIRMATION` (ADR 0019);
    any other type must leave them unset.

    Attributes
    ----------
    type : VerdictType
        The recorded outcome.
    note : str
        Free-text context.
    requirements : str | None
        What evidence would resolve a `needs_confirmation` Verdict.
    supporting_evidence : tuple[str, ...]
        Evidence gathered so far that supports confirmation.
    contradicting_evidence : tuple[str, ...]
        Evidence gathered so far that argues against confirmation.
    """

    type: VerdictType
    note: str = ""
    requirements: str | None = None
    supporting_evidence: tuple[str, ...] = ()
    contradicting_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Enforce ADR 0019's fields-only-on-needs_confirmation rule."""
        if self.type == VerdictType.NEEDS_CONFIRMATION:
            if not self.requirements:
                raise ValueError("needs_confirmation requires 'requirements'")
        elif self.requirements or self.supporting_evidence or self.contradicting_evidence:
            raise ValueError(
                "requirements/supporting_evidence/contradicting_evidence are "
                "only valid on a needs_confirmation Verdict"
            )


def _verdict_to_dict(verdict: Verdict) -> dict[str, Any]:
    return {
        "type": verdict.type.value,
        "note": verdict.note,
        "requirements": verdict.requirements,
        "supporting_evidence": list(verdict.supporting_evidence),
        "contradicting_evidence": list(verdict.contradicting_evidence),
    }


def _verdict_from_dict(data: dict[str, Any]) -> Verdict:
    return Verdict(
        type=VerdictType(data["type"]),
        note=data.get("note", ""),
        requirements=data.get("requirements"),
        supporting_evidence=tuple(data.get("supporting_evidence", ())),
        contradicting_evidence=tuple(data.get("contradicting_evidence", ())),
    )


@dataclass(frozen=True)
class VerdictEntry:
    """A Verdict plus who recorded it and what Oracle result backs it.

    Attributes
    ----------
    verdict : Verdict
        The recorded Verdict.
    recorded_by : RecordedBy
        Who recorded it.
    oracle_result : OracleResult | None
        The Oracle result backing a `confirmed` Verdict (ADR 0008), or
        None for any other Verdict type.
    """

    verdict: Verdict
    recorded_by: RecordedBy
    oracle_result: OracleResult | None = None

    def __post_init__(self) -> None:
        """Enforce ADR 0008's confirmed-requires-a-passing-Oracle rule here too.

        `record_verdict` already enforces this before ever constructing a
        `VerdictEntry`, but the rule belongs on the type itself (matching
        `Verdict.__post_init__`'s own ADR 0019 check in this file), not
        only in one caller's function body: a `VerdictEntry` built any
        other way (a migration, a bulk importer, a future recording path)
        must not be able to bypass it.
        """
        if self.verdict.type == VerdictType.CONFIRMED and (
            self.oracle_result is None or not self.oracle_result.passed
        ):
            raise MissingOracleResultError(
                "a confirmed VerdictEntry requires a passing oracle_result"
            )


@dataclass(frozen=True)
class FindingRecord:
    """A Finding and its full, append-only Verdict history.

    Attributes
    ----------
    finding : Finding
        The Finding itself.
    history : tuple[VerdictEntry, ...]
        Every Verdict recorded on it, oldest first.
    """

    finding: Finding
    history: tuple[VerdictEntry, ...]

    @property
    def latest(self) -> VerdictEntry | None:
        """The most recently recorded Verdict, or None if there isn't one."""
        return self.history[-1] if self.history else None


def _findings_path(workspace_dir: Path) -> Path:
    return workspace_dir / "findings" / FINDINGS_FILENAME


def _read_events(workspace_dir: Path) -> list[dict[str, Any]]:
    path = _findings_path(workspace_dir)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_event(workspace_dir: Path, event: dict[str, Any]) -> None:
    path = _findings_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def _verdict_entry_from_event(event: dict[str, Any]) -> VerdictEntry:
    return VerdictEntry(
        verdict=_verdict_from_dict(event),
        recorded_by=RecordedBy(event["recorded_by"]),
        oracle_result=oracle_result_from_dict(event.get("oracle_result")),
    )


def _latest_entry_for(events: list[dict[str, Any]], finding_id: str) -> VerdictEntry | None:
    # Scans the raw dicts in reverse and builds at most one VerdictEntry,
    # rather than reconstructing every verdict event for this finding just
    # to keep the last one.
    for event in reversed(events):
        if event["kind"] == "verdict" and event["finding_id"] == finding_id:
            return _verdict_entry_from_event(event)
    return None


def record_finding(workspace_dir: Path, finding: Finding) -> None:
    """Append a new Finding to the Workspace's append-only log.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to record into.
    finding : Finding
        The Finding to record.

    Raises
    ------
    FindingAlreadyExistsError
        If a Finding with this id is already on file. Findings are
        never deleted, so there is nothing to overwrite; a duplicate id
        means the caller should look the existing one up instead.
    """
    events = _read_events(workspace_dir)
    if any(e["kind"] == "finding" and e["id"] == finding.id for e in events):
        raise FindingAlreadyExistsError(finding.id)
    _append_event(workspace_dir, {"kind": "finding", **_finding_to_dict(finding)})


def record_verdict(
    workspace_dir: Path,
    finding_id: str,
    verdict: Verdict,
    recorded_by: RecordedBy,
    oracle_result: OracleResult | None = None,
) -> None:
    """Append a Verdict to an existing Finding's history.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to record into.
    finding_id : str
        The Finding this Verdict applies to.
    verdict : Verdict
        The Verdict to record.
    recorded_by : RecordedBy
        Who is recording it.
    oracle_result : OracleResult | None
        Required, and must have `passed=True`, when `verdict.type` is
        `confirmed` (ADR 0008). Ignored, and never persisted, for any
        other Verdict type.

    Raises
    ------
    UnknownFindingError
        If no Finding with `finding_id` has been recorded.
    AcceptedRiskOverrideError
        If the latest recorded Verdict is a human-recorded accepted_risk
        and `recorded_by` is the agent: a manual accepted-risk marker is
        never silently overwritten by automation (ADR 0004).
    MissingOracleResultError
        If `verdict.type` is `confirmed` and no `oracle_result` was given
        at all: a `confirmed` Verdict requires a host-run Oracle, not
        just the agent's say-so (ADR 0008).
    OracleCheckFailedError
        If `verdict.type` is `confirmed` and `oracle_result` was given
        but didn't pass.
    ContradictingEvidenceOnRecordError
        If `verdict.type` is `confirmed` and the latest recorded Verdict
        is `needs_confirmation` carrying unresolved
        `contradicting_evidence`: a promotion to confirmed is only valid
        once nothing contradicts it on record (ADR 0019).
    """
    events = _read_events(workspace_dir)
    if not any(e["kind"] == "finding" and e["id"] == finding_id for e in events):
        raise UnknownFindingError(finding_id)

    latest = _latest_entry_for(events, finding_id)
    if (
        latest is not None
        and latest.verdict.type == VerdictType.ACCEPTED_RISK
        and latest.recorded_by == RecordedBy.HUMAN
        and recorded_by == RecordedBy.AGENT
    ):
        raise AcceptedRiskOverrideError(finding_id)

    if verdict.type == VerdictType.CONFIRMED:
        if oracle_result is None:
            raise MissingOracleResultError(finding_id)
        if not oracle_result.passed:
            raise OracleCheckFailedError(finding_id)
        if (
            latest is not None
            and latest.verdict.type == VerdictType.NEEDS_CONFIRMATION
            and latest.verdict.contradicting_evidence
        ):
            raise ContradictingEvidenceOnRecordError(finding_id)

    persisted_oracle_result = oracle_result if verdict.type == VerdictType.CONFIRMED else None
    _append_event(
        workspace_dir,
        {
            "kind": "verdict",
            "finding_id": finding_id,
            **_verdict_to_dict(verdict),
            "recorded_by": recorded_by.value,
            "oracle_result": oracle_result_to_dict(persisted_oracle_result),
        },
    )


def load_findings(workspace_dir: Path) -> list[FindingRecord]:
    """Reconstruct every Finding and its full Verdict history.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to read from.

    Returns
    -------
    list[FindingRecord]
        Every Finding recorded in this Workspace, in the order they
        were first recorded, each with its complete Verdict history.
    """
    events = _read_events(workspace_dir)
    findings: dict[str, Finding] = {}
    histories: dict[str, list[VerdictEntry]] = {}
    order: list[str] = []

    for event in events:
        if event["kind"] == "finding":
            finding = _finding_from_dict(event)
            findings[finding.id] = finding
            histories[finding.id] = []
            order.append(finding.id)
        elif event["kind"] == "verdict":
            histories[event["finding_id"]].append(_verdict_entry_from_event(event))

    return [FindingRecord(finding=findings[fid], history=tuple(histories[fid])) for fid in order]
