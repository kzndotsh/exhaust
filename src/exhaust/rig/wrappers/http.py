"""The Rig's second pinned tool: curl, a payload-submission client (ADR 0012, ADR 0018, ADR 0027).

Two narrow, enumerated methods, `get` and `post_form`, neither accepting
anything beyond a validated `url` and an optional flat string-to-string
mapping of request values. Neither builds a shell command from those
values: every value reaches `curl` as its own argv token (`--data-urlencode`
for form fields, a hand-built, percent-encoded query string for `get`),
so nothing a caller passes can be read as a second `curl` flag the way an
unvalidated `host` could smuggle an nmap flag (ADR 0018's same concern,
applied to a tool whose whole job is submitting attacker-controlled
values instead of refusing them).
"""

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard, cast
from urllib.parse import quote

from exhaust.rig.bridges import MethodInfo, ToolInfo, ToolResult

_INFO = ToolInfo(
    name="curl",
    usage="HTTP client: submits GET query parameters or POST form fields to a Target.",
    doc="https://curl.se/docs/manpage.html",
)

_METHODS = (
    MethodInfo(
        name="get",
        mutates=True,
        consequential=True,
        required_extent="full",
    ),
    MethodInfo(
        name="post_form",
        mutates=True,
        consequential=True,
        required_extent="full",
    ),
)

# http(s) scheme, a host, and an optional path — no leading '-' (would be read as
# a curl option, not a URL) and nothing a shell or curl's own option parser could
# read as anything but a literal address (ADR 0018).
_URL_PATTERN = re.compile(r"https?://[A-Za-z0-9][A-Za-z0-9.\-:]*(?:/[\w\-./]*)?")
_VERSION_PATTERN = re.compile(r"^curl (\S+)", re.MULTILINE)

_REQUEST_TIMEOUT_S = 30.0
_VERSION_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class CurlBridge:
    """Wraps a pinned `curl` binary behind two payload-submission methods.

    Attributes
    ----------
    executable : Path
        The `curl` binary to invoke, resolved via `PATH` by default —
        pinning the exact installed version is the Rig's own
        provisioning concern (ADR 0012), not this bridge's.
    """

    executable: Path = Path("curl")
    info = _INFO
    methods = _METHODS

    def run(self, method: str, **params: Any) -> ToolResult:
        """Invoke `method` on `curl`, after validating `url` and every value in it.

        Refuses any method not in `methods` itself, the same as `rig.call`
        already does before this is ever reached (ADR 0018: the bridge
        enforces, never merely advertises).
        """
        if method == "get":
            return self._get(params)
        if method == "post_form":
            return self._post_form(params)
        return ToolResult(ok=False, output=f"curl: unknown method {method!r}")

    def _get(self, params: Mapping[str, Any]) -> ToolResult:
        url = params.get("url")
        if not isinstance(url, str) or not _URL_PATTERN.fullmatch(url):
            return ToolResult(ok=False, output=f"curl: invalid url {url!r}")

        query = params.get("query")
        query_valid = query is None or _is_flat_string_mapping(query)
        if not query_valid:
            return ToolResult(ok=False, output=f"curl: invalid query {query!r}")

        full_url = url
        if query:
            pairs = "&".join(f"{quote(str(k))}={quote(str(v))}" for k, v in query.items())
            separator = "&" if "?" in url else "?"
            full_url = f"{url}{separator}{pairs}"

        return self._invoke(["--", full_url])

    def _post_form(self, params: Mapping[str, Any]) -> ToolResult:
        url = params.get("url")
        if not isinstance(url, str) or not _URL_PATTERN.fullmatch(url):
            return ToolResult(ok=False, output=f"curl: invalid url {url!r}")

        data = params.get("data")
        if not _is_flat_string_mapping(data):
            return ToolResult(ok=False, output=f"curl: invalid data {data!r}")

        argv: list[str] = []
        for key, value in data.items():
            argv.extend(["--data-urlencode", f"{key}={value}"])
        argv.extend(["--", url])

        return self._invoke(argv)

    def _invoke(self, argv: list[str]) -> ToolResult:
        full_argv = [
            str(self.executable),
            "-s",
            "-S",
            "--max-time",
            str(int(_REQUEST_TIMEOUT_S)),
            *argv,
        ]
        try:
            completed = subprocess.run(
                full_argv,
                capture_output=True,
                text=True,
                timeout=_REQUEST_TIMEOUT_S + 5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ToolResult(ok=False, output=f"curl: invocation failed: {exc}")

        return ToolResult(ok=completed.returncode == 0, output=completed.stdout or completed.stderr)

    def installed_version(self) -> str | None:
        """Parse the real version out of `curl --version`'s first line.

        Returns
        -------
        str | None
            The installed version (e.g. `"8.22.0"`), or `None` if the
            binary can't be run at all, or its output doesn't match the
            expected `"curl <x>"` shape.
        """
        try:
            completed = subprocess.run(
                [str(self.executable), "--version"],
                capture_output=True,
                text=True,
                timeout=_VERSION_TIMEOUT_S,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

        match = _VERSION_PATTERN.search(completed.stdout)
        return match.group(1) if match else None


def _is_flat_string_mapping(value: Any) -> TypeGuard[dict[str, str]]:
    """Whether `value` is a `dict[str, str]`, the only shape `get`/`post_form` accept."""
    if not isinstance(value, dict):
        return False
    untyped: dict[object, object] = cast("dict[object, object]", value)
    return all(isinstance(k, str) and isinstance(v, str) for k, v in untyped.items())
