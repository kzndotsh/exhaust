"""A local proxy fronting Anthropic's Messages API, so the agent never holds the real key.

ADR 0021.

The agent process is handed a separate, budget-capped virtual key, never
the real Anthropic API key, which this proxy holds itself and never
exposes. Every request must present the virtual key; the proxy checks
the run's remaining budget before forwarding, then records the call's
actual cost from the real response's token usage once it returns —
enforced at the one point every model call must pass through, not
merely tracked and read back after the fact.

This module is Pi-agnostic: it speaks Anthropic's wire protocol over
plain HTTP and knows nothing about Pi, the gate, or `AgentSession`.
`pi_adapter.provider_config` is what points a Pi subprocess at it.
"""

import http.client
import http.server
import json
import secrets
import stat
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

_MESSAGES_PATH = "/v1/messages"
_API_KEY_HEADER = "x-api-key"
_VIRTUAL_KEY_BYTES = 32


class InsecureCredentialFileError(Exception):
    """Raised when a credential file is missing, empty, or readable by group/other."""


class BudgetExceededError(Exception):
    """Raised when a call would be, or already was, allowed past an exhausted budget."""


def load_api_key_from_file(path: Path) -> str:
    """Read a real provider API key from a file, never from an environment variable (ADR 0021).

    A file with restricted permissions is harder to leak through a
    logged environment dump, a child process inheriting the
    environment, or `/proc` than a value sitting in `os.environ` — the
    same reasoning ADR 0021 cites for handing the agent its own virtual
    key the same way.

    Parameters
    ----------
    path : Path
        The file holding the key, as its entire stripped contents.

    Returns
    -------
    str
        The key.

    Raises
    ------
    InsecureCredentialFileError
        If `path` doesn't exist, is empty, or is readable or writable
        by its group or by others.
    """
    try:
        mode = path.stat().st_mode
    except FileNotFoundError as exc:
        raise InsecureCredentialFileError(f"{path} does not exist") from exc

    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise InsecureCredentialFileError(
            f"{path} is readable or writable by group or others; chmod 600 it"
        )

    key = path.read_text().strip()
    if not key:
        raise InsecureCredentialFileError(f"{path} is empty")
    return key


def write_virtual_key_file(path: Path, key: str) -> None:
    """Write `key` to `path` with owner-only permissions, creating it if needed.

    The counterpart to `load_api_key_from_file`: this proxy's own
    virtual key gets the same restricted-file shape as the real
    credential it fronts, per ADR 0021's closing sentence.
    """
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(key)


@dataclass(frozen=True)
class TokenPricing:
    """What this run's model costs per token, so the proxy can price a real response's usage.

    A plain rate the caller supplies, not a hardcoded table: provider
    pricing changes over time and per model, and this proxy has no
    business maintaining its own stale copy of it.

    Attributes
    ----------
    input_usd_per_million : float
        Cost per million input tokens, in USD.
    output_usd_per_million : float
        Cost per million output tokens, in USD.
    """

    input_usd_per_million: float
    output_usd_per_million: float

    def cost_usd(self, *, input_tokens: int, output_tokens: int) -> float:
        """Price one response's real token usage."""
        return (
            input_tokens * self.input_usd_per_million + output_tokens * self.output_usd_per_million
        ) / 1_000_000


class SpendTracker:
    """Thread-safe running total against one run's dollar budget (ADR 0021).

    A plain counter, not a ledger: this run's spend doesn't survive the
    proxy's own process, the same way `RunBudget`'s `max_turns` doesn't
    survive a `Harness.run()` call. Budget enforcement for a long-lived,
    resumable run is a separate, larger problem this doesn't solve.
    """

    def __init__(self, max_usd: float, pricing: TokenPricing) -> None:
        self._max_usd = max_usd
        self._pricing = pricing
        self._spent_usd = 0.0
        self._lock = threading.Lock()

    @property
    def spent_usd(self) -> float:
        """Report this run's total spend so far."""
        with self._lock:
            return self._spent_usd

    def check_not_exhausted(self) -> None:
        """Raise `BudgetExceededError` if the budget is already spent.

        Checked before forwarding a call, so a budget already exhausted
        by a prior call blocks the next one before it ever reaches the
        real provider — the enforcement ADR 0021 asks for, not a
        after-the-fact tally.
        """
        with self._lock:
            if self._spent_usd >= self._max_usd:
                raise BudgetExceededError(
                    f"budget exhausted: ${self._spent_usd:.4f} of ${self._max_usd:.4f} spent"
                )

    def record(self, *, input_tokens: int, output_tokens: int) -> float:
        """Record a completed call's real usage, returning its cost.

        Never refused here: a call already in flight runs to completion
        and is paid for, even if it pushes spend over the cap. The next
        call's `check_not_exhausted` is what stops there being one.
        """
        cost = self._pricing.cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)
        with self._lock:
            self._spent_usd += cost
            return cost


