"""The Rig's second pinned tool: curl, a payload-submission client (ADR 0012, ADR 0018, ADR 0027).

Three narrow, enumerated methods, `get`, `post_form`, and `post_multipart`,
none accepting anything beyond a validated `url` and flat string-to-string
request values (or, for `post_multipart`, a filename string, the one
field the method exists to inject into). Neither builds a shell command
from those values: every value reaches `curl` as its own argv token
(`--data-urlencode` for form fields, `-F` for multipart, a hand-built
query string for `get`), so nothing a caller passes can be read as a
second `curl` flag the way an unvalidated `host` could smuggle an nmap
flag (ADR 0018's same concern, applied to a tool whose whole job is
submitting attacker-controlled values instead of refusing them).
"""

import re
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard, cast
from urllib.parse import quote

from exhaust.rig.bridges import MethodInfo, ToolInfo, ToolResult

_INFO = ToolInfo(
    name="curl",
    usage="HTTP client: GET/path-segment/header values, POST form fields, or a multipart upload.",
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
    MethodInfo(
        name="post_multipart",
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

# A plain curl invocation sends 'User-Agent: curl/<version>' and no Accept header
# at all — one of the cheapest, most common signals a Target's bot-detection
# checks for, confounding "blocked as a non-browser client" with "not vulnerable"
# (lwthiker/curl-impersonate's own stated motivation, audited 2026-10-29). This
# is a browser-shaped header set only, not TLS/HTTP2 fingerprint parity: that
# needs curl built against a different TLS library entirely and is a separate,
# bigger decision this bridge doesn't make on its own.
_DEFAULT_HEADERS: tuple[str, ...] = (
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language: en-US,en;q=0.9",
)


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
        if method == "post_multipart":
            return self._post_multipart(params)
        return ToolResult(ok=False, output=f"curl: unknown method {method!r}")

    def _get(self, params: Mapping[str, Any]) -> ToolResult:
        url = params.get("url")
        if not isinstance(url, str) or not _URL_PATTERN.fullmatch(url):
            return ToolResult(ok=False, output=f"curl: invalid url {url!r}")

        query = params.get("query")
        if query is not None and not _is_flat_string_mapping(query):
            return ToolResult(ok=False, output=f"curl: invalid query {query!r}")

        path_segment = params.get("path_segment")
        if path_segment is not None and not isinstance(path_segment, str):
            return ToolResult(ok=False, output=f"curl: invalid path_segment {path_segment!r}")

        headers = params.get("headers")
        if headers is not None and not _is_flat_string_mapping(headers):
            return ToolResult(ok=False, output=f"curl: invalid headers {headers!r}")

        full_url = url
        if path_segment is not None:
            # Deliberately not percent-encoded: path-segment injection's own
            # payload IS the encoding under test (raw "../", "%2e%2e%2f",
            # double-encoded variants). The "--" separator already stops this
            # from ever being read as a curl flag; no further escaping is this
            # bridge's job to impose on what it exists to deliver intact.
            full_url = f"{url.rstrip('/')}/{path_segment}"
        if query:
            pairs = "&".join(f"{quote(str(k))}={quote(str(v))}" for k, v in query.items())
            separator = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{separator}{pairs}"

        return self._invoke(["--", full_url], headers=headers)

    def _post_form(self, params: Mapping[str, Any]) -> ToolResult:
        url = params.get("url")
        if not isinstance(url, str) or not _URL_PATTERN.fullmatch(url):
            return ToolResult(ok=False, output=f"curl: invalid url {url!r}")

        data = params.get("data")
        if not _is_flat_string_mapping(data):
            return ToolResult(ok=False, output=f"curl: invalid data {data!r}")

        headers = params.get("headers")
        if headers is not None and not _is_flat_string_mapping(headers):
            return ToolResult(ok=False, output=f"curl: invalid headers {headers!r}")

        argv: list[str] = []
        for key, value in data.items():
            argv.extend(["--data-urlencode", f"{key}={value}"])
        argv.extend(["--", url])

        return self._invoke(argv, headers=headers)

    def _post_multipart(self, params: Mapping[str, Any]) -> ToolResult:
        url = params.get("url")
        if not isinstance(url, str) or not _URL_PATTERN.fullmatch(url):
            return ToolResult(ok=False, output=f"curl: invalid url {url!r}")

        field = params.get("field")
        if not isinstance(field, str) or not field:
            return ToolResult(ok=False, output=f"curl: invalid field {field!r}")

        filename = params.get("filename")
        if not isinstance(filename, str) or not filename:
            return ToolResult(ok=False, output=f"curl: invalid filename {filename!r}")

        content = params.get("content", "")
        if not isinstance(content, str):
            return ToolResult(ok=False, output=f"curl: invalid content {content!r}")

        headers = params.get("headers")
        if headers is not None and not _is_flat_string_mapping(headers):
            return ToolResult(ok=False, output=f"curl: invalid headers {headers!r}")

        # The uploaded bytes are never attacker-controlled by this bridge — only
        # `filename` is the injection point (ADR 0018's narrow surface). curl's
        # own `-F field=@path;filename=...` lets the on-wire filename differ
        # from the local temp file's real name, which is exactly what's needed:
        # a semicolon in `filename` can't smuggle a second `-F` sub-parameter
        # either, since curl reads the whole `-F` value as one argv token.
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tmp") as tmp:
            tmp.write(content)
            tmp.flush()
            form_spec = f"{field}=@{tmp.name};filename={filename}"
            return self._invoke(["-F", form_spec, "--", url], headers=headers)

    def _invoke(self, argv: list[str], *, headers: Mapping[str, str] | None = None) -> ToolResult:
        header_args: list[str] = []
        for header in _DEFAULT_HEADERS:
            header_args.extend(["-H", header])
        if headers:
            for name, value in headers.items():
                header_args.extend(["-H", f"{name}: {value}"])

        full_argv = [
            str(self.executable),
            "-s",
            "-S",
            "--max-time",
            str(int(_REQUEST_TIMEOUT_S)),
            *header_args,
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
