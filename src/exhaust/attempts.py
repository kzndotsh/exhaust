"""Per-vertical tool-attempt log, so a `SelfReport` can be checked, not trusted.

A `SelfReport`'s `tools_exercised` claim (ADR 0005) is only worth
anything if it's checked against what the agent actually did, not taken
on its own say-so. This module is that record: every time the Harness
actually dispatches a Rig tool call on a vertical's behalf, it appends
one line here. Append-only, like `findings.jsonl`: a tool invocation
that happened is a fact about history, not mutable current state the
way `ledger.json`'s per-vertical state is, so there's nothing to
rewrite and no reason to hold it as a JSON object keyed by vertical.
"""

import json
from pathlib import Path

ATTEMPTS_FILENAME = "attempts.jsonl"


def _attempts_path(workspace_dir: Path) -> Path:
    return workspace_dir / ATTEMPTS_FILENAME


def record_attempt(workspace_dir: Path, vertical: str, tool: str) -> None:
    """Append one record: `tool` was actually dispatched on `vertical`'s behalf.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to record into.
    vertical : str
        The vertical the call was made on behalf of.
    tool : str
        The Rig tool that was actually dispatched.
    """
    path = _attempts_path(workspace_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"vertical": vertical, "tool": tool}, sort_keys=True) + "\n")


def tools_exercised(workspace_dir: Path, vertical: str) -> frozenset[str]:
    """Return every distinct tool actually dispatched for `vertical`.

    Parameters
    ----------
    workspace_dir : Path
        The Workspace to read from.
    vertical : str
        The vertical to look up.

    Returns
    -------
    frozenset[str]
        Every tool name recorded for `vertical`, deduplicated. Empty if
        none has been recorded yet, including if the log file itself
        doesn't exist yet.
    """
    path = _attempts_path(workspace_dir)
    if not path.is_file():
        return frozenset()

    records = (json.loads(line) for line in path.read_text().splitlines() if line.strip())
    return frozenset(record["tool"] for record in records if record["vertical"] == vertical)
