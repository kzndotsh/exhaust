# Audit: vercel-labs/deepsec

Source: [github.com/vercel-labs/deepsec](https://github.com/vercel-labs/deepsec), cloned shallow for this audit. "A security harness for finding vulnerabilities in your codebase powered by coding agents." Read-only, read in full or in part by five subagents, each scoped to one slice of the repo, then synthesized.

Deepsec's shape is different from exhaust's: it passively scans an arbitrary static codebase for vulnerabilities. Exhaust actively probes one live Target through a methodology. Ideas below are filtered for what actually transfers.

## Adopted

**Per-Workspace trust-model brief (deepsec's `INFO.md`).** A hand-written document stating what is attacker-controlled versus trusted for this Target, its auth model, and known false-positive areas, injected verbatim into every agent turn. The strongest single idea in the audit. Became the **Brief** term; see [GLOSSARY.md](../../GLOSSARY.md).

**Vertical as a gated plugin with worked examples as tests.** Deepsec's `MatcherPlugin` contract (slug, a stack/tech gate, a noise tier, `examples[]` doubling as regression tests, a `match()` function) maps directly onto a spine vertical: a skill with its own stack-check and its own tests. Settles that skills are one-per-vertical, built with structure, not bare prose files.

**Stack-detection gates which verticals run.** Deepsec's `detectTech()` plus a `requires` gate skips matchers whose stack isn't present and surfaces framework-specific notes for the ones that run. The recon vertical produces this profile; it gates and informs every vertical after it.

**Verdict stored on the finding; nothing deleted.** Deepsec's processor never deletes a finding. A revalidation verdict (true-positive, false-positive, duplicate, fixed, accepted-risk) is recorded on it, the original severity is preserved separately from any adjustment, and a manual accepted-risk marker is never auto-overwritten. Adopted wholesale as the **Finding** term, with two additions deepsec has no reason to need: a repro/evidence block, and a scope field (Sandbox-only vs. real Target) tying back to the Scope Contract. See [ADR 0004](../adr/0004-findings-are-append-only-claims.md).

**Plan-first dry run, with cost/duration budgets.** Deepsec's `--plan` (read-only, shows intent before acting) and `--max-cost-usd` / `--max-duration` / `--through <phase>` checkpoints. For an agent that actively attacks a Target, a dry run is a safety feature, not just UX, and pairs with the Scope Contract gate.

**Ship a labeled fixture and score the real agent, don't stub it.** Deepsec's own worst failure: its CI stubs the agent in every automated test, a `LIVE_AGENT=1` flag that nothing reads, and no test scores precision or recall against its own ten labeled vulnerabilities. Exhaust should commit from day one to a labeled Sandbox and a scoring script run against the real agent behind an opt-in flag.

## Rejected, and why

- **File-hash incremental rescan store.** Deepsec's unit of work is a file in a static tree; `lastScannedRunId` + `fileHash` lets it skip unchanged files. Exhaust's unit is a finding against a live Target probed through a Sandbox, not a file in a tree. Nothing to incrementally rescan.
- **The ~200-matcher regex funnel as the primary cost control.** Deepsec's main lever is a cheap deterministic pre-filter so the agent only looks at flagged files. Exhaust's agent is actively exercising a Sandbox, not triaging a static file set; the stack-gate is the real analog here, not a regex layer.
- **Match-rate-per-language as a coverage heuristic.** Deepsec's own code comments flag this as weak. Irrelevant once "done" is tracked explicitly per vertical (see [ADR 0005](../adr/0005-harness-done-is-a-per-vertical-ledger.md)).
- **Remote sandbox fan-out (partition + merge across microVMs).** Genuinely clever, but it's scale infrastructure for scanning many codebases at once. Premature for v1's one-Target, one-Sandbox, thin Harness.
- **Multi-phase reconciliation machinery.** Deepsec round-trips findings through separate scan/process/revalidate runs and must re-match verdicts back to findings (by id, then title, then a unique-remainder rule, never guessing). The *principle* (never force-apply an ambiguous match) is worth keeping; the apparatus isn't needed until exhaust's Harness is more than a single loop.

## Contradictions surfaced across the five audits

- Two sub-audits disagreed on whether deepsec supports one-skill-per-vertical. It does not: there is one shared core prompt plus small per-slug and per-stack lookups, not a folder per vulnerability class.
- One sub-audit called deepsec's JSON store "the source of truth" generally; another clarified that `.deepsec/data/` specifically is a per-file scan *cache*, not a CVE or signature database. Deepsec has no external vulnerability feed to borrow for a known-CVE vertical; that sourcing is exhaust's own problem to solve.
- Not a real contradiction, but worth stating plainly: deepsec has rich resumable-phase checkpointing (where a run stopped) but no real completeness condition (whether coverage is exhaustive). Exhaust needs both; deepsec only has the former.

## What this settled for exhaust

- Findings storage shape: [ADR 0004](../adr/0004-findings-are-append-only-claims.md).
- The Harness's "done" condition: [ADR 0005](../adr/0005-harness-done-is-a-per-vertical-ledger.md).
- The **Brief** and **Finding** glossary terms.
- That each spine vertical is a skill built as a gated plugin with its own test examples, not a bare markdown file.
