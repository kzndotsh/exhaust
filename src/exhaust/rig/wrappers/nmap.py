"""The Rig's first pinned tool: nmap, a recon scanner (ADR 0012, ADR 0018).

Two narrow, enumerated methods — `tcp_connect_scan` and
`service_version_scan` — neither accepting anything beyond a validated
`host` and an optional validated `ports` string. Neither passes
anything else through to the underlying binary: a host or ports value
that doesn't match the expected shape is refused before `nmap` ever
runs, so a value like `"--script=vuln"` can't smuggle in capability
this bridge never declared (ADR 0018).
"""

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from exhaust.rig.bridges import MethodInfo, ToolInfo, ToolResult

_INFO = ToolInfo(
    name="nmap",
    usage="Network recon scanner: TCP connect scans and service/version detection.",
    doc="https://nmap.org/book/man.html",
)

_METHODS = (
    MethodInfo(
        name="tcp_connect_scan",
        mutates=False,
        consequential=False,
        required_extent="recon",
    ),
    MethodInfo(
        name="service_version_scan",
        mutates=False,
        consequential=False,
        required_extent="recon",
    ),
)

# No leading '-' (would be read as an nmap option, not a target), and nothing
# outside the characters a hostname, IPv4, or IPv6 address can actually contain.
_HOST_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-:]*")
_PORTS_PATTERN = re.compile(r"[0-9]+(-[0-9]+)?(,[0-9]+(-[0-9]+)?)*")

_SCAN_TIMEOUT_S = 120.0


@dataclass(frozen=True)
class NmapBridge:
    """Wraps a pinned `nmap` binary behind two recon-tier methods.

    Attributes
    ----------
    executable : Path
        The `nmap` binary to invoke, resolved via `PATH` by default —
        pinning the exact installed version is the Rig's own
        provisioning concern (ADR 0012), not this bridge's.
    """

    executable: Path = Path("nmap")
    info = _INFO
    methods = _METHODS

    def run(self, method: str, **params: Any) -> ToolResult:
        """Invoke `method` on `nmap`, after validating `host` and `ports`.

        Refuses any method not in `methods` itself, the same as `rig.call`
        already does before this is ever reached (ADR 0018: the bridge
        enforces, never merely advertises).
        """
        if method == "tcp_connect_scan":
            return self._scan(params, extra_flags=("-sT",))
        if method == "service_version_scan":
            return self._scan(params, extra_flags=("-sV",))
        return ToolResult(ok=False, output=f"nmap: unknown method {method!r}")

    def _scan(self, params: Mapping[str, Any], *, extra_flags: tuple[str, ...]) -> ToolResult:
        host = params.get("host")
        if not isinstance(host, str) or not _HOST_PATTERN.fullmatch(host):
            return ToolResult(ok=False, output=f"nmap: invalid host {host!r}")

        ports = params.get("ports")
        ports_valid = ports is None or (isinstance(ports, str) and _PORTS_PATTERN.fullmatch(ports))
        if not ports_valid:
            return ToolResult(ok=False, output=f"nmap: invalid ports {ports!r}")

        argv = [str(self.executable), "-Pn", *extra_flags]
        if ports is not None:
            argv.extend(["-p", ports])
        argv.append(host)

        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, timeout=_SCAN_TIMEOUT_S, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ToolResult(ok=False, output=f"nmap: invocation failed: {exc}")

        return ToolResult(ok=completed.returncode == 0, output=completed.stdout or completed.stderr)
