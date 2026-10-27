"""Findings and Verdicts (ADR 0004, ADR 0007, ADR 0019).

A Finding is an append-only claim: it is never deleted, and a Verdict
recorded on it never overwrites prior history, only adds to it. This
module is the structured data shape and append-only store a future
Harness tool call (ADR 0007) would write through, not the tool call
itself, and it deliberately knows nothing about the Scope Contract or
any other domain module (see the independence contract in
pyproject.toml).
"""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

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


class FindingAlreadyExistsError(ValueError):
    """Raised when recording a Finding whose id is already on file."""


class UnknownFindingError(ValueError):
    """Raised when recording a Verdict against a Finding id not on file."""


class AcceptedRiskOverrideError(ValueError):
    """Raised when automation tries to overwrite a human accepted-risk Verdict."""


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


@dataclass(frozen=True)
class VerdictEntry:
    """A Verdict plus who recorded it.

    Attributes
    ----------
    verdict : Verdict
        The recorded Verdict.
    recorded_by : RecordedBy
        Who recorded it.
    """

    verdict: Verdict
    recorded_by: RecordedBy


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


def _latest_entry_for(events: list[dict[str, Any]], finding_id: str) -> VerdictEntry | None:
    latest: VerdictEntry | None = None
    for event in events:
        if event["kind"] == "verdict" and event["finding_id"] == finding_id:
            latest = VerdictEntry(
                verdict=Verdict(
                    type=VerdictType(event["type"]),
                    note=event.get("note", ""),
                    requirements=event.get("requirements"),
                    supporting_evidence=tuple(event.get("supporting_evidence", ())),
                    contradicting_evidence=tuple(event.get("contradicting_evidence", ())),
                ),
                recorded_by=RecordedBy(event["recorded_by"]),
            )
    return latest


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
    _append_event(
        workspace_dir,
        {
            "kind": "finding",
            "id": finding.id,
            "target": finding.target,
            "vertical": finding.vertical,
            "claim": finding.claim,
            "severity": finding.severity,
            "scope": finding.scope.value,
            "evidence": finding.evidence,
        },
    )


def record_verdict(
    workspace_dir: Path,
    finding_id: str,
    verdict: Verdict,
    recorded_by: RecordedBy,
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

    Raises
    ------
    UnknownFindingError
        If no Finding with `finding_id` has been recorded.
    AcceptedRiskOverrideError
        If the latest recorded Verdict is a human-recorded accepted_risk
        and `recorded_by` is the agent: a manual accepted-risk marker is
        never silently overwritten by automation (ADR 0004).
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

    _append_event(
        workspace_dir,
        {
            "kind": "verdict",
            "finding_id": finding_id,
            "type": verdict.type.value,
            "note": verdict.note,
            "requirements": verdict.requirements,
            "supporting_evidence": list(verdict.supporting_evidence),
            "contradicting_evidence": list(verdict.contradicting_evidence),
            "recorded_by": recorded_by.value,
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
            finding = Finding(
                id=event["id"],
                target=event["target"],
                vertical=event["vertical"],
                claim=event["claim"],
                severity=event["severity"],
                scope=FindingScope(event["scope"]),
                evidence=event["evidence"],
            )
            findings[finding.id] = finding
            histories[finding.id] = []
            order.append(finding.id)
        elif event["kind"] == "verdict":
            histories[event["finding_id"]].append(
                VerdictEntry(
                    verdict=Verdict(
                        type=VerdictType(event["type"]),
                        note=event.get("note", ""),
                        requirements=event.get("requirements"),
                        supporting_evidence=tuple(event.get("supporting_evidence", ())),
                        contradicting_evidence=tuple(event.get("contradicting_evidence", ())),
                    ),
                    recorded_by=RecordedBy(event["recorded_by"]),
                )
            )

    return [FindingRecord(finding=findings[fid], history=tuple(histories[fid])) for fid in order]
