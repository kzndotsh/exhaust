"""The Harness: drives one agent through one Workspace's Playbook (ADR 0001, 0005, 0007).

`Harness` is the single chokepoint between an untrusted agent's proposed
actions and the privileged domain calls those actions can trigger. It is
the one module permitted to compose every other domain module (`ledger`,
`findings`, `oracle`, `rig`, `scope_contract`, `evidence`, `delimiter`,
`catalog`); every other domain module stays independent of the others,
enforced by `import-linter`.

This slice implements the `RecordFinding`, `ProposeVerdict`, and
`SetVerticalState` actions end to end. `SandboxCall`, `RealTargetCall`,
and `SelfReport` are left as explicit `NotImplementedError` seams: the
first two need a real Rig tool-bridge composition to be worth wiring up
beyond what's already proven in `rig`'s own tests, and `SelfReport`
needs a decision on where its persisted per-vertical attempt log lives
(see the architect synthesis) before `_validate_exhaustion` can be real.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from exhaust.catalog import VerticalEntry, discover_verticals
from exhaust.evidence import (
    EvidenceAlreadyExistsError,
    EvidenceCopyVerificationError,
    EvidenceFileMissingError,
    PathEscapesScratchError,
    SymlinkEvidenceError,
    promote_evidence,
)
from exhaust.findings import (
    AcceptedRiskOverrideError,
    ContradictingEvidenceOnRecordError,
    FindingAlreadyExistsError,
    MissingOracleResultError,
    OracleCheckFailedError,
    RecordedBy,
    UnknownFindingError,
    Verdict,
    new_finding,
)
from exhaust.findings import (
    record_finding as findings_record_finding,
)
from exhaust.findings import (
    record_verdict as findings_record_verdict,
)
from exhaust.harness.actions import (
    ActionOutcome,
    ActionRejected,
    AgentAction,
    ProposeVerdict,
    RealTargetCall,
    RecordFinding,
    SandboxCall,
    SelfReport,
    SetVerticalState,
)
from exhaust.harness.agent import AgentSession, AgentTurnRequest
from exhaust.harness.budget import RunBudget
from exhaust.ledger import (
    InvalidTransitionError,
    ReasonRequiredError,
    ResumedBy,
    VerticalState,
    current_state,
    is_workspace_done,
    transition,
)
from exhaust.oracle import OracleResult
from exhaust.rig import ToolBridge, ToolResult


class HaltReason(StrEnum):
    """Why a `Harness.run()` call returned."""

    BUDGET_EXHAUSTED = "budget_exhausted"
    ALL_TERMINAL = "all_terminal"
    HUMAN_REQUIRED = "human_required"


@dataclass(frozen=True)
class RunOutcome:
    """What a `Harness.run()` call produced.

    Richer than a bare status so a caller can report something useful
    without a second call to `ledger.load_ledger`.

    Attributes
    ----------
    done : bool
        Whether every named vertical was terminal when the run stopped.
    halted_reason : HaltReason
        Why the run stopped.
    final_states : dict[str, VerticalState]
        Every named vertical's state at stop time.
    needs_human : tuple[str, ...]
        Verticals left `blocked`.
    turns_spent : int
        How many agent turns this call actually took.
    """

    done: bool
    halted_reason: HaltReason
    final_states: dict[str, VerticalState]
    needs_human: tuple[str, ...]
    turns_spent: int

    def summary(self) -> str:
        """Render one line per vertical's final state.

        Returns
        -------
        str
            `"<vertical>: <state>"` per line, sorted by vertical name.
        """
        if not self.final_states:
            return "(no verticals)"
        return "\n".join(
            f"{name}: {state.value}" for name, state in sorted(self.final_states.items())
        )


def resume_blocked_vertical(workspace_dir: Path, vertical: str, note: str) -> None:
    """Resume a `blocked` vertical. The only human-privileged entry point.

    A free function, not a `Harness` method: resolving a blocked vertical
    needs no live `AgentSession`, no Rig bridges, nothing a full `Harness`
    construction would otherwise require. Call `Harness.run()` again
    afterward to actually continue it.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace whose ledger this updates.
    vertical : str
        The blocked vertical to resume.
    note : str
        Why it's safe to resume, recorded as the transition's reason.

    Raises
    ------
    InvalidTransitionError
        If `vertical` isn't currently `blocked`.
    """
    transition(
        workspace_dir, vertical, VerticalState.IN_PROGRESS, reason=note, resumed_by=ResumedBy.HUMAN
    )


class Harness:
    """Drives one agent through one Workspace's Playbook.

    Binds a Workspace, an agent session, and a Rig bridge map across many
    turns — the identity and mutable state across calls this codebase
    reserves a real class for (alongside Rig tool bridges). Durable truth
    lives on disk (the ledger, the findings log); the instance itself
    holds only what one `run()` call needs.
    """

    def __init__(
        self,
        workspace_dir: Path,
        skills_dir: Path,
        target: str,
        *,
        agent: AgentSession,
        bridges: Mapping[str, ToolBridge] | None = None,
    ) -> None:
        self._workspace_dir = workspace_dir
        self._skills_dir = skills_dir
        self._target = target
        self._agent = agent
        self._bridges: Mapping[str, ToolBridge] = bridges if bridges is not None else {}
        self._scratch_dir = workspace_dir / "poc"
        self._evidence_dir = workspace_dir / "findings" / "evidence"

    @classmethod
    def open(
        cls,
        workspace_dir: Path,
        skills_dir: Path,
        target: str,
        *,
        agent: AgentSession,
        bridges: Mapping[str, ToolBridge] | None = None,
    ) -> "Harness":
        """Assemble a Harness for an existing Workspace.

        Parameters
        ----------
        workspace_dir : Path
            The Workspace to drive.
        skills_dir : Path
            Where to read the vertical catalog from (ADR 0016).
        target : str
            The Target this Workspace researches.
        agent : AgentSession
            The agent adapter to drive.
        bridges : Mapping[str, ToolBridge] | None
            Registered Rig tool bridges. Defaults to empty: no real
            bridges exist yet, and a run with none simply cannot perform
            a tool call that needs one.

        Returns
        -------
        Harness
            The assembled Harness.
        """
        return cls(workspace_dir, skills_dir, target, agent=agent, bridges=bridges)

    def run(self, *, budget: RunBudget) -> RunOutcome:
        """Drive verticals until the Workspace is done, blocked, or out of budget.

        Idempotent across process restarts: all state is on disk (the
        ledger, the findings log), so calling this again after a halt
        resumes exactly the non-terminal verticals.

        Parameters
        ----------
        budget : RunBudget
            How far this call is allowed to go.

        Returns
        -------
        RunOutcome
            Why the run stopped and the state it left behind.
        """
        turns_spent = 0
        names = [entry.name for entry in discover_verticals(self._skills_dir)]

        while True:
            if is_workspace_done(self._workspace_dir, names):
                return RunOutcome(
                    done=True,
                    halted_reason=HaltReason.ALL_TERMINAL,
                    final_states=self._final_states(names),
                    needs_human=self._blocked(names),
                    turns_spent=turns_spent,
                )
            if turns_spent >= budget.max_turns:
                return RunOutcome(
                    done=False,
                    halted_reason=HaltReason.BUDGET_EXHAUSTED,
                    final_states=self._final_states(names),
                    needs_human=self._blocked(names),
                    turns_spent=turns_spent,
                )

            entry = self._pick_active_vertical(names)
            if entry is None:
                return RunOutcome(
                    done=False,
                    halted_reason=HaltReason.HUMAN_REQUIRED,
                    final_states=self._final_states(names),
                    needs_human=self._blocked(names),
                    turns_spent=turns_spent,
                )

            self._run_one_turn(entry)
            turns_spent += 1

    def _final_states(self, names: list[str]) -> dict[str, VerticalState]:
        return {name: current_state(self._workspace_dir, name) for name in names}

    def _blocked(self, names: list[str]) -> tuple[str, ...]:
        return tuple(
            name
            for name in names
            if current_state(self._workspace_dir, name) == VerticalState.BLOCKED
        )

    def _pick_active_vertical(self, names: list[str]) -> VerticalEntry | None:
        """Pick the next vertical to drive, or None if nothing is runnable.

        Fixed strategy for v1, not pluggable: prefer a vertical already
        `in_progress` or `retryable` (resume it) over starting a new
        `pending` one. Gate-based ordering (`VerticalEntry.gate`) is
        deferred; this sketch's own open questions haven't settled what
        a gate names. `blocked` and terminal verticals are never
        returned.
        """
        entries = {entry.name: entry for entry in discover_verticals(self._skills_dir)}

        resumable = (VerticalState.IN_PROGRESS, VerticalState.RETRYABLE)
        for name in names:
            if current_state(self._workspace_dir, name) in resumable:
                return entries[name]

        for name in names:
            if current_state(self._workspace_dir, name) == VerticalState.PENDING:
                return entries[name]

        return None

    def _run_one_turn(self, entry: VerticalEntry) -> None:
        request = AgentTurnRequest(vertical=entry, procedure="", available_tools=())
        action = self._agent.step(request)

        # A PENDING vertical only moves to IN_PROGRESS once we know the agent isn't
        # skipping it: SKIPPED is only a legal transition from PENDING (ADR 0011's gate
        # exclusion happens before any work starts), so marking IN_PROGRESS first would
        # make every skip request arrive too late to ever succeed.
        still_pending = current_state(self._workspace_dir, entry.name) == VerticalState.PENDING
        if still_pending and not isinstance(action, SetVerticalState):
            transition(self._workspace_dir, entry.name, VerticalState.IN_PROGRESS)

        outcome = self._dispatch(action, entry.name)
        self._agent.observe(outcome)

    def _dispatch(self, action: AgentAction, _active: str) -> ActionOutcome:
        """Validate and perform one proposed action, or reject it.

        The single chokepoint: the only path from an untrusted action to
        a real effect anywhere in this module. `_active` names the
        vertical this turn belongs to; unused until the `SandboxCall`,
        `RealTargetCall`, and `SelfReport` branches are implemented.
        """
        match action:
            case SandboxCall():
                raise NotImplementedError("sandbox tool calls: no Rig composition wired up yet")
            case RealTargetCall():
                raise NotImplementedError("real-Target tool calls: no Rig composition wired up yet")
            case RecordFinding() as a:
                return self._record_finding(a)
            case ProposeVerdict() as a:
                return self._propose_verdict(a)
            case SelfReport():
                raise NotImplementedError(
                    "exhaustion validation: persisted attempt-log location not decided yet"
                )
            case SetVerticalState() as a:
                return self._set_state(a)

    def _record_finding(self, a: RecordFinding) -> ActionOutcome:
        try:
            destination = promote_evidence(
                self._scratch_dir, a.evidence_scratch_path, self._evidence_dir
            )
        except (
            SymlinkEvidenceError,
            EvidenceFileMissingError,
            PathEscapesScratchError,
            EvidenceCopyVerificationError,
            EvidenceAlreadyExistsError,
        ) as exc:
            return ActionRejected(str(exc))

        finding = new_finding(
            self._target, a.vertical, a.claim, a.severity, a.scope, str(destination)
        )
        try:
            findings_record_finding(self._workspace_dir, finding)
        except FindingAlreadyExistsError as exc:
            return ActionRejected(str(exc))

        return ToolResult(ok=True, output=f"recorded finding {finding.id}")

    def _propose_verdict(self, a: ProposeVerdict) -> ActionOutcome:
        oracle_result = self._obtain_oracle_result(a.finding_id, a.verdict)
        try:
            findings_record_verdict(
                self._workspace_dir,
                a.finding_id,
                a.verdict,
                RecordedBy.AGENT,
                oracle_result=oracle_result,
            )
        except (
            MissingOracleResultError,
            OracleCheckFailedError,
            ContradictingEvidenceOnRecordError,
            AcceptedRiskOverrideError,
            UnknownFindingError,
        ) as exc:
            return ActionRejected(str(exc))

        return ToolResult(ok=True, output=f"recorded verdict on {a.finding_id}")

    def _obtain_oracle_result(self, _finding_id: str, _verdict: Verdict) -> OracleResult | None:
        """Return the Oracle seam's result for a proposed Verdict.

        Always None today: nothing automated can confirm a finding yet
        (ADR 0008), so `confirmed` stays unreachable by construction, not
        by policy. The parameters name the contract a real Oracle-runner
        will need; they're unused until one exists.
        """
        return None

    def _set_state(self, a: SetVerticalState) -> ActionOutcome:
        try:
            transition(self._workspace_dir, a.vertical, a.to, reason=a.reason)
        except (InvalidTransitionError, ReasonRequiredError) as exc:
            return ActionRejected(str(exc))

        return ToolResult(ok=True, output=f"{a.vertical} -> {a.to.value}")
