from pathlib import Path

import pytest

from exhaust.findings import (
    FindingScope,
    RecordedBy,
    Verdict,
    VerdictType,
    load_findings,
    new_finding,
)
from exhaust.findings import record_finding as findings_record_finding
from exhaust.harness import (
    ActionOutcome,
    AgentAction,
    ExhaustionAttestation,
    HaltReason,
    Harness,
    ProposeVerdict,
    RealTargetCall,
    RecordFinding,
    RunBudget,
    RunOutcome,
    SandboxCall,
    SelfReport,
    SetVerticalState,
    resume_blocked_vertical,
)
from exhaust.harness.agent import AgentTurnRequest
from exhaust.ledger import VerticalState, current_state, transition
from exhaust.rig import ToolResult


class ScriptedAgent:
    """A fake AgentSession: plays back a fixed list of actions, one per step()."""

    def __init__(self, actions: list[AgentAction]) -> None:
        self._actions = iter(actions)
        self.observed: list[ActionOutcome] = []

    def step(self, request: AgentTurnRequest) -> AgentAction:
        del request
        return next(self._actions)

    def observe(self, outcome: ActionOutcome) -> None:
        self.observed.append(outcome)


def _write_skill(skills_dir: Path, slug: str, front_matter: str) -> None:
    skill_dir = skills_dir / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{front_matter}---\nBody.\n")


def test_run_on_an_empty_playbook_is_immediately_done(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=ScriptedAgent([]))

    outcome = harness.run(budget=RunBudget(max_turns=10))

    assert outcome.done is True
    assert outcome.halted_reason is HaltReason.ALL_TERMINAL
    assert outcome.turns_spent == 0


