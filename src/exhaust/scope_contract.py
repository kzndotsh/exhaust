"""The Scope Contract gate (ADR 0003).

With no Scope Contract in a Workspace, the agent is confined to the Sandbox.
Reaching a real, remote Target requires a Scope Contract naming that Target,
the permitted extent of testing, and the basis for authority. The gate
defaults closed: a missing, unreadable, or malformed contract denies real-
Target action rather than permitting it.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

CONTRACT_FILENAME = "SCOPE_CONTRACT.yaml"

VALID_BASES = frozenset({"owned_infrastructure", "bug_bounty_scope", "written_permission"})


@dataclass(frozen=True)
class ScopeContract:
    """A Workspace's authorization to test a real, remote Target.

    Attributes
    ----------
    target : str
        The Target this contract authorizes.
    basis : str
        The authority basis: one of `VALID_BASES`.
    extent : str
        The permitted extent of testing.
    """

    target: str
    basis: str
    extent: str


def load_scope_contract(workspace_dir: Path) -> ScopeContract | None:
    """Load the Workspace's Scope Contract, or None if absent or invalid.

    Returns None rather than raising on a malformed file: the gate must
    fail closed, and a contract that can't be parsed is no contract at all.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace directory to look for `SCOPE_CONTRACT.yaml` in.

    Returns
    -------
    ScopeContract | None
        The parsed contract, or None if missing or invalid.
    """
    contract_path = workspace_dir / CONTRACT_FILENAME
    if not contract_path.is_file():
        return None

    try:
        data = yaml.safe_load(contract_path.read_text())
    except yaml.YAMLError:
        return None

    if not isinstance(data, dict):
        return None
    data = cast(dict[str, Any], data)

    target = data.get("target")
    basis = data.get("basis")
    extent = data.get("extent")
    if not isinstance(target, str) or not target:
        return None
    if basis not in VALID_BASES:
        return None
    if not isinstance(extent, str) or not extent:
        return None

    return ScopeContract(target=target, basis=basis, extent=extent)


def is_in_scope(workspace_dir: Path, action_target: str) -> bool:
    """Check whether `action_target` is authorized for this Workspace.

    This is the gate every real-Target action must pass before it
    executes. Re-check at the point of action, not only when the action
    was proposed: the contract on disk is the live authority, not a
    cached decision from earlier in the run.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace directory to load the Scope Contract from.
    action_target : str
        The Target the pending action would touch.

    Returns
    -------
    bool
        True only if a valid contract exists and names this exact Target.
    """
    contract = load_scope_contract(workspace_dir)
    if contract is None:
        return False
    return contract.target == action_target
