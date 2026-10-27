from pathlib import Path
from typing import Any

from exhaust.attempts import record_attempt, tools_exercised
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
    ActionRejected,
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
    resolve_pending_approval,
    resume_blocked_vertical,
)
from exhaust.harness.agent import AgentTurnRequest
from exhaust.ledger import VerticalState, current_state, transition
from exhaust.rig import MethodInfo, ToolInfo, ToolResult


class FakeScanner:
    """A minimal ToolBridge fake, mirroring the one in test_rig.py."""

    info = ToolInfo(name="fake-scanner", usage="scans fake things", doc="see fake-scanner docs")
    methods = (
        MethodInfo(name="scan", mutates=False, consequential=False, required_extent="recon"),
        MethodInfo(name="exploit", mutates=True, consequential=True, required_extent="full"),
    )

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run(self, method: str, **params: Any) -> ToolResult:
        self.calls.append((method, params))
        return ToolResult(ok=True, output=f"ran {method} with {params}")


def _write_scope_contract(workspace_dir: Path, target: str) -> None:
    (workspace_dir / "SCOPE_CONTRACT.yaml").write_text(
        f"target: {target}\nbasis: owned_infrastructure\nextent: full\n"
    )


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


def test_sandbox_call_dispatches_to_the_rig_and_logs_the_attempt(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    scanner = FakeScanner()
    agent = ScriptedAgent(
        [SandboxCall(vertical="injection", tool="fake-scanner", method="scan", params={})]
    )
    harness = Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    )
    harness.run(budget=RunBudget(max_turns=1))

    assert scanner.calls == [("scan", {})]
    assert agent.observed == [ToolResult(ok=True, output="ran scan with {}")]
    assert tools_exercised(tmp_path, "injection") == frozenset({"fake-scanner"})


def test_sandbox_call_rejects_an_unknown_tool_and_logs_nothing(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    agent = ScriptedAgent(
        [SandboxCall(vertical="injection", tool="nonexistent", method="scan", params={})]
    )
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    assert agent.observed[0] is not None
    assert not isinstance(agent.observed[0], ToolResult)
    assert tools_exercised(tmp_path, "injection") == frozenset()


def test_real_target_call_rejects_out_of_scope_target(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    scanner = FakeScanner()
    agent = ScriptedAgent(
        [
            RealTargetCall(
                vertical="injection",
                tool="fake-scanner",
                method="scan",
                params={},
                target="acme.com",
            )
        ]
    )
    harness = Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    )
    harness.run(budget=RunBudget(max_turns=1))

    assert scanner.calls == []
    assert agent.observed[0] is not None
    assert not isinstance(agent.observed[0], ToolResult)
    assert tools_exercised(tmp_path, "injection") == frozenset()


def test_real_target_call_with_a_scope_contract_dispatches_and_logs(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    _write_scope_contract(tmp_path, "acme.com")
    scanner = FakeScanner()
    agent = ScriptedAgent(
        [
            RealTargetCall(
                vertical="injection",
                tool="fake-scanner",
                method="scan",
                params={},
                target="acme.com",
            )
        ]
    )
    harness = Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    )
    harness.run(budget=RunBudget(max_turns=1))

    assert scanner.calls == [("scan", {})]
    assert agent.observed == [ToolResult(ok=True, output="ran scan with {}")]
    assert tools_exercised(tmp_path, "injection") == frozenset({"fake-scanner"})


def _exploit_call() -> RealTargetCall:
    return RealTargetCall(
        vertical="injection", tool="fake-scanner", method="exploit", params={}, target="acme.com"
    )


def test_real_target_call_needing_full_extent_is_rejected_under_a_recon_only_contract(
    tmp_path: Path,
) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    (tmp_path / "SCOPE_CONTRACT.yaml").write_text(
        "target: acme.com\nbasis: owned_infrastructure\nextent: recon\n"
    )
    scanner = FakeScanner()
    agent = ScriptedAgent(
        [
            RealTargetCall(
                vertical="injection",
                tool="fake-scanner",
                method="exploit",
                params={},
                target="acme.com",
            )
        ]
    )
    harness = Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    )
    harness.run(budget=RunBudget(max_turns=1))

    assert scanner.calls == []
    assert agent.observed[0] == ActionRejected(
        "acme.com is not an authorized Target for this Workspace"
    )
    assert tools_exercised(tmp_path, "injection") == frozenset()


