from pathlib import Path

from exhaust.surface import (
    GateSignal,
    GateStatus,
    InputKind,
    SurfaceInput,
    enumerated_inputs,
    is_gate_satisfied,
    load_surface,
    record_gate_signal,
    record_input,
)


def _input(**overrides: object) -> SurfaceInput:
    defaults: dict[str, object] = {
        "kind": InputKind.QUERY_PARAM,
        "location": "https://target/search",
        "name": "q",
        "reach_method": "get",
        "reach_param": "query",
        "normal_value": "test",
        "source": "recon",
    }
    defaults.update(overrides)
    return SurfaceInput(**defaults)  # type: ignore[arg-type]


def test_a_fresh_workspace_has_an_empty_surface(tmp_path: Path) -> None:
    surface = load_surface(tmp_path)
    assert surface.inputs == ()
    assert surface.signals == ()


def test_recorded_inputs_are_readable_back(tmp_path: Path) -> None:
    record_input(tmp_path, _input())
    record_input(tmp_path, _input(name="page", reach_param="query"))

    inputs = enumerated_inputs(tmp_path)
    assert {inp.name for inp in inputs} == {"q", "page"}


def test_re_recording_the_same_identity_is_a_no_op(tmp_path: Path) -> None:
    record_input(tmp_path, _input(normal_value="first"))
    record_input(tmp_path, _input(normal_value="second"))

    inputs = enumerated_inputs(tmp_path)
    assert len(inputs) == 1
    assert inputs[0].normal_value == "first"


def test_a_different_source_is_not_a_distinct_identity(tmp_path: Path) -> None:
    record_input(tmp_path, _input(source="recon"))
    record_input(tmp_path, _input(source="injection"))

    assert len(enumerated_inputs(tmp_path)) == 1


def test_inputs_differing_by_reach_are_distinct(tmp_path: Path) -> None:
    record_input(tmp_path, _input(reach_method="get", reach_param="query"))
    record_input(tmp_path, _input(reach_method="post_form", reach_param="data"))

    assert len(enumerated_inputs(tmp_path)) == 2


def test_an_unconfirmed_gate_is_not_satisfied(tmp_path: Path) -> None:
    assert is_gate_satisfied(tmp_path, "reverse-proxy-confirmed") is False


def test_a_confirmed_signal_satisfies_its_own_gate_only(tmp_path: Path) -> None:
    record_gate_signal(
        tmp_path,
        GateSignal(
            signal="reverse-proxy-confirmed",
            status=GateStatus.CONFIRMED,
            evidence="Via header present",
            source="recon",
        ),
    )

    assert is_gate_satisfied(tmp_path, "reverse-proxy-confirmed") is True
    assert is_gate_satisfied(tmp_path, "graphql-confirmed") is False


def test_a_refuted_signal_does_not_satisfy_its_gate(tmp_path: Path) -> None:
    record_gate_signal(
        tmp_path,
        GateSignal(
            signal="reverse-proxy-confirmed",
            status=GateStatus.REFUTED,
            evidence="no Via header on any response",
            source="recon",
        ),
    )

    assert is_gate_satisfied(tmp_path, "reverse-proxy-confirmed") is False


def test_a_later_confirmed_signal_wins_over_an_earlier_refuted_one(tmp_path: Path) -> None:
    record_gate_signal(
        tmp_path,
        GateSignal(
            signal="reverse-proxy-confirmed",
            status=GateStatus.REFUTED,
            evidence="not seen during recon",
            source="recon",
        ),
    )
    record_gate_signal(
        tmp_path,
        GateSignal(
            signal="reverse-proxy-confirmed",
            status=GateStatus.CONFIRMED,
            evidence="X-Forwarded-For honored mid-run",
            source="access-control",
        ),
    )

    assert is_gate_satisfied(tmp_path, "reverse-proxy-confirmed") is True


def test_a_mid_run_discovery_is_recorded_the_same_way_as_recons_own_pass(tmp_path: Path) -> None:
    record_input(tmp_path, _input(name="q", source="recon"))
    record_input(tmp_path, _input(name="debug", normal_value="0", source="injection"))

    names = {inp.name for inp in enumerated_inputs(tmp_path)}
    assert names == {"q", "debug"}
