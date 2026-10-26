# Audit: Autumn-27/ScopeSentry

Source: [github.com/Autumn-27/ScopeSentry](https://github.com/Autumn-27/ScopeSentry), cloned shallow for this audit. "Cyberspace mapping, subdomain enumeration, port scanning, sensitive information discovery, vulnerability scanning, distributed nodes." Despite the name, this is not an AI agent harness at its core: it's a traditional attack-surface-management platform (Go scanner nodes, Python/FastAPI server claimed by the README though not confirmed in the Go code read here, Vue frontend) with an MCP server bolted on so an external agent can drive it as a remote client. Read-only, read by four subagents. See also the prior six audits in this series.

The name raised an obvious question worth checking directly rather than assuming: does "Scope" here mean anything like our Scope Contract? No. It's a false friend, confirmed precisely: "scope" in this codebase means a project's organizational target list, used for asset grouping and filtering in the UI, never for authorization. Nothing in the task-creation or dispatch path checks a target against any declared scope before acting on it.

## Reinforced, not new

**A ninth and tenth confirmation that code-enforced scope doesn't exist, this time in two different ways.** The MCP layer accepts any target string for a scan task with no ownership check, and even has a silent destructive side effect (a project name collision silently replaces the existing project's target list). Separately, the task-dispatch data model shows the same gap from a different angle: a user-supplied target silently overrides a project's own declared target list rather than being checked against it, and project-to-asset association is matched by loose root-domain overlap, not a real containment check. Neither changes [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md); both are more weight behind it.

**A second, independent example of why the gate must be the single mandatory chokepoint.** This repo has two separate code paths that can push a scan target to a node for execution: the normal task-creation flow, and a second path in a Redis log-subscriber that re-dispatches tasks directly on node registration, bypassing the first path's logic entirely. Neither path contains any scope check, but the structural lesson lands precisely on what T3MP3ST's `scopeViolation` finding already taught us: a system with more than one way to reach execution needs the gate at the one point they all share, or in all of them, never in just the one that happens to be checked.

## Rejected, and explicitly why

**Running arbitrary plugin source as interpreted code in the host process, with no sandbox.** This repo's plugin system (Go source, interpreted at runtime via `yaegi`, with full standard-library access including `os/exec`) is a direct illustration of what our already-decided Rig design (ADR 0012: pinned, versioned external binaries called as subprocesses) exists to avoid. A single bad or malicious plugin here can crash the entire host process, and nothing constrains what a plugin can touch. Confirms our decision was the right one, rather than one of several equally reasonable choices.

## Noted, not adopted

**An MCP adapter over an already-clean service layer is cheap when the service layer is clean, but it answers a question exhaust doesn't currently have.** This repo exposes its scanning capabilities over MCP so a separate agent (Cursor, in its own docs) can drive it remotely. Exhaust's own agent drives its own tools directly; there's no second, external agent that needs to call into exhaust the way one calls into this platform. Worth keeping in mind only if that ever changes, not a decision to make now.

## What this settled for exhaust

- Nothing new. [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md) and [ADR 0012](../adr/0012-rig-wraps-a-pinned-tool-catalog.md) are both reinforced by independent evidence from a tool with a genuinely different shape than anything audited so far (a non-agentic scanning platform rather than an AI harness), which is useful precisely because it shows the same gaps recur even outside the agent-harness space this research has mostly been drawing from.
