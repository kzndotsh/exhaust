"""The Oracle mechanism shapes (ADR 0008).

A Finding may only be marked `confirmed` once a host-run Oracle,
independent of the investigating agent, has verified the claimed effect.
This module defines the shape of an Oracle's result; it does not
implement any actual check. A real check (firing an out-of-band
callback, diffing a control request against an injected one, replaying
an exploit against the Sandbox) needs the Rig's pinned tool catalog and
tool bridges (ADR 0012, ADR 0018), which don't exist yet. What's here
is buildable and enforceable now: the type `findings.py` requires
before it will accept a `confirmed` Verdict.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class OracleMechanism(StrEnum):
    """The five Oracle mechanism shapes ADR 0008 names.

    Each is a way to verify a Finding's claimed effect independently of
    the investigating agent's own report.
    """

    OUT_OF_BAND_CALLBACK = "out_of_band_callback"
    CONTROL_VS_INJECTED_DIFFERENTIAL = "control_vs_injected_differential"
    OBSERVED_EXECUTION_SIGNAL = "observed_execution_signal"
    CROSS_SESSION_ACCESS_DIFFERENTIAL = "cross_session_access_differential"
    INDEPENDENT_GROUND_TRUTH_DIFFERENTIAL = "independent_ground_truth_differential"


@dataclass(frozen=True)
class OracleResult:
    """The outcome of running one Oracle mechanism against a claim.

    Attributes
    ----------
    mechanism : OracleMechanism
        Which mechanism was run.
    passed : bool
        Whether the claimed effect was independently verified.
    detail : str
        What was actually observed (e.g. the callback hit, the diff
        between the control and injected responses).
    """

    mechanism: OracleMechanism
    passed: bool
    detail: str


def oracle_result_to_dict(oracle_result: "OracleResult | None") -> dict[str, Any] | None:
    """Render an OracleResult as a plain dict for JSON storage, or None.

    Parameters
    ----------
    oracle_result : OracleResult | None
        The result to render.

    Returns
    -------
    dict[str, Any] | None
        A plain dict, or None if `oracle_result` was None.
    """
    if oracle_result is None:
        return None
    return {
        "mechanism": oracle_result.mechanism.value,
        "passed": oracle_result.passed,
        "detail": oracle_result.detail,
    }


def oracle_result_from_dict(data: dict[str, Any] | None) -> "OracleResult | None":
    """Reconstruct an OracleResult from the dict `oracle_result_to_dict` rendered.

    Parameters
    ----------
    data : dict[str, Any] | None
        The dict to reconstruct from, or None.

    Returns
    -------
    OracleResult | None
        The reconstructed result, or None if `data` was None.
    """
    if data is None:
        return None
    return OracleResult(
        mechanism=OracleMechanism(data["mechanism"]),
        passed=data["passed"],
        detail=data["detail"],
    )
