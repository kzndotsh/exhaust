"""Concrete `ToolBridge` implementations, one file per tool (ADR 0012).

A tool that outgrows a single file (real output parsing beyond raw
stdout, its own fixtures) becomes its own package here instead —
nothing about this layout requires every entry to stay one file.
`default_bridges()` is the one place that knows every tool this
package ships, so a caller wiring up a Rig never has to import each
bridge class by hand as the list grows.
"""

from exhaust.rig.bridges import ToolBridge
from exhaust.rig.wrappers.curl import CurlBridge
from exhaust.rig.wrappers.nmap import NmapBridge

__all__ = ["CurlBridge", "NmapBridge", "default_bridges"]


def default_bridges() -> dict[str, ToolBridge]:
    """Every tool this package ships, keyed by name, each freshly constructed."""
    return {"nmap": NmapBridge(), "curl": CurlBridge()}
