from typing import Any

import pytest

from exhaust.rig import (
    MethodInfo,
    ToolInfo,
    ToolResult,
    UnknownMethodError,
    UnknownToolError,
    call,
    tools,
)


class FakeScanner:
    """A minimal ToolBridge fake: real tools don't exist yet to test against."""

    info = ToolInfo(name="fake-scanner", usage="scans fake things", doc="see fake-scanner docs")
    methods = (
        MethodInfo(name="scan", mutates=False, consequential=False, required_extent="recon"),
        MethodInfo(
            name="delete_findings", mutates=True, consequential=False, required_extent="recon"
        ),
    )

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run(self, method: str, **params: Any) -> ToolResult:
        self.calls.append((method, params))
        return ToolResult(ok=True, output=f"ran {method} with {params}")


def test_tools_lists_discovery_info_not_methods() -> None:
    bridges = {"fake-scanner": FakeScanner()}
    result = tools(bridges)
    assert result == [FakeScanner.info]


def test_call_dispatches_to_the_bridges_run() -> None:
    scanner = FakeScanner()
    result = call({"fake-scanner": scanner}, "fake-scanner", "scan", target="example.com")

    assert result == ToolResult(ok=True, output="ran scan with {'target': 'example.com'}")
    assert scanner.calls == [("scan", {"target": "example.com"})]


def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(UnknownToolError):
        call({}, "nonexistent-tool", "scan")


def test_unknown_method_is_rejected_before_run_is_called() -> None:
    scanner = FakeScanner()

    with pytest.raises(UnknownMethodError):
        call({"fake-scanner": scanner}, "fake-scanner", "drop_database")

    assert scanner.calls == []


def test_mutating_method_is_callable_but_flagged_as_mutating() -> None:
    scanner = FakeScanner()
    mutating_method = next(m for m in scanner.methods if m.name == "delete_findings")
    assert mutating_method.mutates is True

    result = call({"fake-scanner": scanner}, "fake-scanner", "delete_findings")
    assert result.ok is True
