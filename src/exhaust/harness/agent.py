"""The agent-invocation seam (ADR 0007, ADR 0021).

No concrete agent SDK is named here on purpose: which one gets used, and
how ADR 0021's budget-capped credential proxy gets wired into it, is a
separate, still-open decision. Whatever adapter is written later
implements `AgentSession` and is handed to a `Harness` as a constructor
argument; a `Harness` never imports a concrete SDK itself.
"""

from dataclasses import dataclass
from typing import Protocol

from exhaust.catalog import VerticalEntry
from exhaust.harness.actions import ActionOutcome, AgentAction
from exhaust.rig import ToolInfo


@dataclass(frozen=True)
class AgentTurnRequest:
    """Everything one agent turn needs, and nothing it doesn't.

    `procedure` is loaded just-in-time for the active vertical only
    (ADR 0013's progressive disclosure); an inactive vertical's procedure
    never enters context.

    Attributes
    ----------
    vertical : VerticalEntry
        The vertical currently active.
    procedure : str
        That vertical's full procedure doc.
    available_tools : tuple[ToolInfo, ...]
        What the Rig currently has registered.
    """

    vertical: VerticalEntry
    procedure: str
    available_tools: tuple[ToolInfo, ...]


class AgentSession(Protocol):
    """A live agent bound to one Workspace run.

    Two methods, not one: `step` proposes, `observe` delivers the
    validated outcome back. A single `take_turn(request)` carrying the
    full transcript was considered and rejected, since it would force
    every adapter to reconstruct and re-thread history even for one
    wrapping a live, stateful SDK session that already keeps its own.
    """

    def step(self, request: AgentTurnRequest) -> AgentAction:
        """Present `request`, return the agent's next proposed action."""
        ...

    def observe(self, outcome: ActionOutcome) -> None:
        """Deliver the validated outcome of the action just dispatched."""
        ...
