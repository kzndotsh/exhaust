import stat
from pathlib import Path

from exhaust.rig.bridges import call
from exhaust.rig.wrappers import default_bridges
from exhaust.rig.wrappers.curl import CurlBridge

_FAKE_CURL = """\
#!/usr/bin/env python3
import sys
print(" ".join(sys.argv[1:]))
sys.exit({exit_code})
"""


def _fake_curl(tmp_path: Path, *, exit_code: int = 0) -> Path:
    script = tmp_path / "fake-curl"
    script.write_text(_FAKE_CURL.format(exit_code=exit_code))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _touch_on_run(tmp_path: Path) -> tuple[Path, Path]:
    marker = tmp_path / "invoked"
    script = tmp_path / "fake-curl"
    script.write_text(f"#!/bin/sh\ntouch {marker}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script, marker


def test_info_and_methods_are_consequential_full_extent() -> None:
    bridge = CurlBridge()
    assert bridge.info.name == "curl"
    for method in bridge.methods:
        assert method.required_extent == "full"
        assert method.mutates is True
        assert method.consequential is True


def test_get_with_no_query_passes_the_bare_url(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=_fake_curl(tmp_path))
    result = bridge.run("get", url="http://target.example/search")
    assert result.ok is True
    assert result.output.strip().endswith("-- http://target.example/search")


def test_get_appends_a_percent_encoded_query_string(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=_fake_curl(tmp_path))
    result = bridge.run("get", url="http://target.example/search", query={"q": "a b&c"})
    assert result.ok is True
    assert result.output.strip().endswith("-- http://target.example/search?q=a%20b%26c")


def test_post_form_sends_each_field_as_its_own_data_urlencode_token(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=_fake_curl(tmp_path))
    result = bridge.run("post_form", url="http://target.example/login", data={"user": "' OR 1=1"})
    assert result.ok is True
    assert result.output.strip().endswith(
        "--data-urlencode user=' OR 1=1 -- http://target.example/login"
    )


def test_every_request_carries_browser_shaped_default_headers(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=_fake_curl(tmp_path))
    result = bridge.run("get", url="http://target.example/")
    assert "-H User-Agent: Mozilla/5.0" in result.output
    assert "-H Accept: text/html" in result.output
    assert "-H Accept-Language: en-US" in result.output


def test_a_nonzero_exit_is_reported_as_not_ok(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=_fake_curl(tmp_path, exit_code=1))
    result = bridge.run("get", url="http://target.example/")
    assert result.ok is False


def test_an_unknown_method_is_refused_without_invoking_the_binary(tmp_path: Path) -> None:
    script, marker = _touch_on_run(tmp_path)
    bridge = CurlBridge(executable=script)
    result = bridge.run("delete_everything", url="http://target.example/")
    assert result.ok is False
    assert not marker.exists()


def test_a_url_starting_with_a_dash_is_refused_not_passed_to_curl(tmp_path: Path) -> None:
    script, marker = _touch_on_run(tmp_path)
    bridge = CurlBridge(executable=script)
    result = bridge.run("get", url="--data=@/etc/passwd")
    assert result.ok is False
    assert not marker.exists()


def test_a_missing_url_is_refused(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=_fake_curl(tmp_path))
    result = bridge.run("get")
    assert result.ok is False


def test_a_non_string_query_value_is_refused(tmp_path: Path) -> None:
    script, marker = _touch_on_run(tmp_path)
    bridge = CurlBridge(executable=script)
    result = bridge.run("get", url="http://target.example/", query={"q": 1})
    assert result.ok is False
    assert not marker.exists()


def test_post_form_without_data_is_refused(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=_fake_curl(tmp_path))
    result = bridge.run("post_form", url="http://target.example/")
    assert result.ok is False


def test_goes_through_the_rig_call_gate_like_any_other_bridge(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=_fake_curl(tmp_path))
    result = call({"curl": bridge}, "curl", "get", url="http://target.example/")
    assert result.ok is True


def test_default_bridges_includes_curl_alongside_nmap() -> None:
    bridges = default_bridges()
    assert set(bridges) == {"nmap", "curl"}
    assert isinstance(bridges["curl"], CurlBridge)


def test_installed_version_parses_the_real_curl_version_line(tmp_path: Path) -> None:
    script = tmp_path / "fake-curl"
    script.write_text("#!/bin/sh\necho 'curl 8.22.0 (x86_64-pc-linux-gnu) libcurl/8.22.0'\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    bridge = CurlBridge(executable=script)
    assert bridge.installed_version() == "8.22.0"


def test_installed_version_is_none_when_the_binary_does_not_exist(tmp_path: Path) -> None:
    bridge = CurlBridge(executable=tmp_path / "no-such-binary")
    assert bridge.installed_version() is None


def test_installed_version_is_none_on_unrecognized_output(tmp_path: Path) -> None:
    script = tmp_path / "fake-curl"
    script.write_text("#!/bin/sh\necho 'not curl at all'\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    bridge = CurlBridge(executable=script)
    assert bridge.installed_version() is None
