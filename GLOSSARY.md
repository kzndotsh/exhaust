# Exhaust

Exhaust is an agent-first toolkit for security research. From it you scaffold a self-contained Workspace per Target, and it provides what an agent needs to probe that Target autonomously and exhaustively: the Rig it works from, a library of skills, a Playbook, and the Harness that drives the agent through it.

## Language

**Exhaust**:
The project, and the act it is named for. To exhaust a Target is to work through every known angle of attack until the options are spent, not to stop at the first finding.
_Avoid_: scanner, framework

**Target**:
The single piece of software a Workspace is dedicated to researching (for example Roundcube, ispmanager).
_Avoid_: victim, host, app

**Workspace**:
The per-Target project directory Exhaust generates for one research effort. Holds the Target's source, its Sandbox, proof-of-concept work, and the report.
_Avoid_: project, repo, folder

**Sandbox**:
The isolated, local instance of the Target you attack, stood up inside its Workspace (today a docker-compose stack) and always safe to attack. One Sandbox per Workspace, created by Exhaust. Where the Rig is what you attack from, the Sandbox is what you attack.
_Avoid_: rig, environment

**Scope Contract**:
A per-Workspace file declaring what the agent may touch: the Target in scope, how far testing may go, and the basis for that authority (owned infrastructure, a published bug-bounty scope, or written permission). With no Scope Contract the agent is confined to the Sandbox; reaching a real remote Target requires one.
_Avoid_: scope file, rules of engagement

**Rig**:
The shared host environment you attack *from*: the research tooling and network access every Workspace relies on. Exhaust provides it, starting with a Nix definition and open to other methods later (a container image or install script). One Rig per machine. A Sandbox is the Target you attack and lives in one Workspace; the Rig is the kit you attack from and is shared across all of them.
_Avoid_: sandbox, workspace

**Brief**:
A hand-written, per-Workspace statement of what is attacker-controlled versus trusted for this Target, its auth model, and known false-positive areas, kept in its own `BRIEF.md`. The Workspace's `AGENTS.md` (or `CLAUDE.md`) references it explicitly, so it is pulled into every agent turn on purpose rather than relying on a harness's own undocumented file-discovery rules.
_Avoid_: context, notes

**Finding**:
A claim that a Target has a specific weakness, stored as one record with a deterministic id, a severity, a repro/evidence block, and a scope field (Sandbox-only or real Target). A Finding is never deleted; a verdict (confirmed, false-positive, duplicate, fixed, accepted-risk) is recorded on it instead, preserving the original severity alongside any adjustment.
_Avoid_: vulnerability, bug, result

**Verdict**:
A typed, tool-recorded outcome attached to a Finding after investigation (confirmed, false-positive, duplicate, fixed, accepted-risk). Recorded through a structured call the Harness validates, never accepted as free prose, so a verdict cannot be lost or misread in an agent's narration.
_Avoid_: status, result

**Oracle**:
A host-executed, independent check that confirms a Finding's evidence actually produces the claimed effect (for example, replaying a repro against the Sandbox and checking the result), as distinct from an agent's self-attested claim. A Finding may only carry the `confirmed` Verdict once an Oracle has run.
_Avoid_: grader, judge

**Playbook**:
A Workspace's full set of Verticals: the always-required ones every Workspace walks regardless of Target, plus the gated ones that turn on once recon confirms the trust boundary they cover. Computed from the skill files themselves, never hand-maintained as a second list.
_Avoid_: spine, methodology checklist

**Vertical**:
One item on a Playbook: a category of weakness or behavior the Harness tracks to a terminal state (for example injection, access control, race conditions). Carries `required` (always runs, or only on a confirmed trigger) and, when not required, a `gate` describing that trigger. Not a vector (an entry point on the Target) or a technique (a specific move tried against one) — those exist inside a vertical's investigation, not instead of it.
_Avoid_: module, companion, class, category

**Harness**:
The runtime that drives an agent through a Workspace. It invokes the agent, manages its context, exposes the Rig's tools, and loops it over the Workspace's Playbook until every vertical is terminal. The Harness runs the agent; the model is the coprocessor inside it.
_Avoid_: loop, driver, orchestrator

**Disclosure**:
The act of reporting a confirmed finding to the Target's owner, and the record of its status. Exhaust surfaces the Target's reporting policy (security.txt, SECURITY.md, bug-bounty or GitHub advisory program) and leaves a place to track what was reported, where, and the outcome.
_Avoid_: report (the written document), bounty
