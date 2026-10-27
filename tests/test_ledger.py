from pathlib import Path

import pytest

from exhaust.ledger import (
    LEDGER_FILENAME,
    AlreadyTerminalError,
    HumanResumeRequiredError,
    InvalidTransitionError,
    ReasonRequiredError,
    ResumedBy,
    VerticalState,
    current_state,
    is_workspace_done,
    load_ledger,
    transition,
)


def test_unknown_vertical_is_pending(tmp_path: Path) -> None:
    assert current_state(tmp_path, "injection") == VerticalState.PENDING


def test_start_moves_pending_to_in_progress(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    assert current_state(tmp_path, "injection") == VerticalState.IN_PROGRESS


def test_pending_can_be_skipped_with_a_reason(tmp_path: Path) -> None:
    transition(tmp_path, "graphql", VerticalState.SKIPPED, reason="no GraphQL endpoint confirmed")
    assert current_state(tmp_path, "graphql") == VerticalState.SKIPPED


def test_pending_cannot_be_skipped_without_a_reason(tmp_path: Path) -> None:
    with pytest.raises(ReasonRequiredError):
        transition(tmp_path, "graphql", VerticalState.SKIPPED)


def test_pending_cannot_jump_to_blocked(tmp_path: Path) -> None:
    with pytest.raises(InvalidTransitionError):
        transition(tmp_path, "injection", VerticalState.BLOCKED, reason="n/a")


def test_in_progress_can_become_retryable(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.RETRYABLE, reason="rate limited")
    assert current_state(tmp_path, "injection") == VerticalState.RETRYABLE


def test_retryable_resumes_to_in_progress_automatically(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.RETRYABLE, reason="rate limited")
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    assert current_state(tmp_path, "injection") == VerticalState.IN_PROGRESS


def test_in_progress_can_become_blocked(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.BLOCKED, reason="ambiguous real-Target outcome")
    assert current_state(tmp_path, "injection") == VerticalState.BLOCKED


def test_blocked_cannot_resume_without_a_human(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.BLOCKED, reason="ambiguous real-Target outcome")

    with pytest.raises(HumanResumeRequiredError):
        transition(tmp_path, "injection", VerticalState.IN_PROGRESS, resumed_by=ResumedBy.AGENT)

    with pytest.raises(HumanResumeRequiredError):
        transition(tmp_path, "injection", VerticalState.IN_PROGRESS)


def test_blocked_resumes_with_a_human(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.BLOCKED, reason="ambiguous real-Target outcome")
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS, resumed_by=ResumedBy.HUMAN)
    assert current_state(tmp_path, "injection") == VerticalState.IN_PROGRESS


def test_in_progress_can_become_exhausted(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.EXHAUSTED, reason="no further avenues")
    assert current_state(tmp_path, "injection") == VerticalState.EXHAUSTED


def test_exhausted_accepts_no_further_transitions(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.EXHAUSTED, reason="no further avenues")

    with pytest.raises(InvalidTransitionError):
        transition(tmp_path, "injection", VerticalState.IN_PROGRESS)


def test_skipped_accepts_no_further_transitions(tmp_path: Path) -> None:
    transition(tmp_path, "graphql", VerticalState.SKIPPED, reason="no GraphQL endpoint confirmed")

    with pytest.raises(InvalidTransitionError):
        transition(tmp_path, "graphql", VerticalState.IN_PROGRESS)


def test_terminal_transition_raises_the_specific_already_terminal_error(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.EXHAUSTED, reason="no further avenues")

    with pytest.raises(AlreadyTerminalError):
        transition(tmp_path, "injection", VerticalState.IN_PROGRESS)


def test_unreachable_but_non_terminal_transition_is_a_plain_invalid_transition(
    tmp_path: Path,
) -> None:
    # pending -> blocked is unreachable but pending is not terminal, so this
    # must raise the generic error, not AlreadyTerminalError.
    with pytest.raises(InvalidTransitionError) as exc_info:
        transition(tmp_path, "injection", VerticalState.BLOCKED, reason="n/a")
    assert not isinstance(exc_info.value, AlreadyTerminalError)


def test_no_leftover_temp_file_after_a_transition(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)

    assert (tmp_path / LEDGER_FILENAME).is_file()
    assert not (tmp_path / f"{LEDGER_FILENAME}.tmp").exists()


def test_is_workspace_done_false_when_anything_is_pending(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.EXHAUSTED, reason="no further avenues")
    assert is_workspace_done(tmp_path, ["injection", "access_control"]) is False


def test_is_workspace_done_true_once_everything_is_terminal(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(tmp_path, "injection", VerticalState.EXHAUSTED, reason="no further avenues")
    transition(tmp_path, "graphql", VerticalState.SKIPPED, reason="no GraphQL endpoint confirmed")
    assert is_workspace_done(tmp_path, ["injection", "graphql"]) is True


def test_is_workspace_done_false_while_in_progress(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    assert is_workspace_done(tmp_path, ["injection"]) is False


def test_ledger_persists_across_loads(tmp_path: Path) -> None:
    transition(tmp_path, "injection", VerticalState.IN_PROGRESS)
    transition(
        tmp_path, "access_control", VerticalState.SKIPPED, reason="CLI tool, no browser surface"
    )

    ledger = load_ledger(tmp_path)
    assert ledger["injection"].state == VerticalState.IN_PROGRESS
    assert ledger["access_control"].state == VerticalState.SKIPPED
    assert ledger["access_control"].reason == "CLI tool, no browser surface"


def test_load_ledger_on_empty_workspace(tmp_path: Path) -> None:
    assert load_ledger(tmp_path) == {}
