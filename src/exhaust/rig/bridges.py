"""The Rig's single tool-call gate (ADR 0012, ADR 0018).

Every wrapped external tool satisfies `ToolBridge`, the one real seam
in this module: ADR 0012 already names more than one kind of tool to
wrap (recon scanners, template-based vuln checkers, credential
checkers), so this seam is real, not hypothetical. `call` is the only
way through to any of them. It never accepts an arbitrary command
string and hands it unfiltered to a tool: a method not on that tool's
own closed list is refused here, before a bridge's `run` is ever
invoked.

`tools`/`call` accept the bridge mapping as a parameter rather than
reaching into module-level global state, so assembling which bridges
exist is the caller's job (the Harness, once it exists) and a test can
pass a fake mapping without touching any global registry.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ToolInfo:
    """What a caller sees when discovering a tool, before calling it.

    Attributes
    ----------
    name : str
        The tool's name, as passed to `call`.
    usage : str
        A one-line description of what the tool does.
    doc : str
        A pointer to the tool's full documentation.
    """

    name: str
    usage: str
    doc: str


@dataclass(frozen=True)
class MethodInfo:
    """One method a tool bridge exposes.

    Attributes
    ----------
    name : str
        The method's name, as passed to `call`.
    mutates : bool
        Whether invoking it can change anything. `call` itself doesn't
        gate on this; the Harness decides whether a mutating call is
        allowed, using this as the signal to decide with.
    """

    name: str
    mutates: bool


@dataclass(frozen=True)
class ToolResult:
    """What a tool bridge call returns.

    Attributes
    ----------
    ok : bool
        Whether the underlying tool reported success.
    output : str
        The tool's output, success or failure.
    """

    ok: bool
    output: str


@runtime_checkable
class ToolBridge(Protocol):
    """What a wrapped external tool must satisfy.

    Attributes
    ----------
    info : ToolInfo
        What this tool is, for discovery via `tools`.
    methods : tuple[MethodInfo, ...]
        This tool's closed, named list of callable methods. `call`
        refuses any method name not in this list before `run` is ever
        invoked; `run` itself must refuse the same way, since nothing
        stops a future caller from invoking a bridge's `run` directly
        and bypassing this module's gate.
    """

    info: ToolInfo
    methods: tuple[MethodInfo, ...]

    def run(self, method: str, **params: Any) -> ToolResult:
        """Invoke `method` on the underlying tool with `params`."""
        ...


class UnknownToolError(ValueError):
    """Raised when `call` or `tools` is given a tool name with no bridge."""


class UnknownMethodError(ValueError):
    """Raised when `call` is given a method not on the tool's closed list."""


def tools(bridges: Mapping[str, ToolBridge]) -> list[ToolInfo]:
    """List every available tool's discovery info.

    Parameters
    ----------
    bridges : Mapping[str, ToolBridge]
        Every registered bridge, keyed by tool name.

    Returns
    -------
    list[ToolInfo]
        Each bridge's `info`, not its methods: a caller discovers what
        tools exist here, then calls `call` to actually use one.
    """
    return [bridge.info for bridge in bridges.values()]


def call(bridges: Mapping[str, ToolBridge], tool: str, method: str, **params: Any) -> ToolResult:
    """Invoke one method on one tool, the only way through to any bridge.

    Parameters
    ----------
    bridges : Mapping[str, ToolBridge]
        Every registered bridge, keyed by tool name.
    tool : str
        Which bridge to call.
    method : str
        Which of that bridge's closed, named methods to invoke.
    **params : Any
        Passed through to the bridge's `run`.

    Returns
    -------
    ToolResult
        The bridge's result.

    Raises
    ------
    UnknownToolError
        If `tool` has no registered bridge.
    UnknownMethodError
        If `method` isn't in that bridge's `methods`.
    """
    bridge = bridges.get(tool)
    if bridge is None:
        raise UnknownToolError(tool)

    if method not in {m.name for m in bridge.methods}:
        raise UnknownMethodError(f"{tool}.{method}")

    return bridge.run(method, **params)