def test_skip_vertical_reaches_terminal_and_completes_the_run(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    agent = ScriptedAgent(
        [SetVerticalState(vertical="injection", to=VerticalState.SKIPPED, reason="not applicable")]
    )

    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    outcome = harness.run(budget=RunBudget(max_turns=10))

    assert outcome.done is True
    assert outcome.final_states == {"injection": VerticalState.SKIPPED}
    assert outcome.turns_spent == 1
    assert agent.observed == [ToolResult(ok=True, output="injection -> skipped")]


def test_budget_exhausted_leaves_vertical_in_progress_and_is_resumable(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    (tmp_path / "poc").mkdir()
    (tmp_path / "poc" / "poc.py").write_text("evidence\n")

    # RecordFinding doesn't change the vertical's ledger state, so one turn of it leaves
    # the vertical IN_PROGRESS when the budget runs out.
    agent = ScriptedAgent(
        [
            RecordFinding(
                vertical="injection",
                claim="SQLi in search",
                severity="high",
                scope=FindingScope.SANDBOX,
                evidence_scratch_path=Path("poc.py"),
            )
        ]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    outcome = harness.run(budget=RunBudget(max_turns=1))

    assert outcome.done is False
    assert outcome.halted_reason is HaltReason.BUDGET_EXHAUSTED
    assert outcome.final_states == {"injection": VerticalState.IN_PROGRESS}

    # A later run, with a fresh agent, resumes the same vertical: it's picked up as
    # IN_PROGRESS rather than starting over from PENDING.
    (tmp_path / "poc" / "second.py").write_text("evidence 2\n")
    resumed_agent = ScriptedAgent(
        [
            RecordFinding(
                vertical="injection",
                claim="second pass",
                severity="low",
                scope=FindingScope.SANDBOX,
                evidence_scratch_path=Path("second.py"),
            )
        ]
    )
    resumed = Harness.open(tmp_path, skills_dir, "roundcube", agent=resumed_agent)
    resumed.run(budget=RunBudget(max_turns=1))
    assert current_state(tmp_path, "injection") == VerticalState.IN_PROGRESS
    assert len(load_findings(tmp_path)) == 2


def test_blocked_vertical_halts_the_run_as_human_required(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.BLOCKED, reason="ambiguous outcome")

    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=ScriptedAgent([]))
    outcome = harness.run(budget=RunBudget(max_turns=10))

    assert outcome.done is False
    assert outcome.halted_reason is HaltReason.HUMAN_REQUIRED
    assert outcome.needs_human == ("injection",)


def test_resume_blocked_vertical_then_run_completes_it(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    (tmp_path / "poc").mkdir()
    (tmp_path / "poc" / "poc.py").write_text("evidence\n")
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.BLOCKED, reason="ambiguous outcome")

    resume_blocked_vertical(tmp_path, "injection", note="reviewed, safe to continue")
    assert current_state(tmp_path, "injection") == VerticalState.IN_PROGRESS

    # A resumed, already-IN_PROGRESS vertical is drivable again: this would raise
    # HumanResumeRequiredError if the Harness still treated it as blocked.
    agent = ScriptedAgent(
        [
            RecordFinding(
                vertical="injection",
                claim="found after resume",
                severity="medium",
                scope=FindingScope.SANDBOX,
                evidence_scratch_path=Path("poc.py"),
            )
        ]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    outcome = harness.run(budget=RunBudget(max_turns=1))

    assert outcome.done is False
    assert outcome.final_states == {"injection": VerticalState.IN_PROGRESS}
    assert len(load_findings(tmp_path)) == 1


def test_record_finding_promotes_evidence_and_records_it(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    (tmp_path / "poc").mkdir()
    (tmp_path / "poc" / "poc.py").write_text("print('exploit')\n")

    agent = ScriptedAgent(
        [
            RecordFinding(
                vertical="injection",
                claim="SQLi in search",
                severity="high",
                scope=FindingScope.SANDBOX,
                evidence_scratch_path=Path("poc.py"),
            )
        ]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    records = load_findings(tmp_path)
    assert len(records) == 1
    assert records[0].finding.claim == "SQLi in search"
    promoted = tmp_path / "findings" / "evidence" / "poc.py"
    assert promoted.read_text() == "print('exploit')\n"


def test_record_finding_rejects_a_missing_scratch_file(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    (tmp_path / "poc").mkdir()

    agent = ScriptedAgent(
        [
            RecordFinding(
                vertical="injection",
                claim="SQLi in search",
                severity="high",
                scope=FindingScope.SANDBOX,
                evidence_scratch_path=Path("does-not-exist.py"),
            )
        ]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    assert load_findings(tmp_path) == []
    assert agent.observed[0] is not None
    assert not isinstance(agent.observed[0], ToolResult)


def test_propose_verdict_non_confirmed_is_recorded(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    finding = new_finding("roundcube", "injection", "SQLi", "high", FindingScope.SANDBOX, "poc.py")
    findings_record_finding(tmp_path, finding)

    agent = ScriptedAgent(
        [ProposeVerdict(finding_id=finding.id, verdict=Verdict(type=VerdictType.FALSE_POSITIVE))]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    records = load_findings(tmp_path)
    assert records[0].latest is not None
    assert records[0].latest.verdict.type == VerdictType.FALSE_POSITIVE
    assert records[0].latest.recorded_by == RecordedBy.AGENT


def test_propose_verdict_confirmed_is_rejected_with_no_oracle_seam(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    finding = new_finding("roundcube", "injection", "SQLi", "high", FindingScope.SANDBOX, "poc.py")
    findings_record_finding(tmp_path, finding)

    agent = ScriptedAgent(
        [ProposeVerdict(finding_id=finding.id, verdict=Verdict(type=VerdictType.CONFIRMED))]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    records = load_findings(tmp_path)
    assert records[0].latest is None


def test_set_vertical_state_rejects_an_invalid_transition(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)

    agent = ScriptedAgent(
        [SetVerticalState(vertical="injection", to=VerticalState.SKIPPED, reason="too late")]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    assert agent.observed[0] is not None
    assert not isinstance(agent.observed[0], ToolResult)
    assert current_state(tmp_path, "injection") == VerticalState.IN_PROGRESS


def test_record_finding_rejects_a_duplicate_claim(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    (tmp_path / "poc").mkdir()
    (tmp_path / "poc" / "a.py").write_text("a\n")
    (tmp_path / "poc" / "b.py").write_text("b\n")

    agent = ScriptedAgent(
        [
            RecordFinding(
                vertical="injection",
                claim="SQLi in search",
                severity="high",
                scope=FindingScope.SANDBOX,
                evidence_scratch_path=Path("a.py"),
            )
        ]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    # Same target/vertical/claim triple as above -> the same deterministic Finding id.
    agent2 = ScriptedAgent(
        [
            RecordFinding(
                vertical="injection",
                claim="SQLi in search",
                severity="high",
                scope=FindingScope.SANDBOX,
                evidence_scratch_path=Path("b.py"),
            )
        ]
    )
    harness2 = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent2)
    harness2.run(budget=RunBudget(max_turns=1))

    assert agent2.observed[0] is not None
    assert not isinstance(agent2.observed[0], ToolResult)
    assert len(load_findings(tmp_path)) == 1


def test_sandbox_call_is_not_implemented_yet(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    agent = ScriptedAgent(
        [SandboxCall(vertical="injection", tool="nuclei", method="scan", params={})]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)

    with pytest.raises(NotImplementedError):
        harness.run(budget=RunBudget(max_turns=1))


def test_real_target_call_is_not_implemented_yet(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    agent = ScriptedAgent(
        [
            RealTargetCall(
                vertical="injection", tool="nuclei", method="scan", params={}, target="acme.com"
            )
        ]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)

    with pytest.raises(NotImplementedError):
        harness.run(budget=RunBudget(max_turns=1))


def test_self_report_is_not_implemented_yet(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    attestation = ExhaustionAttestation(
        tools_exercised=(), findings_dispositioned=(), no_further_avenues=True
    )
    agent = ScriptedAgent([SelfReport(vertical="injection", attestation=attestation)])
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)

    with pytest.raises(NotImplementedError):
        harness.run(budget=RunBudget(max_turns=1))


def test_run_outcome_summary_lists_each_vertical() -> None:
    outcome = RunOutcome(
        done=True,
        halted_reason=HaltReason.ALL_TERMINAL,
        final_states={
            "injection": VerticalState.SKIPPED,
            "access_control": VerticalState.EXHAUSTED,
        },
        needs_human=(),
        turns_spent=3,
    )
    assert outcome.summary() == "access_control: exhausted\ninjection: skipped"


def test_run_outcome_summary_on_no_verticals() -> None:
    outcome = RunOutcome(
        done=True,
        halted_reason=HaltReason.ALL_TERMINAL,
        final_states={},
        needs_human=(),
        turns_spent=0,
    )
    assert outcome.summary() == "(no verticals)"
