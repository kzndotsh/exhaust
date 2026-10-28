"""The Rig: a pinned external tool catalog behind one call gate (ADR 0012, ADR 0018)."""

from exhaust.rig.bridges import (
    MethodInfo,
    ToolBridge,
    ToolInfo,
    ToolResult,
    UnknownMethodError,
    UnknownToolError,
    call,
    method_info,
    tools,
)
from exhaust.rig.catalog import PINNED_TOOLS, PinnedTool
from exhaust.rig.preflight import PreflightResult, check_pinned_tools
from exhaust.rig.wrappers import NmapBridge, default_bridges

__all__ = [
    "PINNED_TOOLS",
    "MethodInfo",
    "NmapBridge",
    "PinnedTool",
    "PreflightResult",
    "ToolBridge",
    "ToolInfo",
    "ToolResult",
    "UnknownMethodError",
    "UnknownToolError",
    "call",
    "check_pinned_tools",
    "default_bridges",
    "method_info",
    "tools",
]
