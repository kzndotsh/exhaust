"""The Target's observed surface (ADR 0011, ADR 0024).

Every vertical's Procedure needs to know what inputs the Target exposes and
which gated verticals' trust-boundary signals have actually been observed.
This module is the shared, append-only record of both: an observation is
never deleted, and re-recording the same input or gate signal is a no-op the
reader absorbs, so the initial recon pass running once, running twice, or a
later vertical surfacing something new mid-run are all the same code path.

This module knows nothing about the Rig, the catalog, or the ledger — it
enforces its store's shape, not who may write to it or what a confirmed
signal should do for scheduling. Composing this module with
`catalog.required_gate_signals` and `ledger.transition` to decide which
verticals are eligible to run is the Harness's job, once it exists.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

SURFACE_FILENAME = "surface.jsonl"


class InputKind(StrEnum):
    """The closed set of request-shaped input locations a Target exposes.

    A vocabulary of HTTP input shapes, bounded by the protocol itself, not a
    catalog of verticals or of gate signals: ADR 0016's no-hand-maintained-
    catalog rule has nothing to say about it, the same way it has nothing to
    say about `ledger.VerticalState`.
    """

    QUERY_PARAM = "query_param"
    FORM_FIELD = "form_field"
    HEADER = "header"
    COOKIE = "cookie"
    PATH_SEGMENT = "path_segment"
    UPLOAD_FILENAME = "upload_filename"


@dataclass(frozen=True)
class SurfaceInput:
    """One input the Target exposes, as recon or a later vertical observed it.

    Attributes
    ----------
    kind : InputKind
        What kind of input this is.
    location : str
        The URL or endpoint this input was observed on.
    name : str
        The parameter, header, field, or cookie name (empty for a bare
        path segment).
    reach_method : str
        The Rig method name a consuming vertical calls to place a value
        at this input (e.g. `"get"`, `"post_form"`). Recording this once,
        here, is what lets every consuming vertical skip re-deriving its
        own "input shape -> Rig method" mapping.
    reach_param : str
        The `reach_method` keyword argument a payload goes into (e.g.
        `"query"`, `"path_segment"`).
    normal_value : str
        A well-formed value, so a consuming vertical can record its own
        baseline before probing.
    source : str
        `"recon"` for the initial pass, or the name of whichever vertical
        surfaced this input mid-run.
    """

    kind: InputKind
    location: str
    name: str
    reach_method: str
    reach_param: str
    normal_value: str
    source: str


class GateStatus(StrEnum):
    """Whether an observation confirmed or refuted a declared gate."""

    CONFIRMED = "confirmed"
    REFUTED = "refuted"


@dataclass(frozen=True)
class GateSignal:
    """One observation about a gated vertical's declared trust boundary.

    Attributes
    ----------
    signal : str
        Matches, verbatim, some gated vertical's own `gate` front-matter
        string (ADR 0011). The set of signals worth observing is never
        declared here: it is derived from the catalog
        (`catalog.required_gate_signals`), so this module carries no
        vocabulary of its own.
    status : GateStatus
        Whether this observation confirmed or refuted the signal.
    evidence : str
        What was actually observed, for the audit trail.
    source : str
        `"recon"` for the initial pass, or the name of whichever vertical
        recorded this signal mid-run.
    """

    signal: str
    status: GateStatus
    evidence: str
    source: str


@dataclass(frozen=True)
class Surface:
    """The reconstructed, de-duplicated view a reader gets.

    Attributes
    ----------
    inputs : tuple[SurfaceInput, ...]
        Every distinct input observed so far, by identity (kind, location,
        name, reach_method, reach_param); the first recording of a given
        identity wins, later re-observations are absorbed as a no-op.
    signals : tuple[GateSignal, ...]
        Every gate observation recorded so far, in record order. Not
        de-duplicated: `is_gate_satisfied` only needs to find one
        `CONFIRMED` match, so keeping every observation preserves the
        audit trail at no extra cost.
    """

    inputs: tuple[SurfaceInput, ...]
    signals: tuple[GateSignal, ...]


def _surface_path(workspace_dir: Path) -> Path:
    return workspace_dir / "surface" / SURFACE_FILENAME


def _read_events(workspace_dir: Path) -> list[dict[str, Any]]:
    path = _surface_path(workspace_dir)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_event(workspace_dir: Path, event: dict[str, Any]) -> None:
    path = _surface_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def _input_to_dict(inp: SurfaceInput) -> dict[str, Any]:
    return {
        "kind": inp.kind.value,
        "location": inp.location,
        "name": inp.name,
        "reach_method": inp.reach_method,
        "reach_param": inp.reach_param,
        "normal_value": inp.normal_value,
        "source": inp.source,
    }


def _input_from_dict(data: dict[str, Any]) -> SurfaceInput:
    return SurfaceInput(
        kind=InputKind(data["kind"]),
        location=data["location"],
        name=data["name"],
        reach_method=data["reach_method"],
        reach_param=data["reach_param"],
        normal_value=data["normal_value"],
        source=data["source"],
    )


def _input_identity(inp: SurfaceInput) -> tuple[str, str, str, str, str]:
    return (inp.kind.value, inp.location, inp.name, inp.reach_method, inp.reach_param)


def _signal_to_dict(sig: GateSignal) -> dict[str, Any]:
    return {
        "signal": sig.signal,
        "status": sig.status.value,
        "evidence": sig.evidence,
        "source": sig.source,
    }


def _signal_from_dict(data: dict[str, Any]) -> GateSignal:
    return GateSignal(
        signal=data["signal"],
        status=GateStatus(data["status"]),
        evidence=data["evidence"],
        source=data["source"],
    )


def record_input(workspace_dir: Path, inp: SurfaceInput) -> None:
    """Append one observed input.

    Never checks for a prior recording of the same identity: the reader
    (`load_surface`) de-duplicates, so re-observing an input — recon
    running again, or a second vertical independently finding the same
    field — is a silent no-op rather than an error. Unlike
    `findings.record_finding`, which raises on a duplicate id because a
    Finding is a claim a human reasons about one at a time, an input is
    an observation many actors legitimately re-report.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to record into.
    inp : SurfaceInput
        The input observed.
    """
    _append_event(workspace_dir, {"event": "input", **_input_to_dict(inp)})


def record_gate_signal(workspace_dir: Path, sig: GateSignal) -> None:
    """Append one gate observation.

    Append-only, like `record_input`: a later `CONFIRMED` for the same
    signal after an earlier `REFUTED` simply adds a second, newer
    observation to the record. `is_gate_satisfied` resolves what that
    means for scheduling; this function only records what was seen.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to record into.
    sig : GateSignal
        The gate observation.
    """
    _append_event(workspace_dir, {"event": "signal", **_signal_to_dict(sig)})


def load_surface(workspace_dir: Path) -> Surface:
    """Reconstruct the Surface from every event recorded so far.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to read from.

    Returns
    -------
    Surface
        Inputs de-duplicated by identity (first recording wins) and every
        gate signal in record order. A Workspace recon hasn't touched yet
        yields an empty Surface, not an error.
    """
    events = _read_events(workspace_dir)

    inputs_by_identity: dict[tuple[str, str, str, str, str], SurfaceInput] = {}
    signals: list[GateSignal] = []
    for event in events:
        if event["event"] == "input":
            inp = _input_from_dict(event)
            inputs_by_identity.setdefault(_input_identity(inp), inp)
        elif event["event"] == "signal":
            signals.append(_signal_from_dict(event))

    return Surface(inputs=tuple(inputs_by_identity.values()), signals=tuple(signals))


def enumerated_inputs(workspace_dir: Path) -> tuple[SurfaceInput, ...]:
    """Return the Workspace's de-duplicated inputs.

    The one call a consuming vertical's step 1 makes.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to read from.

    Returns
    -------
    tuple[SurfaceInput, ...]
        Every distinct input observed so far.
    """
    return load_surface(workspace_dir).inputs


def is_gate_satisfied(workspace_dir: Path, gate: str) -> bool:
    """Whether `gate` has at least one `CONFIRMED` observation on record.

    This is the entire mechanical meaning of ADR 0011's "a recon-confirmed
    signal": a gated vertical is eligible once, and only once, this is
    true. A `REFUTED` signal, or no signal at all, is not satisfied. Pure
    function of the store, re-evaluated on every call, so a later
    `CONFIRMED` takes effect with nothing to invalidate.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to read from.
    gate : str
        The gate string, as declared in some vertical's own front matter.

    Returns
    -------
    bool
        True iff a `CONFIRMED` `GateSignal` with `signal == gate` exists.
    """
    return any(
        signal.signal == gate and signal.status == GateStatus.CONFIRMED
        for signal in load_surface(workspace_dir).signals
    )
