"""Workspace scaffolding (ADR 0001, ADR 0006).

A Workspace is the per-Target project directory exhaust generates for one
research effort. Scaffolding it never creates a Scope Contract: per ADR
0003 the gate defaults closed, so a freshly scaffolded Workspace is
Sandbox-only until a human adds one.
"""

from pathlib import Path

AGENTS_MD_TEMPLATE = """\
# {target}

This Workspace is confined to the Sandbox until a `SCOPE_CONTRACT.yaml`
authorizes testing against the real Target (see ADR 0003 in the exhaust
project docs).

See `BRIEF.md` for what is attacker-controlled versus trusted on this
Target, its auth model, and known false-positive areas.
"""

BRIEF_MD_TEMPLATE = """\
# Brief: {target}

Fill this in before research starts (ADR 0006).

## Attacker-controlled vs. trusted

(What input reaches the Target from an untrusted party, and what doesn't.)

## Auth model

(How the Target authenticates and authorizes requests.)

## Known false-positive areas

(Behavior that looks like a weakness but isn't, and why.)
"""

SANDBOX_COMPOSE_TEMPLATE = """\
# Sandbox for {target} (ADR: Rig wraps a pinned tool catalog).
#
# Fill in the services needed to stand up a local, isolated instance of
# the Target. This stack is always safe to attack.
"""


def scaffold_workspace(path: Path, target: str) -> None:
    """Create a new Workspace directory for `target` at `path`.

    Raises FileExistsError if `path` already exists, so an operator never
    silently overwrites a prior Workspace's Brief or findings.
    """
    if path.exists():
        raise FileExistsError(f"{path} already exists")

    path.mkdir(parents=True)
    (path / "AGENTS.md").write_text(AGENTS_MD_TEMPLATE.format(target=target))
    (path / "BRIEF.md").write_text(BRIEF_MD_TEMPLATE.format(target=target))

    sandbox_dir = path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "docker-compose.yml").write_text(SANDBOX_COMPOSE_TEMPLATE.format(target=target))

    (path / "poc").mkdir()
    (path / "findings").mkdir()
