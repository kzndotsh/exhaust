# Audit: CISOfy/lynis

Source: [github.com/CISOfy/lynis](https://github.com/CISOfy/lynis), cloned shallow for this audit. "Security auditing tool for Linux, macOS, and UNIX-based systems. Assists with compliance testing (HIPAA/ISO27001/PCI DSS) and system hardening." A pure POSIX-shell system-hardening and compliance auditor, developed since 2007, with no AI component at all. A different domain from every prior audit (local host/config compliance, not active web-app pentesting), chosen specifically to see what fifteen years of real-world iteration on "run hundreds of individually registered checks and produce a structured report" converges on. Read-only, read by four subagents.

## Adopted or reinforced

**Register is the single choke point, and "not run" is a first-class outcome with a reason.** Every one of Lynis's ~461 checks passes through one registration function, which decides and logs whether it runs or is skipped, and why. Any score or report the system produces is scoped only to what actually ran. This is the exact mechanism ADR 0005 already called for, arrived at independently in an unrelated domain fifteen years ago; folded into that ADR as the concrete shape to implement it in, not a new decision.

**Namespaced ID prefixes and declarative, cleanly-skipping prerequisites.** Each check's stable ID carries its category as a prefix (`AUTH-9204`, `SSH-7408`), with custom or third-party checks namespaced separately (`CUST-`) so they can't collide with the core catalog. A check declares what it needs (an OS, a package manager, a binary) and is skipped cleanly, never failed, when that's absent. Both line up with and reinforce our stack-gating design (ADR 0011) rather than adding anything new.

**A separate verbose log from the machine-readable report, with an explicit mode to suppress logging entirely.** Worth carrying into exhaust's own design as an option: a way to keep potentially sensitive Target data (discovered credentials, for instance) out of a persistent log even when full detail is wanted in the structured report.

## New decision

**No hand-maintained vertical catalog, separate from the skill files themselves.** Lynis kept exactly this kind of secondary index (`db/tests.db`) alongside its real source of truth, and it has drifted after years of maintenance: 34 checks that exist in code are missing from the index, 5 entries in the index point at checks that no longer exist. The audit engine itself doesn't even read the stale file, so the drift was invisible until someone went looking. Recorded as [ADR 0016](../adr/0016-no-hand-maintained-vertical-catalog.md): whatever needs to list exhaust's verticals computes that list from the skill files directly, never from a second file meant to mirror them.

## Noted, not adopted

**A single aggregate hardening-index score.** Lynis computes a 0-100 score from partial credit each check awards itself, banded into a hardening posture. This answers a question exhaust doesn't have: we're producing a list of discovered Findings against one Target, not a single compliance-posture number across many configuration facts. Not transferable, and not a gap in our design, just a different kind of deliverable.

**A grep-based target-type extension (static Dockerfile auditing) added without touching the core.** A clean existence proof that a new *kind* of target (a static manifest, not a live host) can be bolted on as an independent module. Worth remembering if exhaust's own Target concept ever needs to generalize past live web applications, but nothing to act on now given your actual targets so far.

## Rejected, and why

- **Re-deriving structured screen output by parsing the verbose log back out with grep and sed.** Called out by the project's own code as fragile. Already avoided by our typed Verdict and Finding records existing as their own channel; worth remembering as a reason, not just a preference.
- **Compliance-framework mapping that's declared in config but never actually wired to anything.** Flags for HIPAA, ISO27001, and PCI-DSS exist, but nothing in the open-source code ever calls the function that would record a compliance finding. Another instance of a documented capability that outruns the code behind it, the same lesson from several prior audits now seen in a tool with no AI involved at all, showing it's a general software-maturity failure mode, not one specific to agent-driven tools.
- **Fourteenth-plus confirmation that CI is metadata/lint-only, no audit-as-test.** Consistent with every prior audit; no new decision needed.

## What this settled for exhaust

- [ADR 0005](../adr/0005-harness-done-is-a-per-vertical-ledger.md) sharpened with a concrete implementation shape: one registration choke point, not-run as a first-class state.
- [ADR 0016](../adr/0016-no-hand-maintained-vertical-catalog.md): the spine's catalog is always derived from skill files, never a separate hand-maintained index.
