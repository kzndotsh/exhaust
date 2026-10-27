from pathlib import Path

from exhaust.attempts import record_attempt, tools_exercised


def test_no_attempts_yet_is_empty(tmp_path: Path) -> None:
    assert tools_exercised(tmp_path, "injection") == frozenset()


def test_recorded_attempt_is_returned_for_its_vertical(tmp_path: Path) -> None:
    record_attempt(tmp_path, "injection", "nuclei")
    assert tools_exercised(tmp_path, "injection") == frozenset({"nuclei"})


def test_repeated_tool_is_deduplicated(tmp_path: Path) -> None:
    record_attempt(tmp_path, "injection", "nuclei")
    record_attempt(tmp_path, "injection", "nuclei")
    assert tools_exercised(tmp_path, "injection") == frozenset({"nuclei"})


def test_distinct_tools_both_appear(tmp_path: Path) -> None:
    record_attempt(tmp_path, "injection", "nuclei")
    record_attempt(tmp_path, "injection", "burp")
    assert tools_exercised(tmp_path, "injection") == frozenset({"nuclei", "burp"})


def test_attempts_are_scoped_to_their_own_vertical(tmp_path: Path) -> None:
    record_attempt(tmp_path, "injection", "nuclei")
    record_attempt(tmp_path, "access_control", "burp")
    assert tools_exercised(tmp_path, "injection") == frozenset({"nuclei"})
    assert tools_exercised(tmp_path, "access_control") == frozenset({"burp"})
