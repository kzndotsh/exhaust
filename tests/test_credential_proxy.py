import http.client
import http.server
import json
import threading
from collections.abc import Generator
from pathlib import Path

import pytest

from exhaust.harness.credential_proxy import (
    CredentialProxy,
    CredentialProxyConfig,
    InsecureCredentialFileError,
    SpendTracker,
    TokenPricing,
    generate_virtual_key,
    load_api_key_from_file,
    write_virtual_key_file,
)

_PRICING = TokenPricing(input_usd_per_million=3.0, output_usd_per_million=15.0)


def test_cost_usd_prices_input_and_output_tokens_independently() -> None:
    cost = _PRICING.cost_usd(input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(18.0)


def test_load_api_key_from_file_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InsecureCredentialFileError):
        load_api_key_from_file(tmp_path / "nope")


def test_load_api_key_from_file_rejects_group_or_other_readable(tmp_path: Path) -> None:
    key_file = tmp_path / "key"
    key_file.write_text("sk-ant-real-key")
    key_file.chmod(0o644)

    with pytest.raises(InsecureCredentialFileError, match="chmod 600"):
        load_api_key_from_file(key_file)


def test_load_api_key_from_file_rejects_an_empty_file(tmp_path: Path) -> None:
    key_file = tmp_path / "key"
    key_file.write_text("")
    key_file.chmod(0o600)

    with pytest.raises(InsecureCredentialFileError, match="empty"):
        load_api_key_from_file(key_file)


def test_load_api_key_from_file_reads_a_properly_secured_key(tmp_path: Path) -> None:
    key_file = tmp_path / "key"
    key_file.write_text("sk-ant-real-key\n")
    key_file.chmod(0o600)

    assert load_api_key_from_file(key_file) == "sk-ant-real-key"


def test_write_virtual_key_file_is_owner_only(tmp_path: Path) -> None:
    key_file = tmp_path / "virtual-key"
    write_virtual_key_file(key_file, "deadbeef")

    assert key_file.read_text() == "deadbeef"
    assert (key_file.stat().st_mode & 0o777) == 0o600


def test_generate_virtual_key_is_not_the_same_every_time() -> None:
    assert generate_virtual_key() != generate_virtual_key()


def test_spend_tracker_blocks_once_the_budget_is_spent() -> None:
    tracker = SpendTracker(max_usd=0.01, pricing=_PRICING)
    tracker.check_not_exhausted()  # nothing spent yet

    tracker.record(input_tokens=10_000, output_tokens=0)  # costs $0.03, over the $0.01 cap

    with pytest.raises(Exception, match="budget exhausted"):
        tracker.check_not_exhausted()


def test_spend_tracker_records_real_cost() -> None:
    tracker = SpendTracker(max_usd=100.0, pricing=_PRICING)
    cost = tracker.record(input_tokens=1_000_000, output_tokens=0)
    assert cost == pytest.approx(3.0)
    assert tracker.spent_usd == pytest.approx(3.0)


class _FakeUpstreamHandler(http.server.BaseHTTPRequestHandler):
    """Stands in for Anthropic's real API: echoes back a canned usage payload."""

    received_api_keys: list[str] = []  # noqa: RUF012 - test double, mutated deliberately

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        self.received_api_keys.append(self.headers.get("x-api-key", ""))
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)

        body = json.dumps({"usage": {"input_tokens": 100, "output_tokens": 50}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fake_upstream() -> Generator[str, None, None]:
    _FakeUpstreamHandler.received_api_keys = []
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeUpstreamHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5.0)


def _post(base_url: str, *, api_key: str | None) -> tuple[int, dict[str, object]]:
    conn = http.client.HTTPConnection(base_url.removeprefix("http://"))
    try:
        headers = {"Content-Type": "application/json"}
        if api_key is not None:
            headers["x-api-key"] = api_key
        conn.request("POST", "/v1/messages", b"{}", headers)
        response = conn.getresponse()
        payload = json.loads(response.read())
        return response.status, payload
    finally:
        conn.close()


def test_a_call_with_the_right_virtual_key_is_forwarded_and_spend_is_recorded(
    fake_upstream: str,
) -> None:
    budget = SpendTracker(max_usd=100.0, pricing=_PRICING)
    cfg = CredentialProxyConfig(
        real_api_key="sk-ant-real",
        virtual_key="virtual-123",
        budget=budget,
        upstream_base_url=fake_upstream,
    )

    with CredentialProxy(cfg) as proxy:
        status, payload = _post(proxy.base_url, api_key="virtual-123")

    assert status == 200
    assert payload == {"usage": {"input_tokens": 100, "output_tokens": 50}}
    assert budget.spent_usd == pytest.approx(_PRICING.cost_usd(input_tokens=100, output_tokens=50))
    # The real key reached upstream, never the virtual one.
    assert _FakeUpstreamHandler.received_api_keys == ["sk-ant-real"]


def test_a_call_with_the_wrong_virtual_key_is_rejected_before_forwarding(
    fake_upstream: str,
) -> None:
    budget = SpendTracker(max_usd=100.0, pricing=_PRICING)
    cfg = CredentialProxyConfig(
        real_api_key="sk-ant-real",
        virtual_key="virtual-123",
        budget=budget,
        upstream_base_url=fake_upstream,
    )

    with CredentialProxy(cfg) as proxy:
        status, _ = _post(proxy.base_url, api_key="wrong-key")

    assert status == 401
    assert budget.spent_usd == 0.0
    assert _FakeUpstreamHandler.received_api_keys == []


def test_a_call_against_an_exhausted_budget_is_rejected_before_forwarding(
    fake_upstream: str,
) -> None:
    budget = SpendTracker(max_usd=0.0, pricing=_PRICING)
    cfg = CredentialProxyConfig(
        real_api_key="sk-ant-real",
        virtual_key="virtual-123",
        budget=budget,
        upstream_base_url=fake_upstream,
    )

    with CredentialProxy(cfg) as proxy:
        status, _ = _post(proxy.base_url, api_key="virtual-123")

    assert status == 402
    assert _FakeUpstreamHandler.received_api_keys == []


def test_an_unknown_path_is_rejected(fake_upstream: str) -> None:
    budget = SpendTracker(max_usd=100.0, pricing=_PRICING)
    cfg = CredentialProxyConfig(
        real_api_key="sk-ant-real",
        virtual_key="virtual-123",
        budget=budget,
        upstream_base_url=fake_upstream,
    )

    with CredentialProxy(cfg) as proxy:
        conn = http.client.HTTPConnection(proxy.base_url.removeprefix("http://"))
        try:
            conn.request("POST", "/v1/not-messages", b"{}", {"x-api-key": "virtual-123"})
            response = conn.getresponse()
            response.read()
            status = response.status
        finally:
            conn.close()

    assert status == 404


def test_base_url_before_entering_the_context_raises() -> None:
    budget = SpendTracker(max_usd=1.0, pricing=_PRICING)
    cfg = CredentialProxyConfig(real_api_key="k", virtual_key="v", budget=budget)
    proxy = CredentialProxy(cfg)
    with pytest.raises(RuntimeError):
        _ = proxy.base_url
