# Audit: anthropics/defending-code-reference-harness

Source: [github.com/anthropics/defending-code-reference-harness](https://github.com/anthropics/defending-code-reference-harness), cloned shallow for this audit. "Skills for threat modeling, scanning, triage, patching, plus an autonomous scanning harness you can `/customize`." Anthropic's own reference implementation, drawn from partnering with security teams since Claude Mythos Preview, built around the exact vocabulary (skills, a harness) exhaust uses. Read-only, read by five subagents each scoped to one slice. See also the [deepsec](2026-10-26-deepsec-audit.md) and [Shannon](2026-10-26-shannon-audit.md) audits.

One operational note: a subagent's own safety classifier flagged itself mid-run because it was quoting this repo's literal prompt-tag syntax (`<overall>`, `<score>`, and similar) back verbatim in its report. That is the classifier working as intended on quoted tag-shaped text, not an actual incident, and it's exactly the failure mode [ADR 0009](../adr/0009-untrusted-target-output-is-delimited.md) below exists to prevent.

## Adopted, or strongly validated

**A `confirmed` Verdict needs a host-run Oracle.** Despite compiling ASAN into every target, this repo's own discovery stage never has the host re-execute a proof-of-concept: "crash_found" is entirely an LLM grader reading its own prose tags. The only place anything is code-enforced is a separate patch-validation ladder, not discovery. The one place in the whole repo that gets this right is its own detection-and-response track, where the ground truth is mounted read-only inside a fresh grading container the investigating agent never sees. Recorded as the **Oracle** glossary term and [ADR 0008](../adr/0008-confirmed-requires-a-host-run-oracle.md).

**Scope enforcement here is prose too, with the gap stated and then ignored in the same repo.** `docs/security.md` says outright "constraints must be enforced in code, not prompts." The authorization statement is, itself, a prompt string (`DEFAULT_ENGAGEMENT_CONTEXT`), overridable by a file. This is the fourth tool audited with the identical gap (deepsec, Shannon, and this repo's own two tracks). [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md) is now amended to say the authority a Scope Contract grants can never be satisfiable by anything that arrives inside the agent's own context, a Target's response included.

**No ground-truth evaluation of discovery quality, anywhere.** Recall and precision figures in this repo's own READMEs ("15/15 landed crashes," "~70% crash-found rate") are manual, tiny-n, self-reported anecdotes. The one deterministic scorer in the entire repo belongs to the detection-and-response track. Fourth confirmation of the eval gap deepsec first surfaced.

**Untrusted Target output needs its own delimiter.** This repo already has a dedicated module for exactly this (`prompts/untrusted.py`, nonce-delimited tool output so the model doesn't mistake it for instructions). Exhaust needs the same mechanism for a stronger reason: a live Target is actively adversarial by construction, not merely an untrusted data source. Recorded as [ADR 0009](../adr/0009-untrusted-target-output-is-delimited.md).

**Payload handoff via a file, never shell argv or heredoc.** The skills' shared `checkpoint.py` deliberately writes agent-derived strings to a file via the Write tool rather than passing them through a shell command, specifically to keep Target-derived content out of argv. A concrete, cheap practice worth copying for the Harness's own checkpointing.

**A fresh, isolated verifier/reviewer that never sees the investigator's reasoning.** The patch skill's reviewer sees only file, line, category, and diff, never the finding's own prose description. The grade/judge stages run in a separate container from the one that found the crash. This is the same independent-verifier discipline the overall-architecture report's field lessons argued for directly ("a discovery agent that also verifies self-censors true positives").

## Rejected, and why

- **Enumerated vulnerability checklists inside a discovery prompt.** This repo's own `docs/best-practices.md` argues the opposite of what we'd been assuming: "describe vulnerability shapes, not checklists — enumerating bug classes hurts recall." Its own `vuln-scan` skill contradicts this (it does use a category menu), which the auditor flagged as an internal inconsistency in the source repo itself. We're not resolving this by fiat: it's a real, open tension, written up below rather than decided.
- **Prose-tag parsing for verdicts, with fail-open defaults.** Judge falls back to `NEW` on any parse failure; grader score defaults to `0.0`; missing criteria default to `FAIL`. Exhaust's typed, tool-recorded Verdict (ADR 0007) is already strictly better than this pattern; nothing to change, just confirmation.
- **A sandbox gate that's only an env-var check.** `harness/sandbox.py`'s `require()` refuses to run unless `VULN_PIPELINE_AGENT_RUNTIME` is set, but setting that variable by hand skips the real protection, which lives in a shell wrapper script, not the Python gate itself. A caution for how exhaust's own Scope Contract check should be wired: it needs to sit at the point of actual network or tool access, not a preflight an operator can route around.
- **Per-run regeneration of findings rather than true append-only history.** This repo's `TRIAGE.json` is rewritten each run from checkpoints, with duplicates recorded as `duplicate_of` but the file itself replaced, not appended to. Exhaust's Finding model (ADR 0004) already committed to genuine append-only records; no change needed.

## The open tension: enumerate, or describe a shape?

The repo's own best-practices doc and its own `vuln-scan` skill disagree with each other. Our reading: these aren't actually contradictory once you separate two different jobs. A fixed, named vertical in the spine is for *tracking coverage* (exactly what ADR 0005's per-vertical ledger needs: something concrete to mark exhausted or skipped). But the prompt an agent actually works from *within* a vertical should describe the vulnerability's shape and explicitly invite variant-hunting, not hand the agent a literal form to fill in line by line. That's our working resolution, not a settled decision; it's worth a second look once real skills get written.

## What this settled for exhaust

- **Oracle** glossary term and [ADR 0008](../adr/0008-confirmed-requires-a-host-run-oracle.md): a `confirmed` Verdict requires host-executed evidence.
- [ADR 0009](../adr/0009-untrusted-target-output-is-delimited.md): Target output gets its own prompt delimiter.
- [ADR 0003](../adr/0003-scope-contract-gates-real-targets.md) amended: the Scope Contract's authority can never be satisfied by anything inside the agent's own context.
- Open, not settled: how literally a vertical's internal prompt should enumerate sub-checks versus describe a shape.
