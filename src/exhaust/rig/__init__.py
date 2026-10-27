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

__all__ = [
    "PINNED_TOOLS",
    "MethodInfo",
    "PinnedTool",
    "ToolBridge",
    "ToolInfo",
    "ToolResult",
    "UnknownMethodError",
    "UnknownToolError",
    "call",
    "method_info",
    "tools",
]