def test_consequential_real_target_call_waits_for_a_human(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    _write_scope_contract(tmp_path, "acme.com")
    scanner = FakeScanner()

    agent = ScriptedAgent([_exploit_call()])
    Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    ).run(budget=RunBudget(max_turns=1))

    assert scanner.calls == []
    rejection = agent.observed[0]
    assert isinstance(rejection, ActionRejected)
    assert rejection.reason.startswith("awaiting human approval: ")
    key = rejection.reason.removeprefix("awaiting human approval: ")

    # Re-proposing before a human acts stays rejected, same key: nothing
    # executes just because the agent asked again.
    agent = ScriptedAgent([_exploit_call()])
    Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    ).run(budget=RunBudget(max_turns=1))
    assert scanner.calls == []
    assert agent.observed == [rejection]

    resolve_pending_approval(tmp_path, key, approve=True, note="reviewed the plan")

    # Approving doesn't execute it: the agent must propose it again.
    assert scanner.calls == []

    agent = ScriptedAgent([_exploit_call()])
    Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    ).run(budget=RunBudget(max_turns=1))

    assert scanner.calls == [("exploit", {})]
    assert agent.observed == [ToolResult(ok=True, output="ran exploit with {}")]
    assert tools_exercised(tmp_path, "injection") == frozenset({"fake-scanner"})


def test_denied_consequential_call_stays_rejected(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    _write_scope_contract(tmp_path, "acme.com")
    scanner = FakeScanner()

    agent = ScriptedAgent([_exploit_call()])
    Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    ).run(budget=RunBudget(max_turns=1))
    rejection = agent.observed[0]
    assert isinstance(rejection, ActionRejected)
    key = rejection.reason.removeprefix("awaiting human approval: ")

    resolve_pending_approval(tmp_path, key, approve=False, note="too risky for this engagement")

    agent = ScriptedAgent([_exploit_call()])
    Harness.open(
        tmp_path, skills_dir, "roundcube", agent=agent, bridges={"fake-scanner": scanner}
    ).run(budget=RunBudget(max_turns=1))

    assert scanner.calls == []
    assert agent.observed[0] == ActionRejected(f"awaiting human approval: {key}")


def test_self_report_without_evidence_is_rejected(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    attestation = ExhaustionAttestation(
        tools_exercised=("fake-scanner",), findings_dispositioned=(), no_further_avenues=True
    )
    agent = ScriptedAgent([SelfReport(vertical="injection", attestation=attestation)])
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    assert agent.observed[0] is not None
    assert not isinstance(agent.observed[0], ToolResult)
    assert current_state(tmp_path, "injection") == VerticalState.IN_PROGRESS


def test_self_report_rejects_an_open_finding(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    finding = new_finding("roundcube", "injection", "SQLi", "high", FindingScope.SANDBOX, "poc.py")
    findings_record_finding(tmp_path, finding)

    attestation = ExhaustionAttestation(
        tools_exercised=(), findings_dispositioned=(finding.id,), no_further_avenues=True
    )
    agent = ScriptedAgent([SelfReport(vertical="injection", attestation=attestation)])
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    harness.run(budget=RunBudget(max_turns=1))

    assert agent.observed[0] is not None
    assert not isinstance(agent.observed[0], ToolResult)
    assert current_state(tmp_path, "injection") == VerticalState.IN_PROGRESS


def test_self_report_reaches_exhausted_once_every_claim_checks_out(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    _write_skill(skills_dir, "injection", "name: injection\nrequired: true\n")
    finding = new_finding("roundcube", "injection", "SQLi", "high", FindingScope.SANDBOX, "poc.py")
    findings_record_finding(tmp_path, finding)
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    record_attempt(tmp_path, "injection", "fake-scanner")

    setup_agent = ScriptedAgent(
        [ProposeVerdict(finding_id=finding.id, verdict=Verdict(type=VerdictType.FALSE_POSITIVE))]
    )
    Harness.open(tmp_path, skills_dir, "roundcube", agent=setup_agent).run(
        budget=RunBudget(max_turns=1)
    )

    attestation = ExhaustionAttestation(
        tools_exercised=("fake-scanner",),
        findings_dispositioned=(finding.id,),
        no_further_avenues=True,
    )
    agent = ScriptedAgent([SelfReport(vertical="injection", attestation=attestation)])
    Harness.open(tmp_path, skills_dir, "roundcube", agent=agent).run(budget=RunBudget(max_turns=1))

    rejection = agent.observed[0]
    assert isinstance(rejection, ActionRejected)
    key = rejection.reason.removeprefix("awaiting human approval: ")
    resolve_pending_approval(tmp_path, key, approve=True, note="checked the evidence")

    agent = ScriptedAgent([SelfReport(vertical="injection", attestation=attestation)])
    harness = Harness.open(tmp_path, skills_dir, "roundcube", agent=agent)
    outcome = harness.run(budget=RunBudget(max_turns=1))

    assert agent.observed == [ToolResult(ok=True, output="injection -> exhausted")]
    assert outcome.final_states == {"injection": VerticalState.EXHAUSTED}


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
