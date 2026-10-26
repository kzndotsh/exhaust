# Audit: cloudflare/cloudflare-os

Source: [github.com/cloudflare/cloudflare-os](https://github.com/cloudflare/cloudflare-os), cloned shallow for this audit. "An AI productivity environment" built internally at Cloudflare and open-sourced, not a security tool at all: agents build per-user sandboxed apps ("Gadgets") and reach external services only through a capability-based broker ("Gatekeepers") that can defer human approval by simulating an action's result so the agent isn't blocked waiting. Audited specifically for its approval-gating and capability-scoping design, which bears directly on our Scope Contract and crash-handling decisions even though the domain (productivity apps, not pentesting) is completely different. Read-only, read by five subagents.

## The headline finding: a real alternative, seriously considered and explicitly rejected

Cloudflare OS's signature idea is that a side-effecting action awaiting human approval doesn't have to block the agent. A pure, gatekeeper-supplied function locally simulates the action's outcome, the agent reads that simulated state back and keeps working as if the action already succeeded, and the real provider call only fires once a human actually approves it, possibly much later, possibly in a batch.

We looked at this seriously as a candidate for how exhaust's Scope Contract and Oracle checks might avoid blocking the Harness, and are explicitly not adopting it, for reasons this audit surfaced directly. First, it only works where a pure local simulator can model the action's effect without actually performing it; the project's own code requires this capability to be declared per action, and anything without one falls back to blocking exactly the way our design already does. An attack against a real Target has no such local simulator: you cannot predict what exploiting a vulnerability will actually do without doing it. Second, and more importantly, the project's own internal planning notes admit an unresolved gap: if a human later rejects an action the agent already built further work on top of as if it had succeeded, there is no rollback, and the question of what should happen is explicitly flagged as unsolved before this reaches production maturity. Proceeding against a real Target as if authorization were already granted, before it actually is, is precisely the failure mode our Scope Contract exists to prevent. The asymmetry matters: Cloudflare's worst case is a wrongly-simulated email draft; ours would be a wrongly-simulated green light to attack something. Decided to keep blocking as the default with no Scope Contract present; this strengthens [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md) rather than changing it.

## Adopted or sharpened

**Distinguish a known failure from a genuinely unknown outcome, and never auto-retry the unknown one.** Cloudflare's own deferred-action system makes exactly this split (a declared terminal failure is safe to retry or abandon; an outcome-unknown state is held open and never silently replayed). Folded into [ADR 0015](../adr/0015-crash-mid-real-target-action-blocks-not-retries.md) as the concrete shape "ambiguous outcome" should take.

**Re-check the Scope Contract immediately before an action executes, not only when it was first proposed.** Cloudflare's system binds an action's authorization to an identity check at queue time and checks that binding again right before applying it, because time passes and circumstances can change in between. Folded into [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md).

**A third independent confirmation of the single-mandatory-chokepoint principle.** One function is the sole place any capability gets minted, named explicitly in the project's own review guidelines as the bar every reviewer checks. Same lesson as T3MP3ST's `scopeViolation` and ScopeSentry's dual dispatch paths, now seen in a system built by a different team for a completely different purpose.

**A concrete, working example of the scope-binding mechanism itself.** A GitHub capability binds to exactly one repository by its immutable numeric ID at creation, every subsequent API call is checked against that binding, and search results are independently verified to stay inside it. This is the actual shape our Scope Contract's enforcement code should take: bind an identity into state the agent cannot alter, check every action against that bound state, not a separately-maintained allowlist that could drift from it.

**Keep approval policy itself outside what the agent can write.** Authentication and auto-approval configuration are deliberately kept in environment variables outside the system's own mutable data store, specifically so a compromised session can't grant itself more trust. Directly applicable: the Scope Contract's own authority should live somewhere the agent's actions cannot modify, not merely somewhere the Harness happens to check first.

## Noted, not adopted

**Deny-by-default capability passing (no ambient access; a Worker only has the bindings it was explicitly handed) and full network denial by default for sandboxed code.** Good general discipline, but the "no network" half doesn't transfer: exhaust's Sandbox exists specifically to be reached. The capability-scoping half is already consistent with our design.

**An in-process fetch-hook egress allowlist used during the project's own agent evals**, confirmed by its own code comments to only cover requests through that one process, not raw sockets or subprocesses. A real idea for restricting what a benchmark run can reach, but an honest instance of the same caveat raised earlier: a JS-level or process-level hook alone doesn't prove isolation; proving it needs an OS- or network-level check too.

**Its own eval harness is deterministic (no LLM-as-judge in the scoring path) but not blind.** Ground truth lives in the same file as the task's prompt in every example, so it's a real deterministic scorer, just not a held-out one in the sense [ADR 0014](../adr/0014-eval-uses-blind-held-out-ground-truth.md) means. Confirms the deterministic-scoring half of that ADR without adding anything new.

## Rejected, and why

- **Code review before an agent's generated code ever executes.** Agent-written app code runs immediately in a live preview; a human only reviews it at the point of merging into the permanent version. Reasonable for a productivity app whose code is first-party-generated and sandboxed from the network; wrong model for a tool whose whole job is running code against something adversarial.
- **A V8-isolate boundary as the sole isolation mechanism.** Appropriate for trusted, generated application code with no network reach. Not strong enough for anything resembling hostile input or real exploit traffic, which is explicitly what exhaust's Sandbox has to contain; a real VM or container boundary with its own network policy is the right comparison there, not a language-level isolate.

## What this settled for exhaust

- [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md) sharpened twice: re-check immediately before execution, and keep authority outside anything the agent can write to.
- [ADR 0015](../adr/0015-crash-mid-real-target-action-blocks-not-retries.md) sharpened: known-failed versus outcome-unknown is the distinction that decides whether a retry is ever safe.
- A serious alternative to blocking (deferred/simulated approval) considered and explicitly declined, with the reasoning preserved here rather than left implicit.
