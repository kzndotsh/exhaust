"""The Rig's pinned external tool catalog (ADR 0012).

The Rig wraps existing, well-known security tools rather than
reimplementing them, each pinned to a specific version installed from
its own upstream release. This module is the data shape one pinned
entry takes. No tools are actually pinned yet: which tools the Rig
ships is a separate, still-open decision, the same way the Playbook's
vertical catalog (`catalog.py`) is deliberately empty until that's
decided. Nothing here should be read as a commitment to any specific
tool.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PinnedTool:
    """One externally-sourced tool the Rig installs and wraps.

    Attributes
    ----------
    name : str
        The tool's name, matching the `ToolBridge` registered for it.
    version : str
        The exact pinned version, never a floating tag.
    source : str
        Where it's installed from (e.g. a GitHub repository).
    platform : str
        The platform this pin targets (e.g. "linux-x86_64").
    """

    name: str
    version: str
    source: str
    platform: str


PINNED_TOOLS: tuple[PinnedTool, ...] = ()
