from pathlib import Path

import pytest

from exhaust.approvals import (
    AlreadyResolvedError,
    ApprovalStatus,
    ConsequentialCall,
    ExhaustionClaim,
    NoteRequiredError,
    UnknownApprovalError,
    approval_key,
    is_approved,
    request_approval,
    resolve,
)


def _call(target: str = "acme.com") -> ConsequentialCall:
    return ConsequentialCall(
        vertical="injection", tool="fake-scanner", method="exploit", params={}, target=target
    )


def test_unrequested_subject_is_not_approved(tmp_path: Path) -> None:
    assert is_approved(tmp_path, _call()) is False


def test_requesting_twice_is_idempotent(tmp_path: Path) -> None:
    first = request_approval(tmp_path, _call())
    second = request_approval(tmp_path, _call())
    assert first == second


def test_approving_makes_the_exact_subject_approved(tmp_path: Path) -> None:
    key = request_approval(tmp_path, _call())
    resolve(tmp_path, key, decision=ApprovalStatus.APPROVED, note="reviewed")
    assert is_approved(tmp_path, _call()) is True


def test_denying_leaves_the_subject_unapproved(tmp_path: Path) -> None:
    key = request_approval(tmp_path, _call())
    resolve(tmp_path, key, decision=ApprovalStatus.DENIED, note="too risky")
    assert is_approved(tmp_path, _call()) is False


def test_different_params_are_different_subjects(tmp_path: Path) -> None:
    key = request_approval(tmp_path, _call())
    resolve(tmp_path, key, decision=ApprovalStatus.APPROVED, note="reviewed")
    assert is_approved(tmp_path, _call(target="other.com")) is False


def test_a_consequential_call_and_an_exhaustion_claim_never_collide(tmp_path: Path) -> None:
    call = ConsequentialCall(
        vertical="injection", tool="fake-scanner", method="exploit", params={}, target="a"
    )
    claim = ExhaustionClaim(vertical="injection", tools_exercised=(), findings_dispositioned=())
    assert approval_key(call) != approval_key(claim)


def test_resolving_an_unknown_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(UnknownApprovalError):
        resolve(tmp_path, "nonexistent", decision=ApprovalStatus.APPROVED, note="reviewed")


def test_resolving_without_a_note_is_rejected(tmp_path: Path) -> None:
    key = request_approval(tmp_path, _call())
    with pytest.raises(NoteRequiredError):
        resolve(tmp_path, key, decision=ApprovalStatus.APPROVED, note="")


def test_resolving_an_already_resolved_key_is_rejected(tmp_path: Path) -> None:
    key = request_approval(tmp_path, _call())
    resolve(tmp_path, key, decision=ApprovalStatus.APPROVED, note="reviewed")
    with pytest.raises(AlreadyResolvedError):
        resolve(tmp_path, key, decision=ApprovalStatus.DENIED, note="changed my mind")
