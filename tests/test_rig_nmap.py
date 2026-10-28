import stat
from pathlib import Path

from exhaust.rig.bridges import call
from exhaust.rig.wrappers import default_bridges
from exhaust.rig.wrappers.nmap import NmapBridge

_FAKE_NMAP = """\
#!/usr/bin/env python3
import sys
print(" ".join(sys.argv[1:]))
sys.exit({exit_code})
"""


def _fake_nmap(tmp_path: Path, *, exit_code: int = 0) -> Path:
    script = tmp_path / "fake-nmap"
    script.write_text(_FAKE_NMAP.format(exit_code=exit_code))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_info_and_methods_are_recon_tier_and_non_mutating() -> None:
    bridge = NmapBridge()
    assert bridge.info.name == "nmap"
    for method in bridge.methods:
        assert method.required_extent == "recon"
        assert method.mutates is False
        assert method.consequential is False


def test_tcp_connect_scan_invokes_nmap_with_the_right_flags(tmp_path: Path) -> None:
    bridge = NmapBridge(executable=_fake_nmap(tmp_path))
    result = bridge.run("tcp_connect_scan", host="scanme.example")
    assert result.ok is True
    assert result.output.strip() == "-Pn -sT scanme.example"


def test_service_version_scan_passes_ports_through(tmp_path: Path) -> None:
    bridge = NmapBridge(executable=_fake_nmap(tmp_path))
    result = bridge.run("service_version_scan", host="10.0.0.1", ports="22,80,8000-8010")
    assert result.ok is True
    assert result.output.strip() == "-Pn -sV -p 22,80,8000-8010 10.0.0.1"


def test_a_nonzero_exit_is_reported_as_not_ok(tmp_path: Path) -> None:
    bridge = NmapBridge(executable=_fake_nmap(tmp_path, exit_code=1))
    result = bridge.run("tcp_connect_scan", host="scanme.example")
    assert result.ok is False


def test_an_unknown_method_is_refused_without_invoking_the_binary(tmp_path: Path) -> None:
    # Regression: run() must refuse the same way call()'s own gate does, since
    # nothing stops a future caller from invoking run() directly (ADR 0018).
    marker = tmp_path / "invoked"
    script = tmp_path / "fake-nmap"
    script.write_text(f"#!/bin/sh\ntouch {marker}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    bridge = NmapBridge(executable=script)
    result = bridge.run("drop_database", host="scanme.example")

    assert result.ok is False
    assert not marker.exists()


def test_a_host_starting_with_a_dash_is_refused_not_passed_to_nmap(tmp_path: Path) -> None:
    # A value like "--script=vuln" must never reach argv as the host: that would
    # smuggle in capability this bridge never declared (ADR 0018).
    marker = tmp_path / "invoked"
    script = tmp_path / "fake-nmap"
    script.write_text(f"#!/bin/sh\ntouch {marker}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    bridge = NmapBridge(executable=script)
    result = bridge.run("tcp_connect_scan", host="--script=vuln")

    assert result.ok is False
    assert not marker.exists()


def test_ports_with_anything_but_digits_commas_and_hyphens_is_refused(tmp_path: Path) -> None:
    marker = tmp_path / "invoked"
    script = tmp_path / "fake-nmap"
    script.write_text(f"#!/bin/sh\ntouch {marker}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    bridge = NmapBridge(executable=script)
    result = bridge.run("tcp_connect_scan", host="scanme.example", ports="80; rm -rf /")

    assert result.ok is False
    assert not marker.exists()


def test_a_missing_host_is_refused(tmp_path: Path) -> None:
    bridge = NmapBridge(executable=_fake_nmap(tmp_path))
    result = bridge.run("tcp_connect_scan")
    assert result.ok is False


def test_goes_through_the_rig_call_gate_like_any_other_bridge(tmp_path: Path) -> None:
    bridge = NmapBridge(executable=_fake_nmap(tmp_path))
    result = call({"nmap": bridge}, "nmap", "tcp_connect_scan", host="scanme.example")
    assert result.ok is True


def test_default_bridges_includes_nmap() -> None:
    bridges = default_bridges()
    assert set(bridges) == {"nmap"}
    assert isinstance(bridges["nmap"], NmapBridge)
