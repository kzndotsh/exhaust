# Audit: chainreactors/cyber-harness

Source: [github.com/chainreactors/cyber-harness](https://github.com/chainreactors/cyber-harness), cloned shallow for this audit. "AI-driven pi-like agent for cyber security — single binary for pentest, red team, bug bounty." The largest and most mature codebase audited so far (a full Go monorepo with its own egress and guardrail modules, a client-server Hub/node topology, and a real web UI), and the closest in stated purpose to exhaust's actual intended use. Read-only, read by five subagents each scoped to one slice, given the repo's size. See also the [deepsec](2026-10-26-deepsec-audit.md), [Shannon](2026-10-26-shannon-audit.md), [defending-code-reference-harness](2026-10-26-defending-code-reference-harness-audit.md), [OWASP ASRH](2026-10-26-owasp-asrh-audit.md), and [Cloudflare security-audit-skill](2026-10-26-cloudflare-security-audit-skill-audit.md) audits.

## The headline finding: the strongest evidence yet that code-enforced scope is a real, unsolved gap

This repo has dedicated modules named `egress`, `guardrail`, and `decision`, exactly the names you'd expect for a code-enforced authorization boundary. The reality: `core/egress` is an interface with exactly one implementation, a no-op (`Disabled()` returns empty strings for everything). `exts/guardrail` is an LLM-judged policy that is **off by default** (admits every tool call when unconfigured) and, even when enabled, only ever sees a tool call's name and working directory, never a structured target list to check a host against; the only place a target's scope can be mentioned at all is a free-text field concatenated into the judge's own prompt. `core/decision` is just protobuf wire types nothing in this slice even imports. Six tools audited now (deepsec, Shannon, the Anthropic reference harness, OWASP ASRH, Cloudflare's skill, and this one), and this is the sixth with the identical gap, in the one repo whose module names most directly promised a different answer. This isn't a new decision, it's the clearest confirmation yet that [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md) addresses something nobody else in this space has actually solved.

## Adopted, or strongly validated

**The Rig should wrap a pinned catalog of existing tools, not reimplement them.** `arsenal.yaml` pins version, source repository, and release-asset pattern for a long list of external security binaries (several already in your own Nix lab module) and installs them through a small manager, rather than hand-rolling scanning primitives mature tools already do well. Adopted as [ADR 0012](../adr/0012-rig-wraps-a-pinned-tool-catalog.md).

**Skills should use progressive disclosure, not one monolithic file.** A short top-level skill lists what's available; each tool's full playbook is a separate doc loaded only on that tool's first invocation through a virtual path. Adopted as [ADR 0013](../adr/0013-skills-use-progressive-disclosure.md).

**A finalize-time validator that refuses completion, not a self-report, decides "done."** `cmd/audit`'s `validate()` blocks a run from completing when coverage is empty, required tool-check records are missing, or a confirmed finding lacks trace, evidence, or reproduction, paired with a small bounded repair loop. This is a concrete, buildable mechanism for ADR 0005's principle that the Harness, not the agent's claim, decides exhaustion.

**"Reaching a limit or producing final text does not by itself prove the task is done."** Quoted nearly verbatim from this repo's own docs. The sharpest one-line statement of ADR 0005's whole point found in any audit so far.

**Keep raw evidence, judged findings, and coverage state as three separate records.** This repo's own docs state the same split our Finding/ledger model already committed to: exact evidence stays in raw artifacts, model-compacted history is lossy and kept apart from it, and coverage state is its own record. Confirmation, not a new idea.

**A per-evaluation copy-on-write workspace.** `cmd/audit` runs each evaluation against a copied temporary worktree, never writing back to the original. A rough analog of Workspace-per-Target isolation, worth keeping in mind when the Sandbox interacts with source under review.

## Sharpened or reinforced

**A real example of operator-side, honest, manual verification, written up candidly.** `docs/verification/mcp-jadx-llm.md` documents one real session where the model's claims were checked by hand (an independently written verifier script, a byte-for-byte comparison, cross-checked against upstream source), and the doc states its own limits plainly: this "cannot be taken as proof any reverse-engineering conclusion is automatically correct." It's the same Oracle gap as every other tool, but the only one audited that documents the gap this candidly rather than implying it's solved.

**A clean architectural shape for where to attach an Oracle check.** The agent loop's hook points (`before_run`, `after_model`, `run_end`, and similar) are a seam where trusted, host-side verification could run regardless of what the agent itself decided. Worth keeping as a reference shape for the Harness's own implementation, not a new decision.

## Rejected, and why

- **LLM-as-judge for task completion, used as if it were a finding's verdict.** The agent loop's `Evaluator` is a forced-tool-call judge deciding whether a goal was met (`pass`, `continue`, `reason`, `feedback`), which is a reasonable pattern for *task completion* but is not what confirms a *Finding*. If exhaust ever borrows the typed-verdict-tool shape here, it needs its own host-side Oracle gate behind it; this repo's pattern alone doesn't have one.
- **The two-stage guardrail (`risk` then `consequence`) as a stand-in for a Scope Contract.** It's a reasonable idea for mitigating obviously dangerous individual tool calls, but it is not, and was never designed to be, a target-authorization gate. Worth noting the distinction so a future reader doesn't conflate "an LLM reviews risky calls" with "the Harness enforces what Target may be touched."
- **No fixed methodology spine at all, confirmed a second time.** `cmd/audit` has no named vulnerability-class taxonomy in code; its only guidance is one prose hint (auth, tenant boundaries, state changes, concurrency, parsing, business rules). This is now the second tool (after the reference harness's own internal self-contradiction) landing on the "open-ended, not enumerated" side of that still-unresolved tension, and this one pairs it with a strong finalize-time validator rather than relying on the prompt alone. Noted as more evidence, not a resolution.

## What this settled for exhaust

- [ADR 0012](../adr/0012-rig-wraps-a-pinned-tool-catalog.md): the Rig wraps a pinned external tool catalog.
- [ADR 0013](../adr/0013-skills-use-progressive-disclosure.md): skills use progressive disclosure.
- The strongest confirmation yet of [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md): six for six on scope being prose-only elsewhere, even where module names promise otherwise.
- Still open: the enumerate-vs-open-ended tension from the reference-harness audit, now with a second data point on the open-ended side.
