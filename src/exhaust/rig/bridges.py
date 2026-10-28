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
    consequential : bool
        Whether a call to this method against a real Target needs a
        human's approval before it runs (ADR 0023). Declared here, at
        the bridge's own enumerated method list, for the same reason
        `mutates` is: the bridge author already knows which of their
        tool's operations carry real-world weight, and `call` itself
        still doesn't gate on it — the Harness does, using this as the
        signal. Independent of `mutates`: a harmless Sandbox-only write
        can mutate without being consequential, and a non-mutating but
        intrusive real-Target probe can be consequential without
        mutating anything.
    required_extent : str
        The Scope Contract extent tier a real-Target call to this
        method needs (ADR 0024): `"recon"` or `"full"`. A plain string,
        not the `scope_contract` module's own enum, since `rig` and
        `scope_contract` are independent domain modules that never
        import each other; `scope_contract.is_in_scope` is the only
        thing that interprets this value.
    """

    name: str
    mutates: bool
    consequential: bool
    required_extent: str


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

    def installed_version(self) -> str | None:
        """Report the actually-installed tool's version, or `None` if it can't be determined.

        For `rig.preflight.check_pinned_tools` to compare against
        `PinnedTool.version` (ADR 0012): a bridge wraps one specific
        external tool, so it already knows that tool's own
        `--version`-shaped invocation and output format — this module's
        gate doesn't, and has no business guessing at either.
        """
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


def _resolve_method(bridges: Mapping[str, ToolBridge], tool: str, method: str) -> MethodInfo:
    """Look up one bridge's declared metadata for `method`, without invoking it.

    Shared by `call` and `method_info` so a method name is validated the
    same way regardless of which one a caller uses.

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

    for info in bridge.methods:
        if info.name == method:
            return info

    raise UnknownMethodError(f"{tool}.{method}")


def method_info(bridges: Mapping[str, ToolBridge], tool: str, method: str) -> MethodInfo:
    """Look up one method's declared metadata, e.g. to check `consequential` (ADR 0023).

    Parameters
    ----------
    bridges : Mapping[str, ToolBridge]
        Every registered bridge, keyed by tool name.
    tool : str
        Which bridge to look up.
    method : str
        Which of that bridge's closed, named methods to look up.

    Returns
    -------
    MethodInfo
        That method's declared metadata.

    Raises
    ------
    UnknownToolError
        If `tool` has no registered bridge.
    UnknownMethodError
        If `method` isn't in that bridge's `methods`.
    """
    return _resolve_method(bridges, tool, method)


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
    _resolve_method(bridges, tool, method)
    return bridges[tool].run(method, **params)
