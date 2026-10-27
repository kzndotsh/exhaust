# Audit: j3ssie/osmedeus

Source: [github.com/j3ssie/osmedeus](https://github.com/j3ssie/osmedeus), cloned shallow for this audit. "A Modern Orchestration Engine for Security." A mature, long-running Go security-automation engine predating the AI-agent wave, now extended with "Agentic LLM Steps" and ACP subprocess agents. Read-only, read by five subagents. See also the prior seven audits in this series.

## The open question this surfaces, not resolved here

**How exhaust's Harness technically drives its agent is a real, unsettled design question, and this audit sharpens exactly what's at stake.** This repo supports three distinct modes: an embedded agent loop it fully owns, driving an external coding-agent CLI (Claude Code, Codex, OpenCode, Gemini) over the generic Agent Client Protocol, and driving one via a dedicated SDK. Only the embedded-loop mode allows per-action interception. Over ACP specifically, individual tool calls happen entirely inside the external CLI's own process; the only hook is a coarse permission callback (which this implementation auto-approves wholesale), and neither the call's arguments nor its result ever reach the orchestrating code. Every one of our safety-related ADRs (the Scope Contract, the Oracle, evidence promotion) assumes the Harness can see and gate individual tool calls. We never explicitly decided whether exhaust's Harness is an embedded loop, a specific agent CLI with its own richer native hook system (distinct from generic ACP), or something else; this is worth resolving deliberately rather than by default once we're past the spine.

## Adopted or reinforced

**A documented at-least-once task-claim protocol.** `BLMOVE` into a per-worker processing list, with an acknowledgment only after a running-marker is set, plus two separate recovery sweeps (per-worker and orphaned). The project's own docs explain why a simpler `BRPOP` was rejected. Cleaner than the master-worker patterns seen in prior audits.

**Secrets load from environment via reflection but never round-trip back to disk.** A clean pattern worth keeping if exhaust ever needs config persistence alongside secret environment overrides.

**A vivid, concrete instance of why "prove it works" matters for safety code specifically, not just features.** This repo's own cloud cleanup-on-failure logic has a bug that makes it dead code: the condition it checks can never be true, because every provider's error path returns a value the condition requires to be non-null. Paired with a README claiming graceful shutdown on interrupt signals that doesn't exist anywhere in the code. A safety mechanism that looks correct in review but structurally never fires is worse than having none, since it's trusted. If exhaust ever provisions real cloud infrastructure for a Sandbox, the teardown guarantee needs to live on the provider side (a TTL, an auto-shutdown), not solely in client-side cleanup code, however carefully that code reads.

**A declarative workflow DSL was genuinely considered for the spine, and rejected, with a clear reason.** This repo's own shipped example workflows are explicitly labeled "Test Style," using simulated tool output rather than real tools, and its conditional-branching syntax only reaches as far as string expressions over templated values. Judging whether a Target uses a particular stack still needs either a scripted heuristic or an agent doing the actual judgment, at which point the agent is doing the real work anyway and the YAML layer adds an engine dependency without adding real capability. This confirms the skill-file approach already decided (ADR 0011), rather than suggesting we revisit it.

## Rejected, and explicitly why

- **An unauthenticated webhook where a bare UUID is the only credential, and that UUID's holder can override which target gets scanned.** Documented by the project itself as intentional design. This is exactly the shape of anti-pattern a Scope Contract exists to prevent: an identifier that isn't itself an authorization check being treated as sufficient to redirect what gets attacked.
- **Logging a fully rendered command (secrets included) at debug level before it reaches the shell.** A concrete instance of a general rule worth stating plainly for exhaust's own logging: anything templated into a command that might carry a credential must never be logged in its rendered form.
- **"Sandboxed execution" as a marketing claim when the actual default is unsandboxed.** Default execution here runs with full host privileges; container isolation is an opt-in per step, not a default. The project's own security docs are honest about this once you read them closely, but the README's headline claim overstates it. A caution for how exhaust describes its own Sandbox guarantees: say precisely what's enforced by default versus what requires explicit configuration.
- **This repo's thirteenth confirmation that scope is prose, release-only CI, and a generic ACP tool registry with no security-specific presets.** All consistent with every prior audit; no new decision needed.

## What this settled for exhaust

- Nothing new decided; [ADR 0011](../adr/0011-playbook-verticals-are-required-or-gated.md) (skills, not a declarative DSL) is reinforced by a repo that tried the DSL route and explicitly marked its own result as unproven.
- A real open question surfaced for later, deliberate resolution: whether exhaust's Harness is an embedded agent loop, a specific CLI's native hook system, or a generic external-agent protocol, given that only the first two can support the per-action gating our other decisions assume.
