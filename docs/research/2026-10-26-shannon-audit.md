# Audit: KeygraphHQ/shannon

Source: [github.com/KeygraphHQ/shannon](https://github.com/KeygraphHQ/shannon), cloned shallow for this audit. "An autonomous AI pentester for web applications and APIs. It analyzes source code, identifies attack paths, and executes real exploits to prove vulnerabilities. No exploit, no report." Read-only, read by five subagents each scoped to one slice, synthesized directly (not via a separate synthesis pass, since the synthesis subagent's output was cut off mid-report and this audit's own session already holds all five full reports).

Shannon's shape is much closer to exhaust's than deepsec's was: active exploitation of a live target, not passive scanning of a static codebase. See also the prior [deepsec audit](2026-10-26-deepsec-audit.md).

## Adopted, or strongly validated

**Verdict recorded through a typed tool, never prose.** Shannon's prompts state it directly: "record the verdict via tool, do not narrate." Combined with deepsec's schema-validated writes and repair loop, this is now two independent tools agreeing on the same discipline. Recorded as [ADR 0007](../adr/0007-verdicts-are-recorded-through-typed-tools.md) and the **Verdict** glossary term.

**The Scope Contract is solving a real, unsolved problem, and must be code-enforced.** Shannon's safety model is prose only: `docs/safety.md` says "get explicit written authorization" and "don't target production," but nothing in the code checks authorization, scope, or production status. There is no allowlist, no attestation record, no sandbox-vs-real-target distinction anywhere in the codebase; it's all model instructions. Deepsec has no equivalent mechanism either. Two different tools, two different shapes, the same gap. This strongly reinforces [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md) as already correctly scoped: the Scope Contract has to be a file the Harness actually checks before it will touch a real Target, not a line in a prompt the agent is merely asked to respect.

**"Confirmed" is a claim, not a fact, until independently checked.** Shannon's own "no exploit, no report" tagline is not a hard gate: it's a prompt instruction plus a self-attested enum (`exploited`/`blocked`) that the code validates for shape, not for whether the evidence actually demonstrates impact. Shannon's own docs admit "verification is required," meaning a human has to check it. This validates our Finding model's existing shape (a verdict is stored, never auto-trusted, carries a repro/evidence block for a human or later pass to check) rather than changing it.

**A vertical's internal structure is a fixed, numbered checklist, not an open-ended prompt.** Shannon's auth vertical has 9 fixed sections (transport, rate limiting, cookies, token properties, fixation, password policy, login responses, recovery/logout, SSO/OAuth); what gets tested within each section is dynamic (discovered from recon), but the sections themselves are not. This sharpens how each spine vertical should be built: a skill isn't just "the auth skill," it's a fixed procedure the agent works through for this Target.

**A severity floor and an adversarial default.** "A finding with no real consequence is not reported" and "assume every finding is a false positive until proven otherwise" (the review stage ignores prior reasoning and re-reads code fresh). Both are cheap, concrete discipline against an autonomous agent over-reporting to look productive.

**Pin a Workspace to its Target; refuse a mismatched resume.** Shannon's workspace records the target URL and refuses to resume if a later run's URL doesn't match, "to prevent cross-target contamination." A Workspace already belongs to one Target by construction, but nothing currently stops a Harness run from being pointed at a different URL while reusing an existing Workspace's state. Worth a guard.

**Git as the checkpoint/rollback store.** Shannon commits a checkpoint before each agent runs, commits again on success, and rolls back on failure; resume restores only the incomplete agent's paths. A plain, inspectable mechanism for Workspace state, worth considering over inventing a bespoke journal.

**Destructive-op separation.** A scoped `stop` (no infrastructure touched) versus a `reset` that requires typing a confirmation word and wipes everything. Cheap insurance against an autonomous tool's own cleanup commands.

## Rejected, and why

- **Temporal as the orchestration engine.** Shannon's own code comments and docs say Temporal only earns its keep at scale; the same per-run resumability it provides (retries, resume, isolation) could be had with a plain loop plus files and a lock. This is a direct validation of the already-decided thin v1 Harness, not a reason to add a workflow engine.
- **TypeScript/Docker/multi-container stack.** Shannon's CLI-talks-to-a-separate-worker-container-via-a-shared-Temporal-server architecture fits a multi-tenant SaaS product with paid tiers. Exhaust is a local, single-user, Python tool; there's no second process or server to orchestrate around.
- **Fixed-five-verticals-only coverage.** Shannon always runs exactly five classes (auth, authz, injection, xss, ssrf) plus a catch-all "miscellaneous" bucket for everything else (logic flaws, info disclosure, and more, each needing its own ad hoc justification). Exhaust's wider, explicit spine (which already names SSRF/CSRF, deserialization, known-CVE, info disclosure, and disclosure as their own verticals rather than a grab-bag) is more rigorous, not less; no change needed there.
- **The unverified benchmark and coverage checklist.** `COVERAGE.md`'s ~52 checkmarks against a WSTG checklist have no test or evidence behind them, just the claim. The xbow/aikido benchmark is informal: one target, non-blind TP/FP labeling done by Keygraph itself, no independent replay. This is the same eval gap deepsec had (no scored precision/recall in CI), confirmed again rather than solved. The lesson from the deepsec audit stands: ship a labeled Sandbox and a real scoring script from day one, and don't publish a coverage claim without evidence behind each item.

## Contradictions and caveats

- Shannon's own `COVERAGE.md` lists more vulnerability classes (splitting out SQLi and command injection specifically) than its own `docs/safety.md` and the prompt files actually implement (five fixed classes plus a catch-all). The marketing surface overstates the code.
- The repo's `.github/workflows` only contains release/rollback automation; the "does it run a real pentest in CI" question is unanswerable from this repo, since that logic lives in separate sibling repos (`shannon-action`, `shannon-ci`) not included in this audit.
- Shannon's own "workspace" term is unrelated to ours. Checked directly and confirmed different: it's a per-run resumable state directory (a second scan of the same Target without reusing a name gets a new one), not a long-lived per-Target project directory. No glossary collision, nothing to reconcile.

## What this settled for exhaust

- [ADR 0007](../adr/0007-verdicts-are-recorded-through-typed-tools.md): verdicts recorded through typed tools, never prose. New **Verdict** glossary term.
- Confirms [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md) and [ADR 0005](../adr/0005-harness-done-is-a-per-vertical-ledger.md) as already correctly scoped; no changes needed to either.
- A spine vertical's internal shape should be a fixed, numbered checklist the agent works, not an open-ended skill description.
- Worth a small follow-up guard: a Workspace should refuse a Harness run against a Target that doesn't match the one it was created for.
