"""A run's turn/time budget."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RunBudget:
    """How far one `Harness.run()` call is allowed to go.

    Frozen: a run can never mutate its own budget mid-flight. Carries no
    cost ceiling yet, since nothing today can report spend; extend this
    once the ADR 0021 credential proxy can.

    Attributes
    ----------
    max_turns : int
        The most agent turns this run will take before halting.
    max_wall_seconds : float | None
        An optional wall-clock ceiling for the run.
    """

    max_turns: int
    max_wall_seconds: float | None = None
