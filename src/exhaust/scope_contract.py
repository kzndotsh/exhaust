"""The Scope Contract gate (ADR 0003).

With no Scope Contract in a Workspace, the agent is confined to the Sandbox.
Reaching a real, remote Target requires a Scope Contract naming that Target,
the permitted extent of testing, and the basis for authority. The gate
defaults closed: a missing, unreadable, or malformed contract denies real-
Target action rather than permitting it.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

CONTRACT_FILENAME = "SCOPE_CONTRACT.yaml"

VALID_BASES = frozenset(
    {"owned_infrastructure", "bug_bounty_scope", "written_permission"}
)


@dataclass(frozen=True)
class ScopeContract:
    target: str
    basis: str
    extent: str


def load_scope_contract(workspace_dir: Path) -> ScopeContract | None:
    """Load the Workspace's Scope Contract, or None if absent or invalid.

    Returns None rather than raising on a malformed file: the gate must
    fail closed, and a contract that can't be parsed is no contract at all.
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
    """The gate every real-Target action must pass before it executes.

    Re-checked at the point of action, not only when the action was
    proposed: the contract on disk is the live authority, not a cached
    decision from earlier in the run.
    """
    contract = load_scope_contract(workspace_dir)
    if contract is None:
        return False
    return contract.target == action_target