@dataclass(frozen=True)
class CredentialProxyConfig:
    """Everything needed to stand up one run's `CredentialProxy`.

    Attributes
    ----------
    real_api_key : str
        The real Anthropic API key, loaded via `load_api_key_from_file`,
        never passed as a bare string from a CLI flag or env var.
    virtual_key : str
        The key the agent is actually handed; generate one with
        `secrets.token_hex`, never reuse `real_api_key`.
    budget : SpendTracker
        This run's budget and pricing.
    upstream_base_url : str
        The real provider's base URL.
    host : str
        The local interface to bind. `127.0.0.1` keeps this off the
        network entirely; never bind `0.0.0.0` for a service holding a
        real credential.
    port : int
        The local port to bind, `0` to let the OS pick a free one.
    """

    real_api_key: str
    virtual_key: str
    budget: SpendTracker
    upstream_base_url: str = "https://api.anthropic.com"
    host: str = "127.0.0.1"
    port: int = 0


def generate_virtual_key() -> str:
    """Generate one run's virtual key: random, never derived from the real credential."""
    return secrets.token_hex(_VIRTUAL_KEY_BYTES)


class _ProxyRequestHandler(http.server.BaseHTTPRequestHandler):
    """Forwards one `/v1/messages` POST, after checking the virtual key and the budget.

    `BaseHTTPRequestHandler` is constructed per-request by the server,
    so this reads its config from `self.server`, the standard pattern
    for attaching context a plain handler class can't otherwise hold
    (the `cfg` attribute is set once, by `CredentialProxy.__enter__`,
    on the `ThreadingHTTPServer` instance itself).
    """

    @property
    def _cfg(self) -> CredentialProxyConfig:
        return cast("_ProxyHTTPServer", self.server).cfg

    def log_message(self, format: str, *args: object) -> None:
        """Silence the default stderr access log; nothing here should log near a credential."""

    def do_POST(self) -> None:
        if self.path != _MESSAGES_PATH:
            self._respond(404, {"error": {"message": f"unknown path: {self.path}"}})
            return

        if self.headers.get(_API_KEY_HEADER) != self._cfg.virtual_key:
            self._respond(401, {"error": {"message": "invalid or missing virtual key"}})
            return

        try:
            self._cfg.budget.check_not_exhausted()
        except BudgetExceededError as exc:
            self._respond(402, {"error": {"message": str(exc)}})
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        status, response_body = self._forward(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(response_body)

    def _forward(self, body: bytes) -> tuple[int, bytes]:
        upstream = urlsplit(self._cfg.upstream_base_url)
        connection_cls = (
            http.client.HTTPSConnection
            if upstream.scheme == "https"
            else (http.client.HTTPConnection)
        )
        conn = connection_cls(upstream.netloc)
        try:
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in {"host", "content-length", _API_KEY_HEADER}
            }
            headers[_API_KEY_HEADER] = self._cfg.real_api_key
            headers["Content-Length"] = str(len(body))
            conn.request("POST", upstream.path.rstrip("/") + _MESSAGES_PATH, body, headers)
            response = conn.getresponse()
            response_body = response.read()
            self._record_spend(response.status, response_body)
            return response.status, response_body
        finally:
            conn.close()

    def _record_spend(self, status: int, response_body: bytes) -> None:
        if status != 200:
            return
        try:
            payload: dict[str, Any] = json.loads(response_body)
            usage = payload["usage"]
            self._cfg.budget.record(
                input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"]
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            # The real provider's own response shape isn't this proxy's to validate; if usage
            # can't be read, spend simply isn't recorded for this call rather than guessed at.
            pass

    def _respond(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


class _ProxyHTTPServer(http.server.ThreadingHTTPServer):
    cfg: CredentialProxyConfig


@dataclass
class CredentialProxy:
    """A running local proxy; use as a context manager.

    Attributes
    ----------
    cfg : CredentialProxyConfig
        This instance's configuration.
    """

    cfg: CredentialProxyConfig
    _httpd: _ProxyHTTPServer | None = field(default=None, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)

    @property
    def base_url(self) -> str:
        """Report this proxy's own local base URL, for `provider_base_url`.

        Raises
        ------
        RuntimeError
            If called outside the `with` block that starts the server.
        """
        if self._httpd is None:
            raise RuntimeError("CredentialProxy.base_url read before __enter__")
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def __enter__(self) -> "CredentialProxy":
        """Bind and start serving in a background thread."""
        httpd = _ProxyHTTPServer((self.cfg.host, self.cfg.port), _ProxyRequestHandler)
        httpd.cfg = self.cfg
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        """Stop serving and join the background thread."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
