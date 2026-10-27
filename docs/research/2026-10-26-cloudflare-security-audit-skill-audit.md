# Audit: cloudflare/security-audit-skill

Source: [github.com/cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill), cloned shallow for this audit. "A coding-agent skill for multi-phase security audits with independently verified, machine-readable findings." Cloudflare's own tool, MIT-licensed, which the README says seeded Cloudflare's internal vulnerability-discovery harness. Read-only, read by four subagents each scoped to one slice. See also the [deepsec](2026-10-26-deepsec-audit.md), [Shannon](2026-10-26-shannon-audit.md), [defending-code-reference-harness](2026-10-26-defending-code-reference-harness-audit.md), and [OWASP ASRH](2026-10-26-owasp-asrh-audit.md) audits.

Important framing difference: this tool is static-source-first by design, and explicitly refuses to probe anything live. Its own skill file forbids testing "deployed endpoints, external services, shared infrastructure, production identities ... live control planes," and any local dynamic check must run inside an OS-enforced sandbox with no network access or it doesn't run at all. It never needed a Scope Contract because it structurally never reaches past its own sandbox. Exhaust does need one, because exhaust's whole premise is attacking a live Sandbox and, with authorization, a real Target.

## Adopted, or strongly validated

**A small always-on core plus recon-gated domain modules, never a flat list.** Nine target-neutral attack classes (injection, access control, business logic, and similar) run on every audit. Ten domain modules (web auth, client-side, cloud/IaC, AI/LLM, memory safety, supply chain, protocols, desktop/IPC, resource exhaustion, data lifecycle) are selected in only when recon finds the specific trust boundary that module exists to cover, explicitly never by matching a language or dependency keyword. Adopted as [ADR 0011](../adr/0011-playbook-verticals-are-required-or-gated.md).

**A vertical's internal shape, resolved with working code.** This answers the open tension from the reference-harness audit directly. A vertical here is neither a numbered fill-in-the-blank checklist nor pure open-ended prose: it's a fixed catalog of named attack classes, each described as one dense paragraph of hunting instruction (not a yes/no item), with front-loaded false-positive guards and the same hard evidentiary gate repeated in every file (`confirmed` needs a complete source trace plus bounded local evidence, or it's `needs_validation` naming exactly what's missing).

**Evidence promotion is parent-trusted, never agent-written.** An agent's own scratch output never becomes permanent evidence directly; a separate, trusted step copies allowlisted files out, checking for symlinks, file identity, and size, with a re-check after the copy. Adopted as [ADR 0010](../adr/0010-evidence-promotion-is-parent-trusted.md).

**Fingerprint identity is stable across verdict changes.** A record's id doesn't change when its verdict does; promotion or demotion updates the same object rather than creating a new one. Matches our append-only Finding model (ADR 0004) directly.

**Rejected claims are retained with their reason, specifically to avoid relitigating them.** A later run checks whether a rejected claim's underlying source actually changed before reconsidering it. Good confirmation of the append-only design, and a concrete mechanism (a fingerprint tied to source state) worth considering for how Findings persist across repeated runs against the same Workspace.

**Budget reserved before work starts, not spent opportunistically.** Critic and validation calls are funded up front; if the budget can't cover both, the run is marked incomplete rather than quietly skipping verification to afford more hunting.

## Sharpened, not changed

**"Independently verified" here means agent-independence, not host-independence, and the project says so itself.** A fresh agent with no access to the hunter's conclusion is asked to reproduce a check inside its own sandbox, but the parent process never re-executes anything, and the validator's own documentation states its limit plainly: "validator success proves format and ledger consistency only." This is a real distinction worth holding onto. Our Oracle (ADR 0008) is the stronger design: independence of *execution*, not just independence of *reasoning*. Even the one audited tool whose entire tagline is about verified findings doesn't go that far.

## Rejected, and why

- **Terminal/"exhausted" as a formal ledger state.** Despite tracking coverage richly (`planned/in_progress/covered/candidate/blocked/deferred/not_applicable/out_of_scope`), nothing in the validator enforces that a run actually reaches a terminal state across all units; a ledger of all `planned` entries passes validation cleanly. `run_status: incomplete` exists only as prose. This is the same gap ADR 0005 already exists to close; nothing here argues for weakening that ADR.
- **No cross-check between the findings store and the coverage ledger.** The two validators are entirely standalone; nothing confirms a `candidate` ledger unit actually has a matching finding record. Worth remembering as a pitfall to design around, not a pattern to copy.
- **A confirmed Finding requiring no linked, verifiable local-check artifact.** The validator accepts a `confirmed` record with well-formed but entirely fabricated `observed_result` text; nothing ties it to a real run or a real file. This is the same self-attestation gap ADR 0008 exists to close, now seen a fifth time, in the one tool that most tries to avoid it.

## The open question, put to you directly

**Should exhaust's spine be this broad?** Cloudflare's domain modules go well past anything in our current spine: AI/LLM agent abuse, memory-safety and kernel-level bugs, supply-chain and CI compromise, desktop/mobile/IPC bridges, cloud/IaC misconfiguration, resource exhaustion, and protocol/RPC/messaging issues. None of your actual hunting targets so far (Roundcube, Webmin, ispmanager, Mail-in-a-Box) obviously call for most of these; they're server-side web applications, which our spine already covers more deeply than Cloudflare's (their injection coverage is one generic paragraph with no per-type breakdown, and their known-CVE coverage is thin by their own auditor's account, both areas where our spine is already more rigorous). The core-plus-gated-modules shape (ADR 0011) means this isn't an all-or-nothing choice: a narrower exhaust can keep the structure and simply ship fewer, deeper modules. This is a real decision, not something to infer from code; it's listed here for when the spine itself gets locked.

## What this settled for exhaust

- [ADR 0010](../adr/0010-evidence-promotion-is-parent-trusted.md): evidence promotion is parent-trusted.
- [ADR 0011](../adr/0011-playbook-verticals-are-required-or-gated.md): the spine is a core plus recon-gated domain modules.
- Confirms [ADR 0008](../adr/0008-confirmed-requires-a-host-run-oracle.md)'s Oracle design as stronger than even the most verification-focused tool audited.
- Still open, for spine-locking time: how broad exhaust's domain-module set should be.
