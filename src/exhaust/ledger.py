"""The per-vertical ledger (ADR 0005, ADR 0015).

The Harness's "done" is this ledger, not a heuristic or the agent's own
say-so: every vertical carries an explicit state, and the Workspace is
done only once every vertical the caller names is terminal. The ledger
tracks current run-state, rewritten on each transition, not an
append-only history the way Findings are (ADR 0004): a vertical's state
is a fact about where a run stands right now, not a claim that needs
preserving forever.

This module enforces the state machine's shape (which transitions are
legal, that leaving `blocked` is never silent). It does not validate
*why* a transition is legal, e.g. whether an `exhausted` attestation's
`exhaustion_criterion` is actually met: that is the Harness's job
(ADR 0005, ADR 0007), once a Harness exists.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

LEDGER_FILENAME = "ledger.json"


class VerticalState(StrEnum):
    """A vertical's state in the ledger (ADR 0005)."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RETRYABLE = "retryable"
    BLOCKED = "blocked"
    EXHAUSTED = "exhausted"
    SKIPPED = "skipped"


TERMINAL_STATES = frozenset({VerticalState.EXHAUSTED, VerticalState.SKIPPED})

_STATES_REQUIRING_A_REASON = frozenset(
    {VerticalState.RETRYABLE, VerticalState.BLOCKED, VerticalState.EXHAUSTED, VerticalState.SKIPPED}
)

_ALLOWED_TRANSITIONS: dict[VerticalState, frozenset[VerticalState]] = {
    VerticalState.PENDING: frozenset({VerticalState.IN_PROGRESS, VerticalState.SKIPPED}),
    VerticalState.IN_PROGRESS: frozenset(
        {VerticalState.RETRYABLE, VerticalState.BLOCKED, VerticalState.EXHAUSTED}
    ),
    VerticalState.RETRYABLE: frozenset({VerticalState.IN_PROGRESS}),
    VerticalState.BLOCKED: frozenset({VerticalState.IN_PROGRESS}),
    VerticalState.EXHAUSTED: frozenset(),
    VerticalState.SKIPPED: frozenset(),
}


class ResumedBy(StrEnum):
    """Who is resuming a `blocked` vertical: the agent, or a human."""

    AGENT = "agent"
    HUMAN = "human"


class InvalidTransitionError(ValueError):
    """Raised when a transition isn't legal from the vertical's current state."""


class ReasonRequiredError(ValueError):
    """Raised when a transition that must carry a reason doesn't have one."""


class HumanResumeRequiredError(ValueError):
    """Raised when resuming a `blocked` vertical without a human (ADR 0015)."""


@dataclass(frozen=True)
class LedgerEntry:
    """One vertical's current state.

    Attributes
    ----------
    vertical : str
        The vertical's name.
    state : VerticalState
        Its current state.
    reason : str | None
        Why it's in that state, required for every state except
        `pending` and `in_progress`.
    """

    vertical: str
    state: VerticalState
    reason: str | None


def _ledger_path(workspace_dir: Path) -> Path:
    return workspace_dir / LEDGER_FILENAME


def load_ledger(workspace_dir: Path) -> dict[str, LedgerEntry]:
    """Load every vertical's current entry from the Workspace's ledger.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to read from.

    Returns
    -------
    dict[str, LedgerEntry]
        Every vertical recorded so far, keyed by name. A vertical not
        present here is implicitly `pending`.
    """
    path = _ledger_path(workspace_dir)
    if not path.is_file():
        return {}
    data: dict[str, Any] = json.loads(path.read_text())
    return {
        name: LedgerEntry(
            vertical=name,
            state=VerticalState(entry["state"]),
            reason=entry.get("reason"),
        )
        for name, entry in data.items()
    }


def _save_ledger(workspace_dir: Path, ledger: dict[str, LedgerEntry]) -> None:
    path = _ledger_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        name: {"state": entry.state.value, "reason": entry.reason} for name, entry in ledger.items()
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def current_state(workspace_dir: Path, vertical: str) -> VerticalState:
    """Return `vertical`'s current state, `pending` if it isn't in the ledger yet.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to read from.
    vertical : str
        The vertical's name.

    Returns
    -------
    VerticalState
        Its current state.
    """
    entry = load_ledger(workspace_dir).get(vertical)
    return entry.state if entry is not None else VerticalState.PENDING


def transition(
    workspace_dir: Path,
    vertical: str,
    to: VerticalState,
    *,
    reason: str | None = None,
    resumed_by: ResumedBy | None = None,
) -> None:
    """Move `vertical` to state `to`, enforcing the ADR 0005 state machine.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace whose ledger this updates.
    vertical : str
        The vertical's name.
    to : VerticalState
        The state to move to.
    reason : str | None
        Why, required for every target state except `pending` and
        `in_progress`.
    resumed_by : ResumedBy | None
        Who is resuming, required and must be `human` when moving out
        of `blocked` (ADR 0015: never silently retried).

    Raises
    ------
    InvalidTransitionError
        If `to` isn't reachable from the vertical's current state, or
        the current state is already terminal.
    ReasonRequiredError
        If `to` requires a reason and none was given.
    HumanResumeRequiredError
        If resuming from `blocked` without `resumed_by=ResumedBy.HUMAN`.
    """
    ledger = load_ledger(workspace_dir)
    from_state = ledger[vertical].state if vertical in ledger else VerticalState.PENDING

    if from_state in TERMINAL_STATES or to not in _ALLOWED_TRANSITIONS[from_state]:
        raise InvalidTransitionError(f"{vertical}: {from_state} -> {to} is not allowed")

    if to in _STATES_REQUIRING_A_REASON and not reason:
        raise ReasonRequiredError(f"{vertical}: moving to {to} requires a reason")

    if from_state == VerticalState.BLOCKED and resumed_by != ResumedBy.HUMAN:
        raise HumanResumeRequiredError(f"{vertical}: resuming from blocked requires a human")

    ledger[vertical] = LedgerEntry(vertical=vertical, state=to, reason=reason)
    _save_ledger(workspace_dir, ledger)


def is_workspace_done(workspace_dir: Path, verticals: list[str]) -> bool:
    """Check whether every named vertical has reached a terminal state.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to check.
    verticals : list[str]
        Every vertical the Workspace's Playbook names. This module
        doesn't read the catalog itself (ADR 0016's generator lives in
        `catalog.py`, kept independent of this one); the caller passes
        the set.

    Returns
    -------
    bool
        True only if every named vertical is `exhausted` or `skipped`.
        A vertical with no ledger entry yet is implicitly `pending`,
        which is never done.
    """
    return all(current_state(workspace_dir, vertical) in TERMINAL_STATES for vertical in verticals)
