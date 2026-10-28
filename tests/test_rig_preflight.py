from typing import Any

from exhaust.rig.bridges import MethodInfo, ToolInfo, ToolResult
from exhaust.rig.catalog import PinnedTool
from exhaust.rig.preflight import PreflightResult, check_pinned_tools


class _FakeBridge:
    info = ToolInfo(name="fake", usage="fakes things", doc="see fake docs")
    methods = (
        MethodInfo(name="scan", mutates=False, consequential=False, required_extent="recon"),
    )

    def __init__(self, version: str | None) -> None:
        self._version = version

    def run(self, method: str, **params: Any) -> ToolResult:
        return ToolResult(ok=True, output="")

    def installed_version(self) -> str | None:
        return self._version


def test_a_matching_version_reports_ok() -> None:
    pinned = (PinnedTool(name="fake", version="1.0.0", source="x", platform="linux-x86_64"),)
    results = check_pinned_tools({"fake": _FakeBridge("1.0.0")}, pinned)

    assert results == [
        PreflightResult(name="fake", pinned_version="1.0.0", installed_version="1.0.0", ok=True)
    ]


def test_a_mismatched_version_reports_not_ok() -> None:
    pinned = (PinnedTool(name="fake", version="1.0.0", source="x", platform="linux-x86_64"),)
    results = check_pinned_tools({"fake": _FakeBridge("0.9.0")}, pinned)

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].installed_version == "0.9.0"
    assert results[0].pinned_version == "1.0.0"


def test_an_undeterminable_version_reports_not_ok() -> None:
    pinned = (PinnedTool(name="fake", version="1.0.0", source="x", platform="linux-x86_64"),)
    results = check_pinned_tools({"fake": _FakeBridge(None)}, pinned)

    assert results[0].ok is False
    assert results[0].installed_version is None


def test_a_pinned_tool_with_no_registered_bridge_reports_not_ok() -> None:
    pinned = (PinnedTool(name="fake", version="1.0.0", source="x", platform="linux-x86_64"),)
    results = check_pinned_tools({}, pinned)

    assert results[0].ok is False
    assert results[0].installed_version is None


def test_checks_every_pinned_tool_in_order() -> None:
    pinned = (
        PinnedTool(name="a", version="1.0.0", source="x", platform="linux-x86_64"),
        PinnedTool(name="b", version="2.0.0", source="x", platform="linux-x86_64"),
    )
    results = check_pinned_tools({"a": _FakeBridge("1.0.0"), "b": _FakeBridge("2.0.0")}, pinned)

    assert [r.name for r in results] == ["a", "b"]
    assert all(r.ok for r in results)
