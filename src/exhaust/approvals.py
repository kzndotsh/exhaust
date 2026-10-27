"""Pending approvals for consequential actions (ADR 0023).

A `RealTargetCall` whose method the Rig marked consequential, or a
`SelfReport`'s exhaustion attestation once its facts check out, isn't
dispatched the moment the earlier checks pass: it's held here until a
human approves the exact subject. Approving clears the way; it doesn't
execute anything itself (ADR 0023) — the agent must propose the same
action again, and the Harness re-checks for a matching approved record
before dispatching, so the Harness remains the only thing that ever
calls the Rig or transitions a vertical to exhausted.

This is independent of `ledger.py`'s `blocked` state on purpose: a
pending approval is scoped to one action, not a whole vertical, and
resolving it never touches the ledger. No `AgentAction` variant lets an
agent call `resolve` — the human-only boundary is enforced by that
capability not existing in the vocabulary at all, the same discipline
`harness/actions.py` already applies to Oracle results and ledger
transitions, rather than a runtime check on who's calling.
"""

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

APPROVALS_FILENAME = "approvals.json"


class ApprovalStatus(StrEnum):
    """A pending approval's current status."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass(frozen=True)
class ConsequentialCall:
    """A `RealTargetCall` whose method the Rig marked consequential (ADR 0018, 0023).

    Attributes
    ----------
    vertical : str
        The vertical this call is made on behalf of.
    tool : str
        The Rig tool to call.
    method : str
        Which of that tool's methods to invoke.
    params : dict[str, Any]
        The call's parameters.
    target : str
        The real Target this call is about to touch.
    """

    vertical: str
    tool: str
    method: str
    params: dict[str, Any]
    target: str


@dataclass(frozen=True)
class ExhaustionClaim:
    """A `SelfReport`'s attestation, checked but not yet human-approved (ADR 0023).

    Attributes
    ----------
    vertical : str
        The vertical being reported exhausted.
    tools_exercised : tuple[str, ...]
        The attestation's claimed tools, already checked against the
        attempt log by the time this is built.
    findings_dispositioned : tuple[str, ...]
        The attestation's claimed finding ids, already checked against
        the Findings store by the time this is built.
    """

    vertical: str
    tools_exercised: tuple[str, ...]
    findings_dispositioned: tuple[str, ...]


type ApprovalSubject = ConsequentialCall | ExhaustionClaim


@dataclass(frozen=True)
class PendingApproval:
    """One subject's current approval record.

    Attributes
    ----------
    subject : ApprovalSubject
        What's waiting on a human.
    status : ApprovalStatus
        Its current status.
    note : str | None
        Why, required for `approved` and `denied`, never for `pending`.
    """

    subject: ApprovalSubject
    status: ApprovalStatus
    note: str | None


class UnknownApprovalError(ValueError):
    """Raised when resolving a key with no pending record."""


class NoteRequiredError(ValueError):
    """Raised when approving or denying without a note."""


class AlreadyResolvedError(ValueError):
    """Raised when resolving a key that isn't currently pending."""


def _subject_payload(subject: ApprovalSubject) -> dict[str, Any]:
    """Render a subject as a JSON-safe dict, tagged by its own type name.

    The tag means a `ConsequentialCall` and an `ExhaustionClaim` that
    happen to share field values never collide on the same key, and it
    doubles as what a human reads back when deciding.
    """
    match subject:
        case ConsequentialCall():
            return {
                "kind": "consequential_call",
                "vertical": subject.vertical,
                "tool": subject.tool,
                "method": subject.method,
                "params": subject.params,
                "target": subject.target,
            }
        case ExhaustionClaim():
            return {
                "kind": "exhaustion_claim",
                "vertical": subject.vertical,
                "tools_exercised": list(subject.tools_exercised),
                "findings_dispositioned": list(subject.findings_dispositioned),
            }


def approval_key(subject: ApprovalSubject) -> str:
    """Return a deterministic key for `subject`, stable across repeated proposals.

    The same subject (same fields, same kind) always hashes to the same
    key, so an agent re-proposing the identical action finds the record
    a human already resolved, without needing a session or a live
    `Harness` to remember it.

    Parameters
    ----------
    subject : ApprovalSubject
        The call or claim to key.

    Returns
    -------
    str
        A short, stable hex digest.
    """
    canonical = json.dumps(_subject_payload(subject), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _approvals_path(workspace_dir: Path) -> Path:
    return workspace_dir / APPROVALS_FILENAME


def _load(workspace_dir: Path) -> dict[str, dict[str, Any]]:
    path = _approvals_path(workspace_dir)
    if not path.is_file():
        return {}
    data: dict[str, dict[str, Any]] = json.loads(path.read_text())
    return data


def _save(workspace_dir: Path, records: dict[str, dict[str, Any]]) -> None:
    path = _approvals_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(records, indent=2, sort_keys=True) + "\n"

    # Write-to-temp-then-rename, same as ledger.py: a crash mid-write never
    # leaves approvals.json truncated.
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(rendered)
    tmp_path.replace(path)


def is_approved(workspace_dir: Path, subject: ApprovalSubject) -> bool:
    """Check whether `subject` currently has an approved record.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to check.
    subject : ApprovalSubject
        The call or claim to check.

    Returns
    -------
    bool
        True only if a record for this exact subject exists and is
        `approved`. A `denied` or still-`pending` record is not enough.
    """
    records = _load(workspace_dir)
    record = records.get(approval_key(subject))
    return record is not None and record["status"] == ApprovalStatus.APPROVED.value


def request_approval(workspace_dir: Path, subject: ApprovalSubject) -> str:
    """Create a pending record for `subject` if one doesn't already exist.

    Idempotent: proposing the same subject repeatedly before a human
    acts leaves the existing record untouched rather than resetting it.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to record against.
    subject : ApprovalSubject
        The call or claim awaiting approval.

    Returns
    -------
    str
        The subject's key, to surface to the agent so it knows what to
        re-propose once a human has acted.
    """
    records = _load(workspace_dir)
    key = approval_key(subject)
    if key not in records:
        records[key] = {
            "subject": _subject_payload(subject),
            "status": ApprovalStatus.PENDING.value,
            "note": None,
        }
        _save(workspace_dir, records)
    return key


def resolve(
    workspace_dir: Path,
    key: str,
    *,
    decision: Literal[ApprovalStatus.APPROVED, ApprovalStatus.DENIED],
    note: str,
) -> None:
    """Approve or deny a pending record. The only human-privileged entry point.

    No `AgentAction` variant reaches this function; it exists to be
    called the way `harness.resume_blocked_vertical` is, by a human
    acting outside any agent turn.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace whose approvals this updates.
    key : str
        The record to resolve, from `request_approval`'s return value or
        an `ActionRejected` message that surfaced it.
    decision : Literal[ApprovalStatus.APPROVED, ApprovalStatus.DENIED]
        The human's decision.
    note : str
        Why, recorded on the record.

    Raises
    ------
    UnknownApprovalError
        If `key` has no record.
    AlreadyResolvedError
        If the record isn't currently `pending`.
    NoteRequiredError
        If `note` is empty.
    """
    if not note:
        raise NoteRequiredError(f"{key}: resolving requires a note")

    records = _load(workspace_dir)
    record = records.get(key)
    if record is None:
        raise UnknownApprovalError(key)
    if record["status"] != ApprovalStatus.PENDING.value:
        raise AlreadyResolvedError(f"{key}: already {record['status']}")

    record["status"] = decision.value
    record["note"] = note
    _save(workspace_dir, records)
