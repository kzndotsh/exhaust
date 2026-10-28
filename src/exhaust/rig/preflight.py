"""Checks whether every pinned tool is actually present at its pinned version (ADR 0012).

`PINNED_TOOLS` records intent; nothing before this enforced that the
binary a bridge actually finds on `PATH` matches it. This is a
read-only check, never a gate `rig.call` itself runs — a version
mismatch is an operator's problem to notice and fix (`exhaust doctor`),
not a reason to refuse a call that would otherwise work fine.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from exhaust.rig.bridges import ToolBridge
from exhaust.rig.catalog import PinnedTool


@dataclass(frozen=True)
class PreflightResult:
    """One pinned tool's check result.

    Attributes
    ----------
    name : str
        The tool's name, matching its `PinnedTool` and bridge entry.
    pinned_version : str
        The version `PINNED_TOOLS` names.
    installed_version : str | None
        What the bridge actually found, or `None` if there's no
        registered bridge for this tool, or the bridge couldn't
        determine a version at all (the binary isn't on `PATH`, or its
        output didn't parse).
    ok : bool
        Whether `installed_version` exactly matches `pinned_version`.
    """

    name: str
    pinned_version: str
    installed_version: str | None
    ok: bool


def check_pinned_tools(
    bridges: Mapping[str, ToolBridge], pinned: tuple[PinnedTool, ...]
) -> list[PreflightResult]:
    """Check every entry in `pinned` against the matching bridge's `installed_version()`.

    Parameters
    ----------
    bridges : Mapping[str, ToolBridge]
        Every registered bridge, keyed by tool name — the same mapping
        a Rig call gate uses.
    pinned : tuple[PinnedTool, ...]
        The catalog to check against, normally `rig.catalog.PINNED_TOOLS`.

    Returns
    -------
    list[PreflightResult]
        One result per entry in `pinned`, in the same order.
    """
    results: list[PreflightResult] = []
    for tool in pinned:
        bridge = bridges.get(tool.name)
        installed = bridge.installed_version() if bridge is not None else None
        results.append(
            PreflightResult(
                name=tool.name,
                pinned_version=tool.version,
                installed_version=installed,
                ok=installed == tool.version,
            )
        )
    return results
