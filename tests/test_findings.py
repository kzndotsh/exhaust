from pathlib import Path

import pytest

from exhaust.findings import (
    AcceptedRiskOverrideError,
    FindingAlreadyExistsError,
    FindingScope,
    RecordedBy,
    UnknownFindingError,
    Verdict,
    VerdictType,
    compute_finding_id,
    load_findings,
    new_finding,
    record_finding,
    record_verdict,
)


def test_compute_finding_id_is_deterministic() -> None:
    a = compute_finding_id("roundcube", "injection", "SQLi in search")
    b = compute_finding_id("roundcube", "injection", "SQLi in search")
    assert a == b


def test_compute_finding_id_differs_on_any_input() -> None:
    base = compute_finding_id("roundcube", "injection", "SQLi in search")
    assert base != compute_finding_id("webmin", "injection", "SQLi in search")
    assert base != compute_finding_id("roundcube", "access_control", "SQLi in search")
    assert base != compute_finding_id("roundcube", "injection", "SQLi elsewhere")


def test_needs_confirmation_requires_requirements() -> None:
    with pytest.raises(ValueError, match="requirements"):
        Verdict(type=VerdictType.NEEDS_CONFIRMATION)


def test_other_verdicts_reject_confirmation_fields() -> None:
    with pytest.raises(ValueError, match="needs_confirmation"):
        Verdict(type=VerdictType.CONFIRMED, requirements="an Oracle run")


def test_needs_confirmation_accepts_its_fields() -> None:
    verdict = Verdict(
        type=VerdictType.NEEDS_CONFIRMATION,
        requirements="an out-of-band callback hit",
        supporting_evidence=("DNS lookup observed",),
        contradicting_evidence=(),
    )
    assert verdict.requirements == "an out-of-band callback hit"


def test_record_and_load_a_finding(tmp_path: Path) -> None:
    finding = new_finding(
        target="roundcube",
        vertical="injection",
        claim="SQLi in search",
        severity="high",
        scope=FindingScope.SANDBOX,
        evidence="poc.py",
    )
    record_finding(tmp_path, finding)

    records = load_findings(tmp_path)
    assert len(records) == 1
    assert records[0].finding == finding
    assert records[0].history == ()
    assert records[0].latest is None


def test_duplicate_finding_id_is_rejected(tmp_path: Path) -> None:
    finding = new_finding(
        "roundcube", "injection", "SQLi in search", "high", FindingScope.SANDBOX, "poc.py"
    )
    record_finding(tmp_path, finding)

    with pytest.raises(FindingAlreadyExistsError):
        record_finding(tmp_path, finding)


def test_verdict_against_unknown_finding_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(UnknownFindingError):
        record_verdict(tmp_path, "nonexistent", Verdict(type=VerdictType.FIXED), RecordedBy.AGENT)


def test_verdict_history_is_append_only_and_ordered(tmp_path: Path) -> None:
    finding = new_finding(
        "roundcube", "injection", "SQLi in search", "high", FindingScope.SANDBOX, "poc.py"
    )
    record_finding(tmp_path, finding)

    record_verdict(
        tmp_path,
        finding.id,
        Verdict(type=VerdictType.NEEDS_CONFIRMATION, requirements="an Oracle run"),
        RecordedBy.AGENT,
    )
    record_verdict(tmp_path, finding.id, Verdict(type=VerdictType.CONFIRMED), RecordedBy.AGENT)

    records = load_findings(tmp_path)
    history = records[0].history
    assert [entry.verdict.type for entry in history] == [
        VerdictType.NEEDS_CONFIRMATION,
        VerdictType.CONFIRMED,
    ]
    assert records[0].latest is not None
    assert records[0].latest.verdict.type == VerdictType.CONFIRMED


def test_agent_cannot_silently_overwrite_human_accepted_risk(tmp_path: Path) -> None:
    finding = new_finding(
        "roundcube", "injection", "SQLi in search", "high", FindingScope.SANDBOX, "poc.py"
    )
    record_finding(tmp_path, finding)
    record_verdict(tmp_path, finding.id, Verdict(type=VerdictType.ACCEPTED_RISK), RecordedBy.HUMAN)

    with pytest.raises(AcceptedRiskOverrideError):
        record_verdict(tmp_path, finding.id, Verdict(type=VerdictType.FIXED), RecordedBy.AGENT)


def test_human_can_override_their_own_accepted_risk(tmp_path: Path) -> None:
    finding = new_finding(
        "roundcube", "injection", "SQLi in search", "high", FindingScope.SANDBOX, "poc.py"
    )
    record_finding(tmp_path, finding)
    record_verdict(tmp_path, finding.id, Verdict(type=VerdictType.ACCEPTED_RISK), RecordedBy.HUMAN)

    record_verdict(tmp_path, finding.id, Verdict(type=VerdictType.FIXED), RecordedBy.HUMAN)

    records = load_findings(tmp_path)
    assert records[0].latest is not None
    assert records[0].latest.verdict.type == VerdictType.FIXED


def test_agent_accepted_risk_is_not_protected_from_the_agent(tmp_path: Path) -> None:
    finding = new_finding(
        "roundcube", "injection", "SQLi in search", "high", FindingScope.SANDBOX, "poc.py"
    )
    record_finding(tmp_path, finding)
    record_verdict(tmp_path, finding.id, Verdict(type=VerdictType.ACCEPTED_RISK), RecordedBy.AGENT)

    record_verdict(tmp_path, finding.id, Verdict(type=VerdictType.FIXED), RecordedBy.AGENT)

    records = load_findings(tmp_path)
    assert records[0].latest is not None
    assert records[0].latest.verdict.type == VerdictType.FIXED


def test_findings_are_loaded_in_first_recorded_order(tmp_path: Path) -> None:
    first = new_finding(
        "roundcube", "injection", "SQLi in search", "high", FindingScope.SANDBOX, "poc1.py"
    )
    second = new_finding(
        "roundcube",
        "access_control",
        "IDOR on /users/:id",
        "medium",
        FindingScope.SANDBOX,
        "poc2.py",
    )
    record_finding(tmp_path, first)
    record_finding(tmp_path, second)

    records = load_findings(tmp_path)
    assert [r.finding.id for r in records] == [first.id, second.id]


def test_load_findings_on_empty_workspace(tmp_path: Path) -> None:
    assert load_findings(tmp_path) == []
