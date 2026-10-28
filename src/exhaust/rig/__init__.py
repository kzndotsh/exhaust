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
from exhaust.rig.wrappers import NmapBridge, default_bridges

__all__ = [
    "PINNED_TOOLS",
    "MethodInfo",
    "NmapBridge",
    "PinnedTool",
    "ToolBridge",
    "ToolInfo",
    "ToolResult",
    "UnknownMethodError",
    "UnknownToolError",
    "call",
    "default_bridges",
    "method_info",
    "tools",
]
